"""종이 검사 5·6·7 (Plan.md §7): D01에서 Q 추출, 술어별 절제, 적대적 읽기.

설계: docs/GEN-ALGO.md §13, D-040. 생성기 LLM은 aa.GEN_MODEL(잠정).
LLM 입력은 q 전문, 툴 시그니처, 상태 스키마뿐이다. R, 참조 계획, 저자 설계 상태, 손 Q는 주지 않는다.
손 Q(scripts/paper/c1_case_regions.py의 읽기 A·B·C)는 결과 대조에만 쓴다.

단계
  gen      q⁰·q⁻ 각각 체계 셋(S1 직역 / S2 열거 후 조립 / S3 적대적 읽기) × m
  gate     실행 가능, 원판 재현(q⁰), 약화(q⁻)
  ablate   q⁰ 후보의 술어마다: 구간 삭제 재작성 → 내용어·보존 검사 → 독립 세션 재추출 → Q∖P와 행동 비교
  qset     게이트 통과 후보를 배터리 위 행동으로 중복 제거 = 𝒬
  compare  𝒬 대 손 Q 읽기 A·B·C
  literal  𝒬 원소끼리 갈리는 상태를 되먹여 "둘 다 문자 그대로의 읽기인가"만 묻는다(빼지 않는다)
사용: .venv/bin/python scripts/paper/c567_q_extract.py [--m 3] [--workers 24]
LLM 원출력: data/paper-checks/c567/llm.jsonl (키 캐시. 다시 돌리면 없는 키만 부른다)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aa  # noqa: E402

OUT = aa.ROOT / "data" / "paper-checks" / "c567"
BATTERY = OUT / "battery.json"
LOG = OUT / "llm.jsonl"
D01 = aa.ROOT / "data" / "delegations" / "D01"
ENV = "store_procurement_and_inventory"
TOP = "TOP"
REF = "create_purchase_order(product_id=PROD-001,quantity=100,supplier_id=SUP-002)"
PY = str(aa.ROOT / ".venv" / "bin" / "python")

# ---- 입력 렌더링 -------------------------------------------------------------


def render_tools() -> str:
    lines = []
    for t in aa.env_class(ENV).get_tool_schemas():
        props = t["input_schema"].get("properties", {})
        req = set(t["input_schema"].get("required", []))
        args = ", ".join(f"{k}: {v.get('type', '?')}{'' if k in req else ' (optional)'}" for k, v in props.items())
        lines.append(f"- {t['name']}({args})\n  {t['description'].strip()}")
    kinds = aa.env_class(ENV).tool_kinds
    commits = sorted(k for k, v in kinds.items() if v == "commit")
    return "\n".join(lines) + f"\n\nCommit tools (calls that change the world): {', '.join(commits)}"


def render_schema() -> str:
    sch = aa.env_class(ENV).get_state_schema()["properties"]
    out = []
    for coll, spec in sch.items():
        item = spec.get("items", {})
        if item.get("type") == "object" and "properties" in item:
            fields = ", ".join(f"{k}: {v.get('type', '?')}" for k, v in item["properties"].items())
            out.append(f"- state[\"{coll}\"]: list of records — {spec.get('description', '').strip()}\n    fields: {fields}")
        else:
            out.append(f"- state[\"{coll}\"]: {spec.get('type')} — {spec.get('description', '').strip()}")
    return "\n".join(out)


FORMAT = """Write a Python module with exactly these top-level names:

TOP = "TOP"   # return this when the order excludes nothing

PREDICATES = {
    "P1": {"kind": "forbid", "span": "<exact verbatim words of the standing order>"},
    "P2": {"kind": "select", "span": "<...>"},
    ...
}

def answer(state, drop=frozenset()):
    ...

Semantics:
- `state` is a dict laid out as in STATE SCHEMA below (collection name -> list of record dicts).
- answer(state) returns the set of execution plans the standing order permits in that state, or TOP.
  A plan is everything one scheduled run commits: the string "NONE" (no commit at all), or one or more commit
  calls joined by "+". Write a commit as TOOL(arg=value,arg=value) with the arguments sorted by name, e.g.
  "some_tool(a=1,b=X-7)". Use * as a value the order leaves open.
- PREDICATES lists only the decision predicates: the conditions stated in the order that decide which plans are
  permitted. Instructions about what to look at or compare are not decision predicates unless they restrict the
  permitted plans. Do not add conditions the order does not state.
- kind "forbid": a condition that rules plans out. If it rules out every candidate, the answer is {"NONE"}.
  kind "select": a condition that picks among the remaining candidates. If its presupposition fails (nothing
  satisfies it), return TOP — the order then excludes nothing.
- span: copy the exact contiguous words of the order that state the predicate.
- drop: a set of predicate ids. answer(state, drop) must behave as if those spans were deleted from the order:
  skip exactly those predicates and keep everything else.
- Pure Python; you may import re and math. No I/O.
Return the whole module in one ```python block."""

RULES2 = """
Additional rules:
- If several candidates satisfy a select condition equally, all of them are permitted. Do not break ties with anything the order does not state.
- Return {"NONE"} only when a forbid condition rules out every candidate. When a select condition's presupposition fails, return TOP; never NONE.
- drop only removes the listed predicates. Compute the answer exactly as if their spans were absent from the text; dropping a predicate never by itself produces TOP or NONE.
- A span must be only the words that state that condition — not the surrounding request (for example not the verb that asks for the commit)."""

HEAD = "You translate a standing instruction for a tool-using agent into an executable Python program that decides which commits the instruction permits."


def body(order: str, v: int = 1) -> str:
    fmt = FORMAT + (RULES2 if v >= 2 else "")
    return (f"TOOLS\n{render_tools()}\n\nSTATE SCHEMA\n{render_schema()}\n\n{fmt}\n\n"
            f"STANDING ORDER\n<<<\n{order.strip()}\n>>>")


def prompt(scheme: str, order: str, v: int = 1, i: int = 0) -> str:
    if scheme == "S1":
        lead = "Write the program that executes this standing order literally, as its words say."
    elif scheme == "S2":
        lead = ("First enumerate every decision predicate in this standing order as a table "
                "(id | exact span | kind | what it checks in the state). Then assemble the program from exactly those predicates.")
    elif scheme == "S3":
        lead = ("Read this standing order carefully. Can any part of it be read in a different literal way from the most "
                "obvious reading — a reading a careful person could defend from the words alone? If yes, choose one such "
                "alternative reading, state which span you read differently and how, and write the program for that "
                "alternative reading. If no part can be read differently, say so and write the program for the only reading.")
    elif scheme == "S3b":
        lead = ("Read this standing order carefully. First list every span that admits more than one literal reading — a reading "
                "a careful person could defend from the words alone — and under each span list its readings, most obvious first. "
                f"Number all the non-obvious readings across the list 1, 2, 3, ... Then take non-obvious reading number {i + 1} "
                "(if there are fewer, wrap around to 1) and write the program for the order read that way; every other span keeps "
                "its most obvious reading. If no span admits another reading, say so and write the program for the only reading.")
    else:
        raise ValueError(scheme)
    return f"{lead}\n\n{body(order, v)}"


REWRITE = """Here is a standing order. Rewrite it so that the following part is removed:
«{span}»
Remove only the content of that part. Keep every other sentence and phrase as unchanged as possible, and keep the text grammatical and natural.
Output the rewritten order between <order> and </order>.

STANDING ORDER
<<<
{order}
>>>"""

LITERAL = """Here is a standing order and the records at one scheduled run. Two programs that claim to execute the order literally permit different plans in this state.

STANDING ORDER
<<<
{order}
>>>

RECORDS (JSON)
{state}

Program X permits: {ax}
Program Y permits: {ay}
(A plan is the set of commit calls one run makes; "NONE" means no commit; TOP means the order excludes nothing.)

Do not decide which one is right. For each program, answer only: is its result a literal reading of the order's words — something the words themselves support? Reply in JSON: {{"X": {{"literal": true/false, "span": "<words it rests on>"}}, "Y": {{"literal": true/false, "span": "<words it rests on>"}}}}"""

# ---- LLM 캐시 ---------------------------------------------------------------

_cache: dict[str, dict] = {}
_lock = threading.Lock()


def load_cache() -> None:
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            r = json.loads(line)
            _cache[r["key"]] = r


def call(key: str, text: str, kind: str) -> dict:
    if key in _cache:
        return _cache[key]
    t0 = time.time()
    try:
        r = aa.ask(text, system=HEAD, max_tokens=24000)
    except Exception as e:  # noqa: BLE001
        r = {"content": "", "reasoning": "", "finish": f"error: {type(e).__name__}: {e}", "usage": None}
    rec = {"key": key, "kind": kind, "prompt_sha": hashlib.sha256(text.encode()).hexdigest()[:12],
           "content": r["content"], "reasoning_chars": len(r["reasoning"]), "finish": r["finish"],
           "usage": r["usage"], "seconds": round(time.time() - t0, 1)}
    with _lock:
        _cache[key] = rec
        with LOG.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def run_calls(jobs: list[tuple[str, str, str]], workers: int) -> None:
    todo = [j for j in jobs if j[0] not in _cache]
    if not todo:
        return
    print(f"  LLM 호출 {len(todo)}건 …", flush=True)
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda j: call(*j), todo))


# ---- 실행 ------------------------------------------------------------------


def execute(code: str, drops: list[list[str]], timeout: int = 120) -> dict:
    req = json.dumps({"code": code, "battery": str(BATTERY), "drops": drops})
    try:
        p = subprocess.run([PY, str(HERE / "c567_exec.py")], input=req, capture_output=True, text=True, timeout=timeout)
        return json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"load_error": p.stderr[-300:]}
    except subprocess.TimeoutExpired:
        return {"load_error": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"load_error": f"{type(e).__name__}: {e}"}


def errors(res: dict) -> list[str]:
    return [f"{k}: {v['error']}" for k, v in res.items() if isinstance(v, dict)]


def sig(res: dict) -> str:
    return hashlib.sha256(json.dumps(res, sort_keys=True).encode()).hexdigest()[:10]


# ---- 포함(약화)과 표기 --------------------------------------------------------

_C = re.compile(r"^(\w+)\((.*)\)$")


def _commit(c: str):
    m = _C.match(c)
    return m.group(1), dict(p.split("=", 1) for p in m.group(2).split(",") if p)


def commit_match(pat: str, c: str) -> bool:
    (tp, ap), (tc, ac) = _commit(pat), _commit(c)
    return tp == tc and set(ap) == set(ac) and all(ap[k] in ("*", ac[k]) for k in ap)


def plan_match(pat: str, plan: str) -> bool:
    if pat == "NONE" or plan == "NONE":
        return pat == plan
    ps, cs = pat.split("+"), plan.split("+")
    return len(ps) == len(cs) and all(commit_match(p, c) for p, c in zip(ps, cs))


def contains(big, small) -> bool:
    """small ⊆ big. TOP은 모든 것을 담는다."""
    if big == TOP:
        return True
    if small == TOP:
        return False
    return all(any(plan_match(p, s) for p in big) for s in small)


def union(answers: list):
    if any(a == TOP for a in answers):
        return TOP
    return sorted({p for a in answers for p in a})


def short(a) -> str:
    if a == TOP:
        return "⊤"
    if isinstance(a, dict):
        return "ERR"
    out = []
    for p in a:
        if p == "NONE":
            out.append("NONE")
            continue
        parts = []
        for c in p.split("+"):
            t, ar = _commit(c)
            parts.append(f"{ar.get('supplier_id', '?')[-3:]}×{ar.get('quantity', '?')}" if t == "create_purchase_order" else c)
        out.append("+".join(parts))
    return "{" + ", ".join(out) + "}"


# ---- 손 Q (대조용) ------------------------------------------------------------


def hand_answers() -> dict[str, dict[str, object]]:
    import c1_case_regions as c1
    bat = json.loads(BATTERY.read_text())
    out = {}
    for x in "ABC":
        out[x] = {}
        for n, s in bat.items():
            a = c1.answer(s, x)
            if a == c1.TOP:
                out[x][n] = TOP
            elif any(p.startswith("tie@") for p in a):
                out[x][n] = ("TIE", sorted(a))
            else:
                plans = []
                for p in a:
                    if p == "NONE":
                        plans.append("NONE")
                        continue
                    cs = []
                    for part in p.split("+"):
                        sup, q = part.split("x")
                        cs.append(f"create_purchase_order(product_id=PROD-001,quantity={q},supplier_id={sup})")
                    plans.append("+".join(sorted(cs)))
                out[x][n] = sorted(plans)
    return out


def matches_hand(res: dict, hand: dict) -> tuple[bool, list[str]]:
    diff = []
    for n, h in hand.items():
        a = res.get(n)
        if isinstance(h, tuple):  # 합계 읽기의 동률: 배분이 유일하지 않다 → "하나가 아님"이면 일치
            ok = a == TOP or (isinstance(a, list) and len(a) > 1)
        else:
            ok = a == h
        if not ok:
            diff.append(n)
    return not diff, diff


# ---- 절제 보조 --------------------------------------------------------------

STOP = set("the a an of to for and or from that this with whose is are be its it in on at by as any all each which".split())


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+|\d+", s.lower()) if (w.isdigit() or len(w) >= 3) and w not in STOP]


def rewrite_ok(order: str, span: str, other_spans: list[str], new: str) -> tuple[bool, str]:
    o, sp, nw = norm(order), norm(span), norm(new)
    if sp not in o:
        return False, "구간이 원문에 없다"
    outside = o.replace(sp, " ", 1)
    for w in set(words(sp)):
        if re.search(rf"\b{w}\b", outside):
            continue  # 구간 밖에도 있는 말은 남아도 된다
        if re.search(rf"\b{w}\b", nw):
            return False, f"내용어 잔존: {w}"
    i0 = o.find(sp)
    for other in other_spans:
        ot = norm(other)
        j = o.find(ot)
        if j >= 0 and not (j + len(ot) <= i0 or i0 + len(sp) <= j):
            continue  # 겹치는 구간은 보존 검사에서 뺀다
        if ot not in nw:
            return False, f"다른 구간 훼손: {other[:40]}"
    return True, ""


def span_match(a: str, b: str) -> bool:
    """두 구간이 같은 술어를 가리키는가: 한쪽이 다른 쪽을 담거나 내용어 자카드 ≥ 0.6."""
    na, nb = norm(a).strip(" ."), norm(b).strip(" .")
    if na in nb or nb in na:
        return True
    wa, wb = set(words(na)), set(words(nb))
    return bool(wa | wb) and len(wa & wb) / len(wa | wb) >= 0.6


def set_criterion(preds: dict, pid: str, preds2: dict) -> tuple[bool, str]:
    """D-040 원안: 재추출 Q'의 술어 집합 = Q의 술어 집합 − P (종류까지)."""
    gone = [k for k, q in preds2.items() if span_match(q["span"], preds[pid]["span"])]
    if gone:
        return False, f"P가 남음({gone[0]})"
    used = set()
    for k, q in preds.items():
        if k == pid:
            continue
        hit = [k2 for k2, q2 in preds2.items() if k2 not in used and q2["kind"] == q["kind"] and span_match(q2["span"], q["span"])]
        if not hit:
            return False, f"다른 술어 {k} 사라짐"
        used.add(hit[0])
    extra = [k2 for k2 in preds2 if k2 not in used]
    return (not extra), (f"새 술어 {extra[0]}: {preds2[extra[0]]['span'][:40]}" if extra else "")


def parse_order(content: str) -> str | None:
    m = re.search(r"<order>(.*?)</order>", content, re.S)
    return m.group(1).strip() if m else None


# ---- 본 절차 ----------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--abl-attempts", type=int, default=2)
    ap.add_argument("--v", type=int, default=1)
    ap.add_argument("--schemes", default="S1,S2,S3")
    ap.add_argument("--m-qm", type=int, default=None)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    load_cache()
    t_start = time.time()
    orders = {"q0": (D01 / "q_plus.txt").read_text(), "qm": (D01 / "q_minus.txt").read_text()}
    bat = json.loads(BATTERY.read_text())
    V = args.v
    tag = "" if V == 1 else str(V)
    schemes = args.schemes.split(",")
    m_of = lambda qv: args.m if qv == "q0" or args.m_qm is None else args.m_qm  # noqa: E731
    report: dict = {"m": args.m, "v": V, "schemes": schemes, "battery": len(bat)}

    # 1 gen
    jobs = [(f"gen{tag}|{qv}|{sc}|{i}", prompt(sc, orders[qv], V, i), "gen")
            for qv in orders for sc in schemes for i in range(m_of(qv))]
    run_calls(jobs, args.workers)

    cands = []
    for key, _, _ in jobs:
        rec = _cache[key]
        _, qv, sc, i = key.split("|")
        code = aa.extract_block(rec["content"])
        c = {"key": key, "q": qv, "scheme": sc, "i": int(i), "finish": rec["finish"], "code": code}
        if not code:
            c["fail"] = "코드 블록 없음"
        else:
            ex = execute(code, [[]])
            if "load_error" in ex:
                c["fail"] = "적재 실패: " + ex["load_error"][:160]
            else:
                c["preds"] = ex["predicates"]
                c["res"] = ex["results"][0]
                errs = errors(c["res"])
                if errs:
                    c["fail"] = f"실행 오류 {len(errs)}/{len(bat)}: {errs[0][:120]}"
        cands.append(c)

    # 2 gates: 실행 가능 / 원판 재현(q0)
    for c in cands:
        c["g_exec"] = "fail" not in c
        if c["q"] == "q0":
            c["g_repro"] = c["g_exec"] and c["res"]["seed"] == [REF]

    # 3 ablate (q0 후보 중 실행 가능·원판 재현 통과)
    q0ok = [c for c in cands if c["q"] == "q0" and c.get("g_repro")]
    # 3a 구간별 재작성 (같은 구간은 공유)
    spans = sorted({norm(p["span"]) for c in q0ok for p in c["preds"].values()})
    span_raw = {}
    for c in q0ok:
        for p in c["preds"].values():
            span_raw.setdefault(norm(p["span"]), p["span"])
    rw_jobs = [(f"rw|{hashlib.sha256(s.encode()).hexdigest()[:10]}|{t}",
                REWRITE.format(span=span_raw[s], order=orders["q0"].strip()), "rewrite")
               for s in spans for t in range(3)]
    run_calls(rw_jobs, args.workers)

    def rewrites_for(span_n: str, others: list[str]) -> list[str]:
        good = []
        h = hashlib.sha256(span_n.encode()).hexdigest()[:10]
        for t in range(3):
            new = parse_order(_cache[f"rw|{h}|{t}"]["content"])
            if new:
                ok, why = rewrite_ok(orders["q0"], span_raw[span_n], others, new)
                if ok:
                    good.append(new)
        return good

    # 3b 독립 재추출
    abl_plan = []
    for c in q0ok:
        for pid, p in c["preds"].items():
            others = [q["span"] for k, q in c["preds"].items() if k != pid]
            rws = rewrites_for(norm(p["span"]), others)
            abl_plan.append((c, pid, rws))
    ax_jobs = []
    for c, pid, rws in abl_plan:
        if rws:
            rh = hashlib.sha256(rws[0].encode()).hexdigest()[:10]
            for a in range(args.abl_attempts):
                ax_jobs.append((f"ablx{tag}|{rh}|{a}", prompt("S1", rws[0], V), "ablate-extract"))
    run_calls(sorted(set(ax_jobs)), args.workers)

    ex_cache: dict[str, dict] = {}
    for c in q0ok:
        drops = [[pid] for pid in c["preds"]]
        ex = execute(c["code"], drops)
        c["drop_res"] = dict(zip(c["preds"], ex.get("results", [{}] * len(drops))))
    abl_rows = []
    for c, pid, rws in abl_plan:
        row = {"cand": c["key"], "pred": pid, "kind": c["preds"][pid]["kind"], "span": c["preds"][pid]["span"],
               "rewrite": rws[0] if rws else None, "pass": False, "why": "", "set_pass": False, "set_why": ""}
        if not rws:
            row["why"] = "재작성 3회 모두 내용어·보존 검사 실패"
        else:
            rh = hashlib.sha256(rws[0].encode()).hexdigest()[:10]
            target = c["drop_res"][pid]
            if errors(target):
                row["why"] = "Q∖P 실행 오류"
            for a in range(args.abl_attempts):
                code = aa.extract_block(_cache[f"ablx{tag}|{rh}|{a}"]["content"])
                if not code:
                    continue
                if code not in ex_cache:
                    ex_cache[code] = execute(code, [[]])
                e = ex_cache[code]
                if "load_error" in e:
                    continue
                if not row["set_pass"]:
                    row["set_pass"], row["set_why"] = set_criterion(c["preds"], pid, e.get("predicates", {}))
                r = e["results"][0]
                d = [n for n in bat if r.get(n) != target.get(n)]
                if not d:
                    row["pass"], row["why"], row["attempt"] = True, "", a
                    break
                row["why"] = f"재추출 {a}: {len(d)}상태 불일치 (예 {d[0]}: Q'={short(r.get(d[0]))} Q∖P={short(target.get(d[0]))})"
        abl_rows.append(row)
    for c in q0ok:
        rows = [r for r in abl_rows if r["cand"] == c["key"]]
        c["g_ablate"] = bool(rows) and all(r["pass"] for r in rows)
        c["g_ablate_set"] = bool(rows) and all(r["set_pass"] for r in rows)
        c["ablate_pass"] = f"{sum(r['pass'] for r in rows)}/{len(rows)}"
        c["ablate_set_pass"] = f"{sum(r['set_pass'] for r in rows)}/{len(rows)}"

    # 4 𝒬 (q0): 실행 가능 ∧ 원판 재현 ∧ 절제. 행동으로 중복 제거
    def qset(members):
        cls: dict[str, list] = {}
        for c in members:
            cls.setdefault(sig(c["res"]), []).append(c)
        return cls
    q0_full = [c for c in q0ok if c["g_ablate"]]
    Q0 = qset(q0_full)
    Q0_set = qset([c for c in q0ok if c["g_ablate_set"]])
    Q0_noabl = qset(q0ok)  # 절제 게이트 전 (민감도)

    # 5 약화 (q⁻): answer_q⁰(s) ⊆ answer_q⁻(s). 𝒬 합집합 기준과 쌍별
    qm_exec = [c for c in cands if c["q"] == "qm" and c["g_exec"]]
    ref_sets = [grp[0]["res"] for grp in (Q0 or Q0_noabl).values()]
    for c in qm_exec:
        bad = [n for n in bat if not contains(c["res"][n], union([r[n] for r in ref_sets]))]
        c["g_weaken"] = not bad
        c["weaken_bad"] = bad[:5]
        c["weaken_pairs"] = sum(all(contains(c["res"][n], r[n]) for n in bat) for r in ref_sets)
    Qm = qset([c for c in qm_exec if c["g_weaken"]])
    # 민감도: 선택 술어의 전제 실패를 답 전체가 아니라 그 술어에 국소화한 ⊤ (그 술어만 빠진 답)
    local_refs = []
    for grp in (Q0 or Q0_noabl).values():
        c0 = grp[0]
        sel = [k for k, q in c0["preds"].items() if q["kind"] == "select"]
        dr = execute(c0["code"], [sel]).get("results", [{}])[0] if sel else c0["res"]
        local_refs.append({n: (dr.get(n) if c0["res"][n] == TOP else c0["res"][n]) for n in bat})
    for c in qm_exec:
        badl = [n for n in bat if not contains(c["res"][n], union([r[n] for r in local_refs]))]
        c["g_weaken_local"] = not badl
        c["weaken_local_bad"] = badl[:5]

    # 6 손 Q 대조
    hand = hand_answers()
    comp = {}
    for x in "ABC":
        comp[x] = []
        for s, grp in Q0_noabl.items():
            ok, diff = matches_hand(grp[0]["res"], hand[x])
            comp[x].append({"class": s, "match": ok, "n_diff": len(diff), "diff": diff[:6], "in_Q": s in Q0})

    # 7 literal 되먹임: 𝒬(절제 전 포함) 원소 쌍이 갈리는 상태 하나씩
    classes = list(Q0_noabl.items())
    lit_jobs, lit_meta = [], []
    for i in range(len(classes)):
        for j in range(i + 1, len(classes)):
            ri, rj = classes[i][1][0]["res"], classes[j][1][0]["res"]
            d = [n for n in bat if ri[n] != rj[n]]
            if not d:
                continue
            n = d[0]
            k = f"lit{tag}|{classes[i][0]}|{classes[j][0]}|{n}"
            txt = LITERAL.format(order=orders["q0"].strip(), state=json.dumps(bat[n], ensure_ascii=False),
                                 ax=json.dumps(ri[n]), ay=json.dumps(rj[n]))
            lit_jobs.append((k, txt, "literal"))
            lit_meta.append((k, classes[i][0], classes[j][0], n, len(d)))
    run_calls(lit_jobs, args.workers)
    lits = []
    for k, a, b, n, nd in lit_meta:
        m = re.search(r"\{.*\}", _cache[k]["content"], re.S)
        try:
            j = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            j = {}
        lits.append({"X": a, "Y": b, "state": n, "n_diff_states": nd,
                     "X_literal": (j.get("X") or {}).get("literal"), "Y_literal": (j.get("Y") or {}).get("literal"),
                     "X_span": (j.get("X") or {}).get("span"), "Y_span": (j.get("Y") or {}).get("span")})

    # 저장·요약
    usage = [r["usage"] for r in _cache.values() if r.get("usage")]
    report.update({
        "seconds_this_run": round(time.time() - t_start), "llm_calls": len(_cache),
        "tokens": {"prompt": sum(u["prompt_tokens"] for u in usage), "completion": sum(u["completion_tokens"] for u in usage)},
        "cands": [{k: v for k, v in c.items() if k not in ("res", "drop_res", "code")} for c in cands],
        "ablation": abl_rows,
        "Q0": {s: [c["key"] for c in g] for s, g in Q0.items()},
        "Q0_before_ablation": {s: [c["key"] for c in g] for s, g in Q0_noabl.items()},
        "Q0_set_ablation": {s: [c["key"] for c in g] for s, g in Q0_set.items()},
        "Qm": {s: [c["key"] for c in g] for s, g in Qm.items()},
        "hand_compare": comp, "literal": lits,
    })
    (OUT / f"report_v{V}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    (OUT / f"codes_v{V}.json").write_text(json.dumps({c["key"]: c["code"] for c in cands if c.get("code")}, ensure_ascii=False, indent=1))
    (OUT / f"answers_v{V}.json").write_text(json.dumps({c["key"]: c.get("res") for c in cands}, ensure_ascii=False))
    print_summary(report, cands, Q0, Q0_noabl, Qm, comp, abl_rows, lits, bat)


def print_summary(report, cands, Q0, Q0_noabl, Qm, comp, abl_rows, lits, bat) -> None:
    print(f"\n배터리 {len(bat)}상태, m={report['m']}, LLM 호출 누적 {report['llm_calls']}, 토큰 {report['tokens']}")
    print("\n| q | 체계 | 후보 | 실행 가능 | 원판 재현 | 절제(행동) | 절제(집합) | 약화(전역 ⊤) | 약화(국소 ⊤) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for qv in ("q0", "qm"):
        for sc in report["schemes"]:
            cs = [c for c in cands if c["q"] == qv and c["scheme"] == sc]
            print(f"| {qv} | {sc} | {len(cs)} | {sum(c['g_exec'] for c in cs)} | "
                  f"{sum(bool(c.get('g_repro')) for c in cs) if qv == 'q0' else '—'} | "
                  f"{sum(bool(c.get('g_ablate')) for c in cs) if qv == 'q0' else '—'} | "
                  f"{sum(bool(c.get('g_ablate_set')) for c in cs) if qv == 'q0' else '—'} | "
                  f"{sum(bool(c.get('g_weaken')) for c in cs) if qv == 'qm' else '—'} | "
                  f"{sum(bool(c.get('g_weaken_local')) for c in cs) if qv == 'qm' else '—'} |")
    print(f"\n|𝒬 q⁰| (게이트 넷, 행동 절제) = {len(Q0)}, (집합 절제) = {len(report['Q0_set_ablation'])}, 절제 전 = {len(Q0_noabl)}, |𝒬 q⁻| = {len(Qm)}")
    for name, Q in (("𝒬 q⁰ 절제 전", Q0_noabl), ("𝒬 q⁻", Qm)):
        print(f"\n{name}: 행동 클래스 → 체계별 기여")
        for s, g in Q.items():
            by = {}
            for c in g:
                by[c["scheme"]] = by.get(c["scheme"], 0) + 1
            r = g[0]["res"]
            probe = ["seed", "V01_all_short_sum_ok", "V02_all_short_sum_short", "V03_exact_sum_unique_split",
                     "V04_answer_min_order_200", "V06_tie_among_fulfillers", "V07_all_inactive"]
            print(f"  {s} {by} " + " | ".join(f"{p.split('_')[0]}={short(r[p])}" for p in probe))
    print("\n손 Q 대조 (절제 전 𝒬 클래스 중 배터리 전부 일치하는 것)")
    for x in "ABC":
        hits = [r for r in comp[x] if r["match"]]
        best = min(comp[x], key=lambda r: r["n_diff"]) if comp[x] else None
        print(f"  읽기 {x}: 일치 클래스 {len(hits)} {[h['class'] for h in hits]}"
              + (f" / 최소 불일치 {best['n_diff']} {best['diff']}" if best and not hits else ""))
    print("\n절제 실패")
    for r in abl_rows:
        if not r["pass"]:
            print(f"  {r['cand']} {r['pred']} [{r['kind']}] «{r['span'][:50]}» — 행동: {r['why'][:140]} / 집합: {'통과' if r['set_pass'] else r['set_why'][:60]}")
    print(f"\nliteral 되먹임 {len(lits)}쌍: 둘 다 literal={sum(bool(l['X_literal']) and bool(l['Y_literal']) for l in lits)}")


if __name__ == "__main__":
    main()
