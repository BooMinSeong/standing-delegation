"""종이 검사 2·3 (Plan.md §7): "무의미 = 제약 위반" 진단과 그 대칭 검사 (docs/GEN-ALGO.md §15).

검사 2: GEN-V0 편집 88개(D01 51, 항공 37)를 제약에 통과시켜 미리 고정한 무의미 목록이 걸러지는지 본다.
검사 3: 저자 여덟 상태와 D01 할당표 13행이 같은 제약을 전부 통과하는지 본다.

제약 (편집 = 기준 상태 대비 바뀐 값·레코드)
  T  타입·널      : dataclass 선언(중첩 필드는 기준 값의 타입)
  V  값 범위      : sem_type 키의 환경 독립 고정표 초판 — count ≥ 0, month 1..12, date ISO, currency ISO 4217(형식)
  K  FK          : `*_id` 이름 대응. 편집이 **새로** 만든 끊긴 참조만 센다
  I  닻 정체성    : 같은 키의 레코드에서 검색 툴이 질의와 부분 문자열로 대조하는 필드가 바뀌면 기각
                   (변형판 I=: 등호 대조 필드까지). 자유 텍스트 sem_type은 뺀다
  C  개수 편집     : 레코드 수는 후보 컬렉션과 그것을 FK로 참조하는 컬렉션에서만 바뀐다.
                   후보 = 참조 커밋 인자 중 q에 글자로 나오지 않는 값을 키로 가진 컬렉션(q에 나오는 값은 닻)
  Q  q 상수 대응   : q 상수를 기준으로 건 경계 편집은 필드의 sem_type이 상수와 kind·단위가 맞아야 한다
§10 변수 범위(S)는 제약이 아니라 생성 범위라 따로 적는다(D01만. 1차는 손으로 쓴 Q, 검사 1과 같다).
재생(환경이 뜨는가)과 조회(편집된 값이 lookup·verify 툴 반환에 실제로 나오는가)를 함께 적는다.

사용: .venv/bin/python scripts/paper/c23_constraints.py   (먼저 c23_semtype.py)
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import aa  # noqa: E402
import c23_profile as P  # noqa: E402

OUT = aa.ROOT / "data" / "paper-checks" / "c23"
D01 = "store_procurement_and_inventory"
AIR = "flight_and_travel_management"
CFG = {
    D01: {"dir": aa.ROOT / "data/delegations/D01/states/gen-v0", "seed": "emergent_risk_discovery/preview_018",
          "q": (aa.ROOT / "data/delegations/D01/q_minus.txt").read_text(), "label": "D01"},
    AIR: {"dir": aa.ROOT / "data/gen-v0/flight_preview_023", "seed": "conflicting_constraints/preview_023",
          "q": (aa.ROOT / "data/gen-v0/flight_preview_023.q_plus.txt").read_text(), "label": "항공"},
}
# 돌리기 전에 기존 문서만으로 고정한 무의미 목록 (GEN-ALGO §15 표, GEN-V0.md §2.2·§3.1)
NONSENSE = {
    D01: {"P04": "닻 식별 속성(브랜드 → Lays)", "P08": "닻 식별 속성(분류 → Snacks)", "P22": "월 0",
          "P46": "단독 후보 뒤 남은 계약(FK 연쇄)"},
    AIR: {"P06": "공항 3→1로 목적지 삭제", "P10": "q 상수 3(bags)을 stops에", "P11": "q 상수 3(bags)을 stops에",
          "P12": "q 상수 3(bags)을 stops에", "P19": "q 상수 3(bags)을 stops에(N−1)", "P20": "q 상수 3(bags)을 stops에(N//3)"},
}
SCOPE_ONLY = {D01: {"P20": "revenue", "P21": "revenue", "P27": "monthly revenue", "P28": "monthly revenue"}, AIR: {}}
Q_TEMPLATES = ("경계(언급 int)", "각각 부족", "합쳐도 부족", "문자열 속 수 경계")
GENERIC_UNITS = {"", "unit", "units", "item", "items", "piece", "pieces", "count", "quantity", "number"}


def semtypes() -> dict:
    return json.loads((OUT / "semtype.json").read_text())


# ---- 차이 ---------------------------------------------------------------------
def _norm(path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", path)


def _leafdiff(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            sub = f"{path}.{k}" if path else k
            _leafdiff(a.get(k), b.get(k), sub, out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(isinstance(x, dict) for x in a + b):
        for i, (x, y) in enumerate(zip(a, b)):
            _leafdiff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append((path, a, b))


def diff(env: str, base: dict, edit: dict) -> list[dict]:
    ks = P.keys(env)
    ch = []
    for coll in sorted(set(base) | set(edit)):
        A, B = base.get(coll), edit.get(coll)
        if not isinstance(A, list) or not isinstance(B, list):
            if A != B:
                ch.append({"coll": coll, "type": "field", "key": None, "path": coll, "old": A, "new": B})
            continue
        k = ks.get(coll)
        if k:
            ma = {r.get(k): r for r in A if isinstance(r, dict)}
            mb = {r.get(k): r for r in B if isinstance(r, dict)}
            rem, add = [x for x in ma if x not in mb], [x for x in mb if x not in ma]
            if rem or add:
                ch.append({"coll": coll, "type": "count", "removed": rem, "added": add, "n": (len(A), len(B))})
            for key in ma.keys() & mb.keys():
                out = []
                _leafdiff(ma[key], mb[key], "", out)
                for path, a, b in out:
                    ch.append({"coll": coll, "type": "field", "key": key, "keyfield": k, "path": _norm(path),
                               "raw": path, "old": a, "new": b})
        else:
            if len(A) != len(B):
                ch.append({"coll": coll, "type": "count", "removed": [], "added": [], "n": (len(A), len(B))})
            for i, (x, y) in enumerate(zip(A, B)):
                out = []
                _leafdiff(x, y, "", out)
                for path, a, b in out:
                    ch.append({"coll": coll, "type": "field", "key": i, "keyfield": None, "path": _norm(path),
                               "raw": path, "old": a, "new": b})
    return ch


# ---- 제약 ---------------------------------------------------------------------
_PY = {"int": int, "float": (int, float), "str": str, "bool": bool}


def c_type(env, c) -> str | None:
    if c["type"] != "field":
        return None
    new, old = c["new"], c["old"]
    top = c["path"].split("[")[0].split(".")[0]
    cls = P.collection_classes(env).get(c["coll"])
    decl = P.class_fields(env).get(cls, {}).get(top, {})
    if new is None:
        return None if decl.get("nullable") else f"T: {c['path']} = None (널 불허)"
    if top == c["path"] and decl.get("type") in _PY:
        want = _PY[decl["type"]]
        if isinstance(new, bool) and decl["type"] != "bool":
            return f"T: {c['path']} bool ≠ {decl['type']}"
        return None if isinstance(new, want) else f"T: {c['path']} {type(new).__name__} ≠ {decl['type']}"
    if old is not None and type(old) is not type(new) and not (isinstance(old, (int, float)) and isinstance(new, (int, float)) and not isinstance(new, bool)):
        return f"T: {c['path']} {type(new).__name__} ≠ 기준 {type(old).__name__}"
    return None


def _st_of(env, st, c):
    return st[env]["fields"].get(f"{c['coll']}.{c['path']}") or st[env]["fields"].get(
        f"{c['coll']}.{re.sub(r'\\.[^.\\[]+$', '.*', c['path'])}")


def c_range(env, st, c) -> str | None:
    if c["type"] != "field":
        return None
    s = _st_of(env, st, c)
    if not s:
        return None
    k, v = s["kind"], c["new"]
    if v in ("", None):
        return None
    if k == "count" and not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
        return f"V: {c['path']}={v!r} (count ≥ 0)"
    if k == "month" and not (isinstance(v, int) and 1 <= v <= 12):
        return f"V: {c['path']}={v!r} (month 1..12)"
    if k in ("date", "datetime"):
        try:
            (dt.date.fromisoformat if k == "date" else lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00")))(v)
        except Exception:  # noqa: BLE001
            return f"V: {c['path']}={v!r} (ISO {k})"
    if k == "currency" and not (isinstance(v, str) and re.fullmatch(r"[A-Z]{3}", v)):
        return f"V: {c['path']}={v!r} (ISO 4217)"
    return None


def fk_violations(env, state) -> set:
    ks = P.keys(env)
    out = set()
    for coll, f, other in P.fks(env):
        have = {r.get(ks[other]) for r in state.get(other, []) if isinstance(r, dict)}
        for r in state.get(coll, []) or []:
            if isinstance(r, dict) and r.get(f) not in (None, "") and r.get(f) not in have:
                out.add((coll, f, r.get(f), other))
    return out


def identity_set(env, st, variant: str) -> set[tuple[str, str]]:
    idf = P.identity_fields(env)
    pairs = {(c, f) for _, _, c, f in idf["substring"]}
    if variant == "equality":
        pairs |= {(c, f) for _, _, c, f in idf["equality"]}
    ks = P.keys(env)
    keep = set()
    for c, f in pairs:
        s = st[env]["fields"].get(f"{c}.{f}", {})
        if s.get("kind") == "free_text":
            continue
        if f == ks.get(c):          # 키 자체는 정체성 규칙이 아니라 키 대응으로 본다
            continue
        keep.add((c, f))
    return keep


def c_identity(env, st, c, variant="substring") -> str | None:
    if c["type"] != "field" or c.get("keyfield") is None:
        return None
    if (c["coll"], c["path"]) in identity_set(env, st, variant):
        return f"I{'=' if variant == 'equality' else ''}: {c['coll']}.{c['path']} (같은 키 {c['key']})"
    return None


def candidates(env) -> tuple[set, set]:
    """(후보 컬렉션, 딸린 컬렉션)."""
    seed = next(s for s in aa.seeds() if s["pair_id"] == CFG[env]["seed"])
    st0 = aa.initial_state(seed)
    q = CFG[env]["q"]
    ks = P.keys(env)
    vals = []
    for n in seed["execution_dag"]["nodes"]:
        if n.get("kind") != "commit":
            continue
        for v in n["params"].values():
            try:
                vv = json.loads(v) if isinstance(v, str) and v.startswith("[") else v
            except Exception:  # noqa: BLE001
                vv = v
            vals += vv if isinstance(vv, list) else [vv]
    cand = set()
    for coll, k in ks.items():
        keyvals = {r.get(k) for r in st0.get(coll, []) if isinstance(r, dict)}
        if any(v in keyvals and str(v) not in q for v in vals):
            cand.add(coll)
    dep = {coll for coll, f, other in P.fks(env) if other in cand}
    return cand, dep - cand


def c_count(env, c, cand) -> str | None:
    if c["type"] != "count":
        return None
    allowed = cand[0] | cand[1]
    return None if c["coll"] in allowed else f"C: {c['coll']} {c['n'][0]}→{c['n'][1]} (후보 컬렉션 아님)"


def _units_ok(field_units, const_unit) -> bool:
    fu = {u.rstrip("s") for u in field_units}
    cu = (const_unit or "").lower().rstrip("s")
    return not fu or bool(fu & {g.rstrip("s") for g in GENERIC_UNITS}) or cu in fu or cu in GENERIC_UNITS


def c_qconst(env, st, c, template: str | None) -> str | None:
    if not template or not template.startswith(Q_TEMPLATES) or c["type"] != "field":
        return None
    qc = st[env].get("qconst") or {}
    if template.startswith("문자열 속 수 경계"):
        m = re.search(r"\d+\s+(\w+)", str(c["new"]))
        unit = m.group(1).lower() if m else ""
        return None if _units_ok([unit], qc.get("unit")) else f"Q: 문장 속 단위 {unit!r} ≠ q 상수 {qc.get('unit')!r}"
    s = _st_of(env, st, c)
    if not s or s["kind"] == "unknown":
        return None   # 모르면 넓은 쪽(남긴다)
    if s["kind"] != qc.get("kind"):
        return f"Q: {c['path']} kind {s['kind']} ≠ q 상수 {qc.get('kind')}"
    if not _units_ok(s.get("units", []), qc.get("unit")):
        return f"Q: {c['path']} 단위 {s.get('units')} ≠ q 상수 {qc.get('unit')!r}"
    return None


# ---- §10 변수 범위 (D01, 손으로 쓴 Q) -------------------------------------------
def tool_fields(env, state) -> dict[str, set]:
    out: dict[str, set] = {}
    colls = [c for c in P.collection_classes(env) if state.get(c)]
    recs = [None] + [r for c in colls for r in state[c][:3] if isinstance(r, dict)]
    for rec in recs:
        for t, res in P.call_tools(env, state, rec).items():
            acc: set = set()
            if not (isinstance(res, dict) and "__error__" in res):
                P._walk_keys(res, acc)
            out.setdefault(t, set()).update(acc)
    return out


def scope_d01(st, state, qversion: str) -> dict[str, str]:
    """필드 → 차수. qversion ∈ {'minus', 'plus'}."""
    first = {"supplier_contracts.active", "supplier_contracts.ordering_permitted"}
    span = {"supplier_listings.price", "supplier_listings.available_quantity"}
    if qversion == "plus":
        first |= span
    tf = tool_fields(D01, state)
    lead = {f.split(".")[1] for f in first | span}
    second_names = set()
    for t, fs in tf.items():
        if fs & lead:
            second_names |= fs
    out = {}
    qc = st[D01].get("qconst") or {}
    for key, s in st[D01]["fields"].items():
        coll, path = key.split(".", 1)
        leaf = path.split(".")[-1].replace("[]", "")
        if key in first:
            out[key] = "1차"
        elif key in span or (path in second_names and coll in ("supplier_listings", "supplier_contracts")):
            out[key] = "2차"
        elif coll == "purchase_orders":
            out[key] = "이력"
        elif s["kind"] == qc.get("kind") and _units_ok(s.get("units", []), qc.get("unit")):
            out[key] = "3차"
        elif s["kind"] in ("unit", "currency") or leaf in ("unit", "currency"):
            out[key] = "단위·통화(§4)"
        elif s["kind"] == "unknown":
            out[key] = "미정(넓은 쪽: 남김)"
        else:
            out[key] = "범위 밖"
    return out


# ---- 재생·조회 -------------------------------------------------------------------
def replay(env, state) -> str | None:
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            aa.env_class(env)(copy.deepcopy(state))
        return None
    except Exception as ex:  # noqa: BLE001
        return f"{type(ex).__name__}: {ex}"[:160]


def _find(res, keyfield, key, raw_path, new) -> bool:
    hit = False

    def walk(x):
        nonlocal hit
        if hit:
            return
        if isinstance(x, dict):
            if keyfield is None or x.get(keyfield) == key:
                cur = x
                ok = True
                for part in re.findall(r"[^.\[\]]+|\[\d+\]", raw_path):
                    if part.startswith("["):
                        i = int(part[1:-1])
                        cur = cur[i] if isinstance(cur, list) and len(cur) > i else None
                    else:
                        cur = cur.get(part) if isinstance(cur, dict) else None
                    if cur is None:
                        ok = False
                        break
                if ok and cur == new:
                    hit = True
                    return
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(res)
    return hit


def _contains(res, rec) -> bool:
    """결과 안에 rec의 모든 스칼라 필드가 같은 dict가 있는가."""
    scal = {k: v for k, v in rec.items() if not isinstance(v, (list, dict))}
    found = False

    def walk(x):
        nonlocal found
        if found:
            return
        if isinstance(x, dict):
            if scal and all(x.get(k) == v for k, v in scal.items()):
                found = True
                return
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(res)
    return found


def reachable_added(env, base, state, c) -> list[bool]:
    """더해진 레코드가 lookup·verify 툴 반환에 통째로 나타나는가."""
    if c["type"] != "count":
        return []
    k = P.keys(env).get(c["coll"])
    B = [r for r in state.get(c["coll"], []) if isinstance(r, dict)]
    added = [r for r in B if r.get(k) in c["added"]] if k else B[len(base.get(c["coll"], [])):]
    out = []
    for rec in added:
        res = P.call_tools(env, state, rec)
        out.append(any(_contains(v, rec) for name, v in res.items() if not name.startswith("__")))
    return out


def reachable(env, state, c) -> bool | None:
    if c["type"] != "field" or c.get("keyfield") is None:
        return None
    rec = next((r for r in state.get(c["coll"], []) if isinstance(r, dict) and r.get(c["keyfield"]) == c["key"]), None)
    res = P.call_tools(env, state, rec)
    if any(_find(r, c["keyfield"], c["key"], c["raw"], c["new"]) for r in res.values()):
        return True
    # 인자를 그 레코드를 가리키는 다른 레코드에서 채워 본다 (예: 정품 기록 ← 재고의 authenticity_record_id)
    for coll, rows in state.items():
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and coll != c["coll"] and c["key"] in r.values():
                res = P.call_tools(env, state, r)
                if any(_find(x, c["keyfield"], c["key"], c["raw"], c["new"]) for x in res.values()):
                    return True
    return False


# ---- 판정 ----------------------------------------------------------------------
def judge(env, st, base, edit, template=None, cand=None):
    cand = cand or candidates(env)
    ch = diff(env, base, edit)
    rules, rules_eq = [], []
    for c in ch:
        for r in (c_type(env, c), c_range(env, st, c), c_identity(env, st, c), c_count(env, c, cand),
                  c_qconst(env, st, c, template)):
            if r:
                rules.append(r)
        r = c_identity(env, st, c, "equality")
        if r:
            rules_eq.append(r)
    newfk = fk_violations(env, edit) - fk_violations(env, base)
    rules += [f"K: {a}.{f}={v} → {o} 없음" for a, f, v, o in sorted(newfk, key=str)]
    reach = [reachable(env, edit, c) for c in ch if c["type"] == "field"]
    reach += [x for c in ch for x in reachable_added(env, base, edit, c)]
    return {"changes": ch, "rules": rules, "rules_eq": rules_eq, "replay": replay(env, edit), "reach": reach}


def check2(st):
    rows = []
    for env, cfg in CFG.items():
        man = json.loads((cfg["dir"] / "manifest.json").read_text())
        base = json.loads((cfg["dir"] / "base.json").read_text())
        cand = candidates(env)
        scope = scope_d01(st, base, "minus") if env == D01 else {}
        for d in man["dims"]:
            pid = d["file"][:-5]
            edit = json.loads((cfg["dir"] / d["file"]).read_text())
            j = judge(env, st, base, edit, d["template"], cand)
            fields = sorted({f"{c['coll']}.{c['path']}" for c in j["changes"] if c["type"] == "field"})
            rows.append({"env": cfg["label"], "id": pid, "change": d["change"], "template": d["template"],
                         "rules": j["rules"], "rules_eq": j["rules_eq"], "replay": j["replay"], "reach": j["reach"],
                         "nonsense": NONSENSE[env].get(pid), "scope_only": SCOPE_ONLY[env].get(pid),
                         "scope": {f: scope.get(f, "—") for f in fields} if env == D01 else None})
    return rows, {env: candidates(env) for env in CFG}


# ---- 검사 3 --------------------------------------------------------------------
def d01_seed_state():
    seed = next(s for s in aa.seeds() if s["pair_id"] == CFG[D01]["seed"])
    return aa.initial_state(seed)


def _lst(s, sup):
    return next(l for l in s["supplier_listings"] if l["supplier_id"] == sup)


def _con(s, sup):
    return next(c for c in s["supplier_contracts"] if c["supplier_id"] == sup)


def b_many(s):
    """SUP-002의 쌍둥이를 더한 판. ID·이름·SKU·연락처만 다르다(D-042: 이름은 다르게)."""
    l2, c2 = copy.deepcopy(_lst(s, "SUP-002")), copy.deepcopy(_con(s, "SUP-002"))
    l2.update(supplier_id="SUP-004", supplier_name="FreshFlow Beverage Wholesale", supplier_sku="FF-COKE-CAN",
              contact_details="procurement@freshflow.example.com | +1-800-555-1104")
    c2.update(contract_id="CON-004", supplier_id="SUP-004")
    s["supplier_listings"].append(l2)
    s["supplier_contracts"].append(c2)
    return s


def alloc_rows():
    """GEN-ALGO §17 D01 예산표 13행. (영역, 기준, 편집 설명, CASE, 기준 상태, 편집 상태, q 상수 편집인가, 비고)."""
    S0 = d01_seed_state()
    one = lambda: copy.deepcopy(S0)  # noqa: E731
    many = lambda: b_many(copy.deepcopy(S0))  # noqa: E731
    rows = []

    def add(region, bname, desc, case, base, fn, qc=False, note=""):
        e = fn(copy.deepcopy(base))
        rows.append((region, bname, desc, case, base, e, qc, note))

    add("CONTROL", "B_one", "답 업체 계약 비활성", "", one(), lambda s: (_con(s, "SUP-002").update(active=False), s)[1])
    add("CONTROL", "B_one", "답 업체 가용량 60", "", one(), lambda s: (_lst(s, "SUP-002").update(available_quantity=60), s)[1], True)
    add("CLOSE", "B_many", "쌍둥이 한쪽 계약 비활성", "", many(), lambda s: (_con(s, "SUP-004").update(active=False), s)[1])
    add("OPEN", "B_one", "SUP-003 가격 0.75 (동률)", "R2", one(), lambda s: (_lst(s, "SUP-003").update(price=0.75), s)[1])

    def zero(s):
        s["supplier_listings"] = [l for l in s["supplier_listings"] if l["product_id"] != "PROD-001"]
        gone = {c["supplier_id"] for c in s["supplier_contracts"] if c["product_id"] == "PROD-001"}
        s["supplier_contracts"] = [c for c in s["supplier_contracts"] if c["supplier_id"] not in gone]
        return s
    add("OPEN", "B_one", "후보 업체 0 (FK 연쇄 삭제)", "", one(), zero)
    add("FILL", "B_many", "쌍둥이 둘 다 가용량 60", "R3", many(),
        lambda s: (_lst(s, "SUP-002").update(available_quantity=60), _lst(s, "SUP-004").update(available_quantity=60), s)[2], True)
    add("FILL", "B_many", "쌍둥이 둘 다 가용량 40", "R8", many(),
        lambda s: (_lst(s, "SUP-002").update(available_quantity=40), _lst(s, "SUP-004").update(available_quantity=40), s)[2], True)
    add("SILENT", "B_one", "답 업체 가용량 = 100", "R6", one(), lambda s: (_lst(s, "SUP-002").update(available_quantity=100), s)[1], True)
    add("SILENT", "B_one", "답 업체 리드타임 3→10", "R4", one(), lambda s: (_lst(s, "SUP-002").update(lead_time_days=10), s)[1])
    add("SILENT", "B_one", "답 업체 계약 만료일 2025-12-31 (active 그대로)", "", one(),
        lambda s: (_con(s, "SUP-002").update(end_date="2025-12-31"), s)[1], False, "실행 시각 패치 없음")
    add("SILENT", "B_one", "답 업체 제한 문구: 200캔 이상", "R7", one(),
        lambda s: (_con(s, "SUP-002").update(restrictions="Orders accepted in quantities of 200 cans or more."), s)[1])
    add("SILENT", "B_one", "재고 450", "R5", one(),
        lambda s: (next(i for i in s["inventory_items"] if i["product_id"] == "PROD-001").update(quantity_on_hand=450), s)[1], True)

    def pending(s):
        s["purchase_orders"].append({"order_id": "PO-00001", "product_id": "PROD-001", "supplier_id": "SUP-002",
                                     "quantity": 100, "status": "pending", "created_at": "2026-05-27T09:00:00Z"})
        s["next_ids"] = {"order_id": 2}
        return s
    add("SILENT", "B_one", "지난 실행의 미입고 발주 100", "", one(), pending, True, "자기 커밋 읽기 패치 없음")
    return rows


def check3(st):
    S0 = d01_seed_state()
    cand = candidates(D01)
    out = []
    case_dir = aa.ROOT / "data/delegations/D01/states/case"
    for r in [f"R{i}" for i in range(1, 9)]:
        edit = json.loads((case_dir / f"{r}.json").read_text())
        j = judge(D01, st, S0, edit, None, cand)
        out.append({"what": f"CASE {r}", "rules": j["rules"], "rules_eq": j["rules_eq"], "replay": j["replay"],
                    "reach": j["reach"], "note": ""})
    for i, (region, bname, desc, case, base, edit, qc, note) in enumerate(alloc_rows(), 1):
        j = judge(D01, st, base, edit, "경계(언급 int)" if qc else None, cand)
        jb = judge(D01, st, S0, base, None, cand) if bname == "B_many" else None
        out.append({"what": f"할당 {i:02d} {region} {bname}: {desc}" + (f" ({case})" if case else ""),
                    "rules": j["rules"] + ([f"[기준 B_many] {x}" for x in jb["rules"]] if jb else []),
                    "rules_eq": j["rules_eq"], "replay": j["replay"], "reach": j["reach"], "note": note})
    return out


def main():
    st = semtypes()
    rows2, cand = check2(st)
    rows3 = check3(st)
    (OUT / "check2.json").write_text(json.dumps(rows2, ensure_ascii=False, indent=1, default=str))
    (OUT / "check3.json").write_text(json.dumps(rows3, ensure_ascii=False, indent=1, default=str))
    print("후보/딸린 컬렉션:", {CFG[e]["label"]: (sorted(a), sorted(b)) for e, (a, b) in cand.items()})
    print("\n## 검사 2")
    print("| 판 | # | 바뀐 것 | 기각 규칙 | I= 변형 | 재생 | 조회 | 무의미 목록 | §10 범위 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows2:
        reach = "—" if not r["reach"] or all(x is None for x in r["reach"]) else \
            ("○" if all(x for x in r["reach"] if x is not None) else "✗")
        scope = "" if r["scope"] is None else ", ".join(sorted(set(r["scope"].values())))
        print(f"| {r['env']} | {r['id']} | {r['change'][:70]} | {'; '.join(r['rules']) or '통과'} | "
              f"{'; '.join(r['rules_eq']) if r['rules_eq'] else ''} | {'○' if not r['replay'] else r['replay']} | {reach} | "
              f"{r['nonsense'] or (('범위: ' + r['scope_only']) if r['scope_only'] else '')} | {scope} |")
    for lab in ("D01", "항공"):
        rs = [r for r in rows2 if r["env"] == lab]
        ns = [r for r in rs if r["nonsense"]]
        caught = [r["id"] for r in ns if r["rules"]]
        missed = [r["id"] for r in ns if not r["rules"]]
        false = [r["id"] for r in rs if r["rules"] and not r["nonsense"]]
        print(f"\n{lab}: 편집 {len(rs)}, 무의미 {len(ns)} 중 기각 {len(caught)} {caught}, 놓침 {missed}, "
              f"무의미 목록 밖 기각 {len(false)} {false}")
    print("\n## 검사 3")
    print("| 상태 | 기각 규칙 | I= 변형 | 재생 | 조회 | 비고 |")
    print("|---|---|---|---|---|---|")
    for r in rows3:
        reach = "—" if not r["reach"] or all(x is None for x in r["reach"]) else \
            ("○" if all(x for x in r["reach"] if x is not None) else "✗ " + str(r["reach"]))
        print(f"| {r['what']} | {'; '.join(r['rules']) or '통과'} | {'; '.join(r['rules_eq'])} | "
              f"{'○' if not r['replay'] else r['replay']} | {reach} | {r['note']} |")
    bad = [r["what"] for r in rows3 if r["rules"] or r["replay"]]
    print("\n검사 3 판정:", "통과" if not bad else f"반증 — {bad}")


if __name__ == "__main__":
    main()
