"""LLM 슬롯 넷 (D-043, Plan §3·§4.2). 생성기는 aa.GEN_MODEL(Qwen3.8, 평가 대상과 같은 모델).

LLM은 산출을 내고, 빼는 것은 실행 게이트가 한다(D-040 원칙 1·3). 묻는 방식은 슬롯마다 둘이다(원칙 4).

C tags      기록 필드(시각 도장·로그·카운터) 태그. 환경마다 한 번.
            되받기: 씨앗의 commit 호출을 실행해(같은 호출 두 번) 태그대로 변하는가.
              stamp   새로 나타난 값이 날짜시각 형식이고 호출 인자에 없다
              log     두 호출 모두에서 목록이 앞부분을 그대로 둔 채 늘어난다
              counter 두 호출 모두에서 정수가 는다
            두 체계가 같은 (경로, 종류)를 내고 실행이 확인한 태그만 쓴다. 갈리거나 확인되지 않으면 도메인으로 남긴다
            (D-040 원칙 3: 갈리면 넓은 쪽. 도메인 비교에 남기는 것이 D-041의 기본이다).
B reach     씨앗 필터 4. 닻과 이어진 레코드를 읽는 조회 호출열.
            되받기: 초기 상태에서 실행해 성공하고, 결과에 닻 ID가 있고, 참조 계획의 조회 결과에 없는 값이 있다.
A standing  씨앗 필터 1. 씨앗 지시문을 상시 지시로 고쳐 쓴다.
            되받기 ① 고친 q에서 뽑은 Q(검사 5의 직역 체계, 규칙 v2)가 씨앗 상태에서 참조 커밋의 ID 인자를 낸다
                   ② 참조 commit이 바꾸는 기존 레코드의 ID가 고친 q에 글자로 없다
                   ③ Q의 술어 구간마다 내용어의 절반 초과가 원 지시문에 있다(지어낸 조건 없음)
D identity  정체성 필드. 되받기: 코퍼스 레코드의 그 값을 조회 툴에 넣으면 그 레코드의 키가 결과에 있다.
            두 체계가 같이 낸 필드만 쓴다. 정체성 필드는 편집을 기각하므로 갈리면 적게 잡는 쪽이 넓은 쪽이다.
판정 기준·표본 수·순서는 docs/PREREG-SLOTS.md.
LLM 원출력: data/paper-checks/slots/llm.jsonl (키 캐시)
"""
from __future__ import annotations

import ast
import collections
import contextlib
import copy
import hashlib
import io
import json
import pathlib
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import aa  # noqa: E402
import c23_profile as P  # noqa: E402
import c48_exec as X  # noqa: E402
from c567_q_extract import FORMAT, HEAD, RULES2, words  # noqa: E402

OUT = aa.ROOT / "data" / "paper-checks" / "slots"
LOG = OUT / "llm.jsonl"
PY = str(aa.ROOT / ".venv" / "bin" / "python")
EXEC = str(aa.ROOT / "scripts" / "paper" / "c567_exec.py")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
ID_FIELD = re.compile(r"(^id$|_id$|Id$|_code$|_number$|^sku$|_sku$)")

# ---- LLM 캐시 -----------------------------------------------------------------
_cache: dict[str, dict] = {}
_lock = threading.Lock()


def load_cache() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            r = json.loads(line)
            _cache[r["key"]] = r


def call(key: str, text: str, system: str | None = None) -> dict:
    if key in _cache:
        return _cache[key]
    t0 = time.time()
    try:
        r = aa.ask(text, system=system, max_tokens=24000)
    except Exception as e:  # noqa: BLE001
        r = {"content": "", "finish": f"error: {type(e).__name__}: {e}", "usage": None}
    rec = {"key": key, "model": aa.GEN_MODEL, "prompt_sha": hashlib.sha256(text.encode()).hexdigest()[:12],
           "content": r["content"], "finish": r["finish"], "usage": r["usage"], "seconds": round(time.time() - t0, 1)}
    with _lock:
        _cache[key] = rec
        with LOG.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def parse_json(text: str):
    return X.parse_json(text)


# ---- 렌더링 -------------------------------------------------------------------


def render_tools(cls, kinds: set[str] | None = None) -> str:
    lines = []
    for t in cls.get_tool_schemas():
        k = cls.tool_kinds.get(t["name"])
        if kinds and k not in kinds:
            continue
        props = t["input_schema"].get("properties", {})
        req = set(t["input_schema"].get("required", []))
        args = ", ".join(f"{a}: {v.get('type', '?')}{'' if a in req else ' (optional)'}" for a, v in props.items())
        lines.append(f"- {t['name']}({args}) [{k}]\n  {' '.join((t['description'] or '').split())}")
    return "\n".join(lines)


def render_schema(envs: list[str]) -> str:
    out = []
    for e in envs:
        for coll, spec in aa.env_class(e).get_state_schema()["properties"].items():
            key = f"{e}:{coll}"
            item = spec.get("items", {})
            desc = " ".join((spec.get("description") or "").split())
            if item.get("type") == "object" and "properties" in item:
                fields = ", ".join(f"{k}: {v.get('type', '?')}" for k, v in item["properties"].items())
                out.append(f"- state[\"{key}\"]: list of records — {desc}\n    fields: {fields}")
            else:
                out.append(f"- state[\"{key}\"]: {spec.get('type')} — {desc}")
    return "\n".join(out)


def call_text(tool: str, args: dict) -> str:
    return f"{tool}({', '.join(f'{k}={v!r}' for k, v in sorted(args.items()))})"


# ---- 상태 보조 -------------------------------------------------------------------


def leaves(x, key=None):
    """(키, 스칼라 값)."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from leaves(v, k)
    elif isinstance(x, list):
        for v in x:
            yield from leaves(v, key)
    else:
        yield key, x


def id_values(state) -> set[str]:
    out: set[str] = set()
    for k, v in leaves(state):
        if k is not None and isinstance(v, (str, int)) and not isinstance(v, bool) and ID_FIELD.search(str(k)) and len(str(v)) >= 2:
            out.add(str(v))

    def keyed(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(k, str) and re.search(r"\d", k) and len(k) >= 3 and isinstance(v, dict):
                    out.add(k)
                keyed(v)
        elif isinstance(x, list):
            for v in x:
                keyed(v)
    keyed(state)
    return out


def seed_state(s: dict) -> tuple[type, dict, dict]:
    cls, init = aa.composite(aa.seed_envs(s)), aa.seed_init(s)
    with contextlib.redirect_stdout(io.StringIO()):
        state = aa.snapshot(cls(json.loads(json.dumps(init))))
    return cls, init, state


# ==== C 기록 필드 태그 ================================================================

TAGS_LEAD = {
    "C1": "List the record-keeping fields of this environment.",
    "C2": ("Go through the commit tools one by one. For every state field a tool writes, decide whether the value it writes "
           "comes from the call's arguments or from domain logic, or is record-keeping. Then list the record-keeping fields."),
}
TAGS_BODY = """Some fields hold record-keeping that the system writes on each call rather than facts of the domain:
- stamp: a date-time the system writes when a call happens (for example updated_at, created_at, timestamp).
- log: a list the system appends an entry to on each call (an audit log, or a history list inside a record).
- counter: an integer the system increments to mint new IDs.
Anything you do not list is treated as domain data.
Write each path as "<state key>" for a whole top-level entry, or "<state key>.<field>" for a field of the records inside it.

Answer with one JSON object in a ```json block:
{{"fields": [{{"path": "...", "kind": "stamp" | "log" | "counter"}}]}}

STATE KEYS
{keys}

DATA CLASSES (schema.py)
{schema}

COMMIT TOOLS (source)
{source}"""


def commit_source(env: str) -> str:
    src, tree = aa.env_source(env), P._tree(env)
    commits = [k for k, v in aa.env_class(env).tool_kinds.items() if v == "commit"]
    module_funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    parts, helpers = [], set()
    for name in commits:
        f = P._func(tree, name)
        if f is None:
            continue
        parts.append(ast.get_source_segment(src, f))
        for m in ast.walk(f):
            if isinstance(m, ast.Attribute) and isinstance(m.value, ast.Name) and m.value.id == "self":
                helpers.add(m.attr)
            if isinstance(m, ast.Call) and isinstance(m.func, ast.Name) and m.func.id in module_funcs:
                helpers.add(m.func.id)
    for h in sorted(helpers - set(commits)):
        f = P._func(tree, h)
        if f is not None:
            parts.append(ast.get_source_segment(src, f))
    return "\n\n".join(p for p in parts if p)


def tags_prompt(env: str, scheme: str) -> str:
    keys = "\n".join(f"- {k}" for k in aa.env_class(env).get_state_schema()["properties"])
    schema = (aa.AD / "environments" / env / "schema.py").read_text()
    return TAGS_LEAD[scheme] + "\n\n" + TAGS_BODY.format(keys=keys, schema=schema, source=commit_source(env))


def commit_instances(env: str) -> list[tuple[dict, list, str, dict]]:
    """씨앗 131의 참조 계획에서 이 환경의 commit 호출과 그 앞 호출열."""
    tools = {k for k, v in aa.env_class(env).tool_kinds.items() if v == "commit"}
    out = []
    for s in aa.seeds():
        if env not in aa.seed_envs(s):
            continue
        nodes = s["execution_dag"]["nodes"]
        calls = [(aa.dag_tool(n), n.get("params") or {}) for n in nodes]
        for i, n in enumerate(nodes):
            if n.get("kind") == "commit" and aa.dag_tool(n) in tools:
                out.append((s, calls[:i], aa.dag_tool(n), n.get("params") or {}))
    return out


def observe(inst) -> dict:
    s, prefix, tool, args = inst
    cls, init = aa.composite(aa.seed_envs(s)), aa.seed_init(s)
    with contextlib.redirect_stdout(io.StringIO()):
        env = X.replay(cls, init, prefix)
        s0 = aa.snapshot(env)
        ok1 = X.call(env, tool, args)[0]
        s1 = aa.snapshot(env)
        ok2 = X.call(env, tool, args)[0]
        s2 = aa.snapshot(env)
    return {"s0": s0, "s1": s1, "s2": s2, "ok1": ok1, "ok2": ok2, "argv": {str(v) for v in X.values(args)}}


def _field_values(x, field):
    if isinstance(x, dict):
        for k, v in x.items():
            if k == field and not isinstance(v, (dict, list)):
                yield v
            else:
                yield from _field_values(v, field)
    elif isinstance(x, list):
        for v in x:
            yield from _field_values(v, field)


def _grows(a, b, field) -> bool:
    """a → b에서 목록(field가 None이면 a 자체, 아니면 레코드의 field)이 앞부분을 둔 채 늘었는가."""
    if field is None:
        return isinstance(a, list) and isinstance(b, list) and len(b) > len(a) and b[:len(a)] == a
    if isinstance(a, dict) and isinstance(b, dict):
        if field in a and field in b and _grows(a[field], b[field], None):
            return True
        return any(_grows(a[k], b[k], field) for k in set(a) & set(b))
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return any(_grows(x, y, field) for x, y in zip(a, b))
    return False


def _counts_up(a, b, field) -> bool:
    if field is None:
        if isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool):
            return b > a
        if isinstance(a, dict) and isinstance(b, dict):
            return any(_counts_up(a[k], b[k], None) for k in set(a) & set(b))
        return False
    if isinstance(a, dict) and isinstance(b, dict):
        if field in a and field in b and _counts_up(a[field], b[field], None):
            return True
        return any(_counts_up(a[k], b[k], field) for k in set(a) & set(b))
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return any(_counts_up(x, y, field) for x, y in zip(a, b))
    return False


def verify_tag(env: str, path: str, kind: str, obs: list[dict]) -> bool:
    top, _, field = path.partition(".")
    key, field = f"{env}:{top}", (field or None)
    for o in obs:
        if not o["ok1"]:
            continue
        a, b, c = o["s0"].get(key), o["s1"].get(key), o["s2"].get(key)
        if a is None and b is None:
            continue
        if kind == "stamp":
            if field is None:
                if a != b and isinstance(b, str) and ISO.match(b) and b not in o["argv"]:
                    return True
            else:
                new = collections.Counter(map(str, _field_values(b, field))) - collections.Counter(map(str, _field_values(a, field)))
                if any(ISO.match(v) and v not in o["argv"] for v in new):
                    return True
        elif kind == "log":
            if o["ok2"] and _grows(a, b, field) and _grows(b, c, field):
                return True
        elif kind == "counter":
            if o["ok2"] and _counts_up(a, b, field) and _counts_up(b, c, field):
                return True
    return False


def record_tags(env: str) -> dict:
    """환경 하나의 기록 필드 태그. 두 체계의 합집합을 실행으로 되받는다."""
    props = {}
    for sch in ("C1", "C2"):
        r = call(f"tags|{env}|{sch}", tags_prompt(env, sch))
        obj = parse_json(r["content"]) or {}
        for f in obj.get("fields") or []:
            p, k = str(f.get("path", "")).strip().split(":")[-1], f.get("kind")
            if p and k in ("stamp", "log", "counter") and sch not in props.get((p, k), []):
                props.setdefault((p, k), []).append(sch)
    obs = [observe(i) for i in commit_instances(env)]
    kept, dropped = [], []
    for (p, k), by in sorted(props.items()):
        agree, conf = len(by) == 2, verify_tag(env, p, k, obs)
        (kept if agree and conf else dropped).append({"path": p, "kind": k, "by": by, "agree": agree, "confirmed": conf})
    return {"env": env, "n_instances": len(obs), "kept": kept, "dropped": dropped}


def tag_index(tag_rows: list[dict]) -> dict[str, list]:
    """{"<env>:<top>": [field | None, ...]} — c48_exec.TAGS 형식."""
    out: dict[str, list] = {}
    for row in tag_rows:
        for t in row["kept"]:
            top, _, field = t["path"].partition(".")
            out.setdefault(f"{row['env']}:{top}", []).append(field or None)
    return out


# ==== B 도달 조회 제안 ================================================================

REACH_LEAD = {
    "B1": ("Propose read-only calls that read records connected to the records this task acts on and that the "
           "reference run did not read."),
    "B2": ("First list the collections in STATE SCHEMA that are linked by an identifier to the records this task acts on, "
           "and mark which of them the reference run read. Then, for each linked collection it did not read, give a "
           "read-only call that reads its records."),
}
REACH_BODY = """Use only lookup or verify tools from TOOLS, with concrete argument values taken from the reference run below.

Answer with one JSON object in a ```json block:
{{"calls": [{{"tool": "...", "args": {{...}}}}]}}

TASK
<<<
{instruction}
>>>

REFERENCE RUN (calls and results)
{ref}

TOOLS
{tools}

STATE SCHEMA (state keys are "<environment>:<collection>")
{schema}"""
REACH_FEEDBACK = """

Your calls were executed on the records. None of them passed:
{why}
Try again."""


def reference_run(cls, init, nodes) -> tuple[list[dict], str]:
    with contextlib.redirect_stdout(io.StringIO()):
        _, log = X.run_nodes(cls, init, nodes)
    rows, parts = [], []
    for n, x in zip(nodes, log):
        res = json.dumps(x["result"], ensure_ascii=False, default=str)
        rows.append({"tool": x["tool"], "kind": x["kind"], "args": n.get("params") or {}, "ok": x["ok"], "result": x["result"]})
        parts.append(f"{call_text(x['tool'], n.get('params') or {})} [{x['kind']}]\n  -> {res[:1500]}")
    return rows, "\n".join(parts)[:9000]


def anchor_ids(state, commits: list[dict], ids: set[str]) -> set[str]:
    """참조 commit의 ID 인자와, 그 ID를 담은 레코드의 다른 ID 필드(한 걸음)."""
    a = {str(v) for n in commits for v in (n.get("params") or {}).values() if str(v) in ids}
    more: set[str] = set()

    def rec(x):
        if isinstance(x, dict):
            own = {str(v) for k, v in x.items() if ID_FIELD.search(str(k)) and isinstance(v, (str, int)) and not isinstance(v, bool)}
            if own & a:
                more.update(own)
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)
    rec(state)
    return {i for i in a | more if len(i) >= 2}


def check_reach(cls, init, tool: str, args: dict, anchors: set[str], ref_text: str) -> dict:
    kinds = cls.tool_kinds
    if kinds.get(tool) not in ("lookup", "verify"):
        return {"ok": False, "why": f"{tool}: not a lookup/verify tool"}
    args = {k: (str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in (args or {}).items()}
    with contextlib.redirect_stdout(io.StringIO()):
        env = cls(json.loads(json.dumps(init)))
        ok, res, err = X.call(env, tool, args)
    if not ok:
        return {"ok": False, "why": f"{call_text(tool, args)}: error {err}"}
    txt = json.dumps(res, ensure_ascii=False, default=str)
    linked = sorted(i for i in anchors if i in txt)
    if not linked:
        return {"ok": False, "why": f"{call_text(tool, args)}: result does not mention the records the task acts on"}
    new = sorted({str(k) for k, v in leaves(res) if k is not None and not ID_FIELD.search(str(k)) and v is not None
                  and not isinstance(v, bool) and len(str(v)) >= 2 and json.dumps(v, ensure_ascii=False) not in ref_text
                  and str(v) not in ref_text})
    if not new:
        return {"ok": False, "why": f"{call_text(tool, args)}: everything it returned was already in the reference run"}
    return {"ok": True, "linked": linked[:5], "new_fields": new}


def reach(s: dict) -> dict:
    envs = aa.seed_envs(s)
    cls, init, state = seed_state(s)
    nodes = s["execution_dag"]["nodes"]
    commits = [n for n in nodes if n.get("kind") == "commit"]
    rows, ref = reference_run(cls, init, nodes)
    ref_text = json.dumps([r["result"] for r in rows if r["kind"] != "commit"], ensure_ascii=False, default=str)
    anchors = anchor_ids(state, commits, id_values(state))
    body = REACH_BODY.format(instruction=s["instruction"].strip(), ref=ref, tools=render_tools(cls, {"lookup", "verify"}),
                             schema=render_schema(envs))
    out = {"pair_id": s["pair_id"], "anchors": sorted(anchors)[:10], "attempts": []}
    for sch in ("B1", "B2"):
        feedback = ""
        for rnd in range(2):
            r = call(f"reach|{s['pair_id']}|{sch}|{rnd}", REACH_LEAD[sch] + "\n\n" + body + feedback)
            calls = (parse_json(r["content"]) or {}).get("calls") or []
            checks = [dict(check_reach(cls, init, c.get("tool"), c.get("args"), anchors, ref_text), call=c) for c in calls[:12]]
            out["attempts"].append({"scheme": sch, "round": rnd, "n_calls": len(calls), "checks": checks, "finish": r["finish"]})
            if any(c["ok"] for c in checks):
                break
            feedback = REACH_FEEDBACK.format(why="\n".join(c["why"] for c in checks) or "(no calls parsed)")
    passed = [c for a in out["attempts"] for c in a["checks"] if c["ok"]]
    out["F4"] = bool(passed)
    out["new_fields"] = sorted({f for c in passed for f in c["new_fields"]})
    return out


# ==== A 상시 지시 재작성 ===============================================================

STANDING_LEAD = {
    "A1": "Rewrite the instruction as such a standing order.",
    "A2": ("First make a table of every record, date or event the instruction refers to: how the user identified it (by its "
           "name or number, or by a property the user stated) and that property. Then write the standing order, referring "
           "to each of them only by the properties the user stated."),
}
STANDING_BODY = """A user gave an assistant the one-off instruction below. The assistant works only through the tools listed.
We want to run it as a standing order instead: the assistant executes it on a schedule, each run against whatever the records are at that time, with nobody to ask.

Rules:
- Keep every condition, criterion, quantity and limit the user stated, in the user's words where possible.
- Where the instruction names a specific record, date or event that the assistant was meant to pick out by some property the user also stated, refer to it by that property instead of by its name or number.
- Identifiers of the account or entity on whose behalf the order runs (the user's own account, profile, farm, site) may stay.
- Do not add conditions, thresholds or properties the user did not state.

Answer with one JSON object in a ```json block:
{{"order": "<the standing order>"}}

TOOLS
{tools}

INSTRUCTION
<<<
{instruction}
>>>"""
STANDING_FEEDBACK = """

Your standing order was translated literally into a program and checked against the records as they were when the user gave the instruction:
{why}
Revise the standing order under the same rules."""
Q_LEAD = "Write the program that executes this standing order literally, as its words say."


def q_prompt(cls, envs: list[str], order: str) -> str:
    return (f"{Q_LEAD}\n\nTOOLS\n{render_tools(cls)}\n\nSTATE SCHEMA (state keys are \"<environment>:<collection>\")\n"
            f"{render_schema(envs)}\n\n{FORMAT}{RULES2}\n\nSTANDING ORDER\n<<<\n{order.strip()}\n>>>")


def execute(code: str, battery: str) -> dict:
    req = json.dumps({"code": code, "battery": battery, "drops": [[]]})
    try:
        p = subprocess.run([PY, EXEC], input=req, capture_output=True, text=True, timeout=120)
        return json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"load_error": p.stderr[-300:]}
    except subprocess.TimeoutExpired:
        return {"load_error": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"load_error": f"{type(e).__name__}: {e}"}


_CALL = re.compile(r"^(\w+)\((.*)\)$")


def plan_commits(plan: str) -> list[tuple[str, dict]]:
    out = []
    for c in plan.split("+"):
        m = _CALL.match(c)
        if m:
            out.append((m.group(1), dict(p.split("=", 1) for p in re.split(r",(?![^()]*\))", m.group(2)) if "=" in p)))
    return out


def reproduces(answer, commits: list[dict], ids: set[str]) -> bool:
    """답 집합에, 참조 commit마다 같은 툴이고 ID 인자 값이 전부 같은 commit을 가진 plan이 있다. TOP이면 거짓."""
    if not isinstance(answer, list):
        return False
    need = [(aa.dag_tool(n), {k: str(v) for k, v in (n.get("params") or {}).items() if str(v) in ids}) for n in commits]
    for plan in answer:
        pcs = plan_commits(plan)
        if all(any(t == tool and all(a.get(k, "").strip("'\"") == v for k, v in args.items()) for t, a in pcs)
               for tool, args in need):
            return True
    return False


def modified_ids(cls, init, nodes, ids: set[str]) -> set[str]:
    """참조 계획의 commit이 바꾼 기존 레코드의 ID. 도메인 비교(기록 필드 제외)로 본다."""
    with contextlib.redirect_stdout(io.StringIO()):
        _, log = X.run_nodes(cls, init, nodes)
    out: set[str] = set()
    for x in log:
        if x["kind"] != "commit" or not x["ok"]:
            continue
        b, a = X.normalize(x["before"]), X.normalize(x["after"])
        fb, fa = X.flat(b), X.flat(a)
        for p in X.domain_changes(cls, x["before"], x["after"], {x["tool"]}):
            vb, va = fb.get(p), fa.get(p)
            if isinstance(vb, list) and isinstance(va, list):
                for r in vb:
                    if isinstance(r, dict) and r not in va:
                        out |= {str(v) for k, v in r.items() if ID_FIELD.search(str(k)) and str(v) in ids}
            else:
                seg = p.rsplit(".", 1)[-1]
                if seg in ids:
                    out.add(seg)
                if isinstance(vb, dict):
                    out |= {str(v) for k, v in vb.items() if ID_FIELD.search(str(k)) and str(v) in ids}
    return out


def stems(s: str) -> set[str]:
    return {w[:5] for w in words(s)}


def invented(preds: dict, instruction: str) -> list[str]:
    """술어 구간 중 내용어의 절반 이하만 원 지시문에 있는 것."""
    base = stems(instruction)
    bad = []
    for p in (preds or {}).values():
        ws = stems(str(p.get("span", "")))
        if ws and len(ws & base) * 2 <= len(ws):
            bad.append(str(p.get("span", ""))[:80])
    return bad


def check_order(cls, envs, order: str, battery: str, commits, ids, modified, instruction, key: str) -> dict:
    q = call(key, q_prompt(cls, envs, order), system=HEAD)
    code = aa.extract_block(q["content"], "python")
    res = execute(code, battery) if code else {"load_error": "no python block"}
    ans = res.get("results", [{}])[0].get("seed") if "results" in res else {"error": res.get("load_error")}
    v1 = reproduces(ans, commits, ids)
    left = sorted(i for i in modified if i.lower() in order.lower())
    inv = invented(res.get("predicates"), instruction) if "results" in res else []
    why = []
    if not v1:
        got = json.dumps(ans, ensure_ascii=False)[:800] if not isinstance(ans, dict) else f"nothing (the program failed: {str(ans.get('error'))[:200]})"
        why.append(f"- On those records it permits {got}, but the user's instruction led to "
                   + " + ".join(call_text(aa.dag_tool(n), n.get("params") or {}) for n in commits)[:800] + ".")
    if left:
        why.append(f"- It still names {', '.join(left)}, which the commit itself changes, so the next run would act on the same record again.")
    if inv:
        why.append("- These conditions are not in the user's instruction: " + "; ".join(inv))
    return {"order": order, "answer": ans, "V1": v1, "V2": not left, "V2_left": left, "V3": not inv, "V3_spans": inv,
            "ok": v1 and not left and not inv, "why": "\n".join(why)}


def standing(s: dict, m: int = 2) -> dict:
    envs = aa.seed_envs(s)
    cls, init, state = seed_state(s)
    OUT.joinpath("states").mkdir(parents=True, exist_ok=True)
    battery = OUT / "states" / (s["pair_id"].replace("/", "__") + ".json")
    battery.write_text(json.dumps({"seed": state}, ensure_ascii=False, default=str))
    nodes = s["execution_dag"]["nodes"]
    commits = [n for n in nodes if n.get("kind") == "commit"]
    ids = id_values(state)
    mod = modified_ids(cls, init, nodes, ids)
    body = STANDING_BODY.format(tools=render_tools(cls), instruction=s["instruction"].strip())
    out = {"pair_id": s["pair_id"], "modified_ids": sorted(mod), "tries": []}
    first = []
    for sch in ("A1", "A2"):
        for i in range(m):
            k = f"std|{s['pair_id']}|{sch}|{i}|0"
            r = call(k, STANDING_LEAD[sch] + "\n\n" + body)
            order = str((parse_json(r["content"]) or {}).get("order") or "").strip()
            chk = check_order(cls, envs, order, str(battery), commits, ids, mod, s["instruction"], "q|" + k) if order else \
                {"order": "", "ok": False, "why": "- No standing order was given.", "V1": False, "V2": False, "V3": False}
            chk.update(scheme=sch, i=i, round=0)
            out["tries"].append(chk)
            first.append((sch, i, r, chk))
    if not any(t["ok"] for t in out["tries"]):
        for sch, i, r, chk in first:
            k = f"std|{s['pair_id']}|{sch}|{i}|1"
            fb = STANDING_FEEDBACK.format(why=chk["why"])
            r2 = call(k, STANDING_LEAD[sch] + "\n\n" + body + "\n\nYOUR PREVIOUS ANSWER\n" + r["content"][-3000:] + fb)
            order = str((parse_json(r2["content"]) or {}).get("order") or "").strip()
            chk2 = check_order(cls, envs, order, str(battery), commits, ids, mod, s["instruction"], "q|" + k) if order else \
                {"order": "", "ok": False, "why": "- No standing order was given.", "V1": False, "V2": False, "V3": False}
            chk2.update(scheme=sch, i=i, round=1)
            out["tries"].append(chk2)
    out["F1"] = any(t["ok"] for t in out["tries"])
    ok = [t for t in out["tries"] if t["ok"]]
    out["order"] = ok[0]["order"] if ok else ""
    return out


# ==== D 정체성 필드 ==================================================================

IDENT_LEAD = {
    "D1": ("Which fields do these lookup tools use to find a record from the words a user would say (names, brands, "
           "codes, emails and the like)?"),
    "D2": ("For each lookup tool, read how it matches its query parameters against the records. List every record field "
           "it matches against."),
}
IDENT_BODY = """Do not list free-text fields (descriptions, notes, reasons).

Answer with one JSON object in a ```json block:
{{"fields": [{{"collection": "<state key>", "field": "..."}}]}}

STATE KEYS
{keys}

DATA CLASSES (schema.py)
{schema}

LOOKUP TOOLS (source)
{source}"""


def lookup_source(env: str) -> str:
    src, tree = aa.env_source(env), P._tree(env)
    names = [k for k, v in aa.env_class(env).tool_kinds.items() if v in ("lookup", "verify")]
    return "\n\n".join(ast.get_source_segment(src, f) for f in (P._func(tree, n) for n in names) if f is not None)


def identity(env: str, per_field: int = 5) -> dict:
    keys = "\n".join(f"- {k}" for k in aa.env_class(env).get_state_schema()["properties"])
    schema = (aa.AD / "environments" / env / "schema.py").read_text()
    props: dict[tuple[str, str], list] = {}
    for sch in ("D1", "D2"):
        r = call(f"ident|{env}|{sch}", IDENT_LEAD[sch] + "\n\n" + IDENT_BODY.format(keys=keys, schema=schema, source=lookup_source(env)))
        for f in (parse_json(r["content"]) or {}).get("fields") or []:
            c, fd = str(f.get("collection", "")).split(":")[-1], str(f.get("field", ""))
            if c and fd and sch not in props.get((c, fd), []):
                props.setdefault((c, fd), []).append(sch)
    cls = aa.env_class(env)
    kf = P.keys(env)
    schemas = {t["name"]: t for t in cls.get_tool_schemas() if cls.tool_kinds.get(t["name"]) in ("lookup", "verify")}
    kept, dropped = [], []
    for (coll, fd), by in sorted(props.items()):
        hit = None
        key = kf.get(coll)
        for st in P.corpus(env)[:20]:
            recs = [r for r in st.get(coll, []) if isinstance(r, dict) and isinstance(r.get(fd), str) and r.get(fd)]
            for rec in recs[:per_field]:
                rid = str(rec.get(key)) if key else None
                for name, t in schemas.items():
                    for p, spec in t["input_schema"].get("properties", {}).items():
                        if spec.get("type") not in (None, "string"):
                            continue
                        args = {q: "" for q in t["input_schema"].get("required", [])}
                        args[p] = rec[fd]
                        with contextlib.redirect_stdout(io.StringIO()):
                            ok, res, _ = X.call(cls(json.loads(json.dumps(st))), name, args)
                        txt = json.dumps(res, ensure_ascii=False, default=str) if ok else ""
                        if ok and ((rid and rid in txt) or (not rid and rec[fd] in txt)):
                            hit = f"{name}({p}={rec[fd]!r})"
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                break
        agree = len(by) == 2
        (kept if agree and hit else dropped).append({"collection": coll, "field": fd, "by": by, "agree": agree, "evidence": hit})
    return {"env": env, "kept": kept, "dropped": dropped}
