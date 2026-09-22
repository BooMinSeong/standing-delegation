"""후보 Q 프로그램을 격리된 프로세스에서 배터리 위에 돌린다 (c567_q_extract.py가 부른다).

stdin: {"code": str, "battery": path, "drops": [[...], ...], "states": [name, ...] | null}
stdout: {"predicates": {...}, "results": [{state: canon | {"error": str}}, ...]}  (drops 순서대로)
행동 표기는 canon()이 정규화한다: "TOP", 또는 정렬된 plan 문자열 목록.
plan = "NONE" 또는 commit들을 "+"로 이은 것. commit = tool(arg=value,...) 인자 이름순.
"""
from __future__ import annotations

import json
import re
import sys

TOP = "TOP"
_CALL = re.compile(r"^\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", re.S)


def _val(v: str) -> str:
    v = v.strip().strip("'\"").strip()
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else repr(f)
    except ValueError:
        return v


def canon_commit(c: str) -> str:
    m = _CALL.match(c)
    if not m:
        raise ValueError(f"commit 형식 아님: {c!r}")
    tool, body = m.group(1), m.group(2)
    args = {}
    for part in [p for p in re.split(r",(?![^()]*\))", body) if p.strip()]:
        if "=" not in part:
            raise ValueError(f"인자 형식 아님: {part!r}")
        k, v = part.split("=", 1)
        args[k.strip()] = _val(v)
    return tool + "(" + ",".join(f"{k}={args[k]}" for k in sorted(args)) + ")"


def canon_plan(p) -> str:
    if isinstance(p, (list, tuple)):
        parts = list(p)
    else:
        s = str(p).strip()
        if s.upper() == "NONE":
            return "NONE"
        parts = [x for x in re.split(r"\+(?![^()]*\))", s) if x.strip()]
    return "+".join(sorted(canon_commit(x) for x in parts))


def canon(ans):
    if isinstance(ans, str) and ans.strip().upper() == "TOP":
        return TOP
    if ans is None:
        raise ValueError("None 반환")
    if isinstance(ans, str):
        ans = [ans]
    return sorted({canon_plan(p) for p in ans})


def main() -> None:
    req = json.loads(sys.stdin.read())
    battery = json.loads(open(req["battery"]).read())
    names = req.get("states") or list(battery)
    ns: dict = {"TOP": TOP, "__name__": "q_candidate"}
    try:
        exec(compile(req["code"], "<candidate>", "exec"), ns)
        preds = ns.get("PREDICATES", {})
        fn = ns["answer"]
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"load_error": f"{type(e).__name__}: {e}"}))
        return
    out = []
    for drop in req["drops"]:
        res = {}
        for n in names:
            try:
                res[n] = canon(fn(json.loads(json.dumps(battery[n])), frozenset(drop)))
            except Exception as e:  # noqa: BLE001
                res[n] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
        out.append(res)
    print(json.dumps({"predicates": preds, "results": out}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
