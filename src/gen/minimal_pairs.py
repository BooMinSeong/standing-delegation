"""생성기 v0 = 기계 v2 (D-035 3, Plan.md §4.3, docs/DATA-GEN.md §6).

입력은 셋뿐이다: 위임문 q(문자열), 환경 초기 상태(JSON), 스키마(schema.py 경로. 필드 순서·타입만 읽는다).
숨은 규칙 R, 규칙 유형, 섭동표를 입력받지 않는다. "이 위임이 그 필드를 읽을 것인가"를 판단하지 않는다.

절차
  A. 닻: 상태의 문자열 값 중 q에 그대로 나타나는 것(ID, 도시명, 날짜)을 가진 레코드.
  B. 도달: 닻 레코드에서 ID꼴 필드(*_id, *_code, *_number, 기본키) 값을 공유하는 레코드로 닫힘(양방향, 컬렉션 불문).
  C. 차원: 도달 컬렉션의 모든 필드를 스키마 순서로 열거하고, 필드 이름 토큰이 q 토큰과 어간이 같으면 "문자 언급"으로 표시.
     ID·이름·연락처 필드는 편집하지 않는다. 값 풀(같은 필드의 서로 다른 값)이 하나뿐인 문자열도 편집하지 않는다.
  D. 편집 템플릿(기준 상태에서 차원 하나만 바꾼 최소쌍):
     - bool: 뒤집기
     - int, 언급: q의 수 N 에 대한 경계 {N-1, N, N×5}
     - int, 미언급: {0, base×10}
     - float, 언급(후보 컬렉션): 동률(둘째를 첫째와 같게), 근소차(+1%)
     - float, 미언급: {×0.1, ×10}
     - 날짜(YYYY-MM-DD), 미언급: ±1년.  언급: q의 날짜 ±1일
     - 문자열, 값 풀 ≥ 2: 풀의 다른 값으로 교체. 풀 값에 수가 들어 있고 q에 수 N 이 있으면 그 수를 N, N+1 로 바꾼 판도
  E. 구조 템플릿(도달 레코드가 2개 이상인 후보 컬렉션):
     - 단독 후보(첫 레코드만 남김), 각각 부족(언급 int 전부 N-1), 합쳐도 부족(전부 N//3), 정확히 충족(첫 레코드 = N),
     - 기준 간 충돌(수치 필드 쌍: 첫 필드 오름차순에 둘째 필드 값을 오름차순/내림차순으로 재배정)
  F. 등급: tier 1 = 후보 컬렉션의 구조·필드 편집 + 닻 개체 자체 레코드의 수치·bool 편집. tier 2 = 나머지(문자열 풀 교체, 날짜, 그 외 컬렉션).
     등급은 비용 통제용 기계 규칙이고 R 을 보지 않는다. 파일럿은 tier 1 을 돌린다.
출력: 상태 JSON 들 + manifest(차원, 템플릿, 언급 여부, 바뀐 값, 등급).
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import json
import pathlib
import re
from typing import Any

ID_LIKE = re.compile(r"(_id|_code|_number|_ids)$")
SKIP_FIELD = re.compile(r"(^|_)(id|name|sku|email|phone|contact_details|created_at|timestamp|event_id)$|_name$|^name$|^contact")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
GENERIC_TOKENS = {"the", "and", "for", "from", "with", "that", "this", "only", "order", "record", "records"}


# ---------- 토큰·어간 ----------
def stem(t: str) -> str:
    t = t.lower()
    for suf in ("ility", "ities", "ing", "ed"):
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)]
    if re.search(r"(ses|xes|zes|ches|shes)$", t) and len(t) >= 6:
        return t[:-2]
    if t.endswith("s") and len(t) >= 5:
        return t[:-1]
    return t


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z][A-Za-z\-']+", text)]


def token_match(a: str, b: str) -> bool:
    sa, sb = stem(a), stem(b)
    if sa == sb:
        return True
    n = min(len(sa), len(sb))
    return n >= 5 and (sa.startswith(sb) or sb.startswith(sa))


def q_numbers(q: str) -> list[int]:
    """q 안의 단독 정수(날짜·시각·ID 안의 숫자 제외)."""
    q2 = re.sub(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|[A-Z]+-\d+|\w+_\d+", " ", q)
    return sorted({int(n) for n in re.findall(r"(?<![\w.])(\d+)(?![\w.])", q2)})


def q_number_units(q: str) -> list[tuple[int, str]]:
    """q 안의 (정수, 바로 뒤 단어). 예: '100 cans' → (100, 'cans')."""
    q2 = re.sub(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|[A-Z]+-\d+|\w+_\d+", " ", q)
    return [(int(n), u.lower()) for n, u in re.findall(r"(?<![\w.])(\d+)\s+([A-Za-z]+)", q2)]


def q_dates(q: str) -> list[str]:
    return sorted(set(re.findall(r"\d{4}-\d{2}-\d{2}", q)))


# ---------- 스키마 ----------
def schema_fields(schema_py: pathlib.Path) -> dict[str, list[tuple[str, str]]]:
    """클래스명 → [(필드, 타입문자열)] (스키마 순서)."""
    tree = ast.parse(schema_py.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            fields = []
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    fields.append((st.target.id, ast.unparse(st.annotation)))
            out[node.name] = fields
    return out


def type_of(value: Any) -> str:
    if isinstance(value, bool): return "bool"
    if isinstance(value, int): return "int"
    if isinstance(value, float): return "float"
    if isinstance(value, str):
        if DATE_RE.match(value): return "date"
        if DATETIME_RE.match(value): return "datetime"
        return "str"
    if isinstance(value, list): return "list"
    if isinstance(value, dict): return "dict"
    return "other"


# ---------- 닻·도달 ----------
def string_values(rec: dict, prefix="") -> list[tuple[str, str]]:
    out = []
    for k, v in rec.items():
        if isinstance(v, str): out.append((prefix + k, v))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, str): out.append((f"{prefix}{k}[{i}]", x))
                elif isinstance(x, dict): out += string_values(x, f"{prefix}{k}[{i}].")
        elif isinstance(v, dict):
            out += string_values(v, prefix + k + ".")
    return out


def find_anchors(q: str, state: dict) -> set[tuple[str, int]]:
    ql = q.lower()
    anchors = set()
    for col, recs in state.items():
        if not isinstance(recs, list): continue
        for i, rec in enumerate(recs):
            if not isinstance(rec, dict): continue
            for path, v in string_values(rec):
                leaf = path.split(".")[-1].split("[")[0]
                specific = ID_LIKE.search(leaf) or any(ch.isdigit() for ch in v) or " " in v.strip() or (v[:1].isupper() and len(v) >= 4)
                if len(v) >= 3 and specific and not v.islower():
                    if re.search(r"(?<![\w-])" + re.escape(v.lower()) + r"(?![\w-])", ql):
                        anchors.add((col, i)); break
    return anchors


def id_values(rec: dict) -> set[str]:
    vals = set()
    for path, v in string_values(rec):
        leaf = path.split(".")[-1].split("[")[0]
        if ID_LIKE.search(leaf) or leaf.endswith("_ids"):
            vals.add(v)
    # 기본키: 첫 필드가 *_id 인 경우
    first = next(iter(rec.items()), None)
    if first and isinstance(first[1], str) and ID_LIKE.search(first[0]): vals.add(first[1])
    return vals


def reachable(state: dict, anchors: set[tuple[str, int]]) -> set[tuple[str, int]]:
    reach = set(anchors)
    keys = {a: id_values(state[a[0]][a[1]]) for a in anchors}
    frontier = set().union(*keys.values()) if keys else set()
    seen_keys = set(frontier)
    while frontier:
        new = set()
        for col, recs in state.items():
            if not isinstance(recs, list): continue
            for i, rec in enumerate(recs):
                if (col, i) in reach or not isinstance(rec, dict): continue
                iv = id_values(rec)
                if iv & frontier:
                    reach.add((col, i)); new |= (iv - seen_keys)
        seen_keys |= new; frontier = new
    return reach


# ---------- 차원과 편집 ----------
def set_path(rec: dict, path: str, value):
    parts = re.split(r"\.(?![^\[]*\])", path)
    cur = rec
    for p in parts[:-1]:
        m = re.match(r"(\w+)\[(\d+)\]", p)
        cur = cur[m.group(1)][int(m.group(2))] if m else cur[p]
    last = parts[-1]
    m = re.match(r"(\w+)\[(\d+)\]", last)
    if m: cur[m.group(1)][int(m.group(2))] = value
    else: cur[last] = value


def get_path(rec: dict, path: str):
    parts = re.split(r"\.(?![^\[]*\])", path)
    cur = rec
    for p in parts:
        m = re.match(r"(\w+)\[(\d+)\]", p)
        cur = cur[m.group(1)][int(m.group(2))] if m else cur[p]
    return cur


def leaf_fields(rec: dict, prefix="") -> list[tuple[str, Any]]:
    """(경로, 값). list[dict] 는 한 단계 들어간다(cabins[0].fare)."""
    out = []
    for k, v in rec.items():
        if isinstance(v, dict):
            out += leaf_fields(v, f"{prefix}{k}.")
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            out += leaf_fields(v[0], f"{prefix}{k}[0].")
        else:
            out.append((prefix + k, v))
    return out


def shift_date(s: str, days=0, years=0) -> str:
    d = dt.date.fromisoformat(s[:10])
    try:
        d2 = d.replace(year=d.year + years) + dt.timedelta(days=days)
    except ValueError:
        d2 = d + dt.timedelta(days=days + 365 * years)
    return d2.isoformat() + s[10:]


class Generator:
    def __init__(self, q: str, base: dict, schema_py: pathlib.Path | None = None, example_state: dict | None = None):
        self.q = q; self.base = base
        self.qtok = [t for t in tokens(q) if t.lower() not in GENERIC_TOKENS]
        self.nums = q_numbers(q); self.dates = q_dates(q); self.num_units = q_number_units(q)
        self.schema = schema_fields(schema_py) if schema_py else {}
        self.example = example_state or {}
        self.anchors = find_anchors(q, base)
        self.reach = reachable(base, self.anchors)
        self.reach_by_col: dict[str, list[int]] = {}
        for col, i in sorted(self.reach):
            self.reach_by_col.setdefault(col, []).append(i)
        self.anchor_cols = {c for c, _ in self.anchors}
        self.dims: list[dict] = []

    # 언급 판정: 필드 이름 토큰 중 하나가 q 토큰과 어간 일치
    def mentioned(self, path: str) -> bool:
        leaf = path.split(".")[-1].split("[")[0]
        for ft in leaf.split("_"):
            if len(ft) < 3 or ft in ("id", "on", "of", "by"): continue
            if any(token_match(ft, qt) for qt in self.qtok): return True
        return False

    def pool(self, col: str, path: str) -> list:
        vals = []
        for src in (self.base, self.example):
            for rec in src.get(col, []) or []:
                try: v = get_path(rec, path)
                except (KeyError, IndexError, TypeError): continue
                if v not in vals: vals.append(v)
        return vals

    def emit(self, dim_id: str, col: str, template: str, path: str | None, mentioned: bool, tier: int, state: dict, change: str):
        if state == self.base or any(state == d["state"] for d in self.dims):  # 기준과 같거나 이미 있는 상태는 버린다
            return
        self.dims.append({"dim_id": dim_id, "collection": col, "template": template, "field": path, "mentioned": mentioned,
                          "tier": tier, "change": change, "state": state})

    def run(self) -> list[dict]:
        for col, idxs in self.reach_by_col.items():
            recs = [self.base[col][i] for i in idxs]
            is_cand = len(idxs) >= 2
            is_anchor = col in self.anchor_cols
            i0 = idxs[0]; r0 = recs[0]
            # --- 필드 편집 (첫 도달 레코드에) ---
            for path, val in leaf_fields(r0):
                leaf = path.split(".")[-1].split("[")[0]
                if SKIP_FIELD.search(leaf) or ID_LIKE.search(leaf): continue
                t = type_of(val); men = self.mentioned(path)
                tier = 1 if (is_cand or is_anchor) and t in ("bool", "int", "float") else 2
                if ("[" in path or "." in path) and not is_cand: tier = 2
                tag = f"{col}.{path}"
                if t == "bool":
                    self._edit(f"{tag}=flip", col, "뒤집기", path, men, tier, i0, not val)
                elif t == "int":
                    if men:
                        for n in self.nums:
                            for v, nm in ((n - 1, "N-1"), (n, "N"), (n * 5, "Nx5")):
                                if v != val and v >= 0: self._edit(f"{tag}={nm}", col, "경계(언급 int)", path, men, tier, i0, v)
                    elif leaf in ("year", "month", "day", "week"):
                        for v, nm in ((val - 1, "-1"), (val + 1, "+1")):
                            self._edit(f"{tag}={nm}", col, "값 갈림(달력 int ±1)", path, men, 2, i0, v)
                    else:
                        for v, nm in ((0, "0"), (val * 10, "x10")):
                            if v != val: self._edit(f"{tag}={nm}", col, "값 갈림(미언급 int)", path, men, tier, i0, v)
                elif t == "float":
                    if men and is_cand and len(recs) >= 2:
                        v1 = get_path(recs[1], path)
                        if v1 != val:
                            self._edit(f"{tag}=tie", col, "동률(언급 float)", path, men, tier, idxs[1], val)
                            self._edit(f"{tag}=near", col, "근소차(언급 float)", path, men, tier, idxs[1], round(val * 1.01, 4))
                    elif not men:
                        for v, nm in ((round(val * 0.1, 4), "x0.1"), (round(val * 10, 4), "x10")):
                            if v != val: self._edit(f"{tag}={nm}", col, "값 갈림(미언급 float)", path, men, tier, i0, v)
                elif t == "date":
                    if men and self.dates:
                        for d in self.dates:
                            for v, nm in ((shift_date(d, days=-1), "D-1"), (shift_date(d, days=1), "D+1")):
                                if v != val: self._edit(f"{tag}={nm}", col, "경계(언급 날짜)", path, men, 2, i0, v)
                    else:
                        for v, nm in ((shift_date(val, years=-1), "Y-1"), (shift_date(val, years=1), "Y+1")):
                            self._edit(f"{tag}={nm}", col, "값 갈림(미언급 날짜)", path, men, 2, i0, v)
                elif t == "str":
                    pl = [v for v in self.pool(col, path) if v != val]
                    if pl:
                        self._edit(f"{tag}=pool", col, "풀 교체(문자열)", path, men, 2, i0, pl[0])
                    # 문자열 안의 수를 q 의 수 경계로 — q 의 단위어("100 cans"의 cans)가 바로 뒤에 있는 수에만
                    for pv in self.pool(col, path):
                        hit = None
                        for n, unit in self.num_units:
                            m = re.search(r"(\d+)(\s+" + re.escape(unit) + r"\b)", pv or "", re.I)
                            if m: hit = (n, m); break
                        if hit:
                            n, m = hit
                            for v_n, nm in ((n, "N"), (n + 1, "N+1")):
                                nv = pv[: m.start(1)] + str(v_n) + pv[m.end(1):]
                                if nv != val: self._edit(f"{tag}=text{nm}", col, "문자열 속 수 경계(단위 일치)", path, men, 1 if is_cand else 2, i0, nv)
                            break
            # --- 구조 템플릿 (후보 컬렉션) ---
            if is_cand:
                st = copy.deepcopy(self.base); st[col] = [self.base[col][i0]] + [r for j, r in enumerate(self.base[col]) if j not in idxs]
                self.emit(f"{col}#single", col, "단독 후보", None, True, 1, st, f"{col}: {len(idxs)}→1 (첫 레코드만)")
                num_paths = [(p, type_of(v)) for p, v in leaf_fields(r0) if type_of(v) in ("int", "float") and not SKIP_FIELD.search(p.split(".")[-1])]
                men_int = [p for p, t in num_paths if t == "int" and self.mentioned(p)]
                for p in men_int:
                    for n in self.nums:
                        st = copy.deepcopy(self.base)
                        for i in idxs: set_path(st[col][i], p, n - 1)
                        self.emit(f"{col}.{p}#all=N-1", col, "각각 부족(전부 N-1)", p, True, 1, st, f"{p}: 전부 {n-1}")
                        st = copy.deepcopy(self.base)
                        for i in idxs: set_path(st[col][i], p, max(n // 3, 1))
                        self.emit(f"{col}.{p}#all=N/3", col, "합쳐도 부족(전부 N//3)", p, True, 1, st, f"{p}: 전부 {max(n//3,1)}")
                        if get_path(r0, p) != n:
                            st = copy.deepcopy(self.base); set_path(st[col][i0], p, n)
                            self.emit(f"{col}.{p}#first=N", col, "정확히 충족(첫 레코드 = N)", p, True, 1, st, f"{p}[{i0}]: {get_path(r0,p)}→{n}")
                mentioned_num = [p for p, _ in num_paths if self.mentioned(p)]
                for p1 in mentioned_num:
                    for p2, _ in num_paths:
                        if p2 == p1: continue
                        order = sorted(idxs, key=lambda i: get_path(self.base[col][i], p1))
                        vals2 = sorted(get_path(self.base[col][i], p2) for i in idxs)
                        for direction, vs in (("asc", vals2), ("desc", list(reversed(vals2)))):
                            st = copy.deepcopy(self.base)
                            for i, v in zip(order, vs): set_path(st[col][i], p2, v)
                            if st != self.base:
                                self.emit(f"{col}.{p1}x{p2}#{direction}", col, f"기준 간 충돌({direction})", f"{p1}×{p2}", True, 1, st,
                                          f"{p1} 오름차순에 {p2} 를 {'오름' if direction=='asc' else '내림'}차순 재배정")
        return self.dims

    def _edit(self, dim_id, col, template, path, mentioned, tier, idx, new):
        st = copy.deepcopy(self.base)
        old = get_path(st[col][idx], path)
        set_path(st[col][idx], path, new)
        self.emit(dim_id, col, template, path, mentioned, tier, st, f"{col}[{idx}].{path}: {old!r}→{new!r}")


def write(dims: list[dict], out_dir: pathlib.Path, base: dict, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "base.json").write_text(json.dumps(base, indent=1, ensure_ascii=False) + "\n")
    manifest = []
    for k, d in enumerate(dims):
        fname = f"P{k+1:02d}.json"
        (out_dir / fname).write_text(json.dumps(d["state"], indent=1, ensure_ascii=False) + "\n")
        manifest.append({"file": fname, **{kk: v for kk, v in d.items() if kk != "state"}})
    (out_dir / "manifest.json").write_text(json.dumps({"meta": meta, "dims": manifest}, indent=1, ensure_ascii=False) + "\n")


def markdown_table(dims: list[dict]) -> str:
    lines = ["| # | 컬렉션 | 템플릿 | 필드 | 언급 | tier | 바뀐 것 |", "|---|---|---|---|---|---|---|"]
    for k, d in enumerate(dims):
        lines.append(f"| P{k+1:02d} | {d['collection']} | {d['template']} | {d['field'] or '—'} | {'○' if d['mentioned'] else '✗'} | {d['tier']} | {d['change']} |")
    return "\n".join(lines)
