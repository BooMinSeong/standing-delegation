"""종이 검사 2·3: sem_type 배정 (D-040 설계). LLM이 내고 프로그램이 되받는다. q는 주지 않는다.

체계 둘
  F 필드 단위 : 필드 하나 + dataclass + 그 컬렉션을 읽는 툴의 docstring + 코퍼스 예시 값 다섯
  R 레코드 통째: dataclass + docstring + 예시 레코드 다섯 → 필드마다 한 번에
되받기
  (1) 코퍼스 전체 값이 kind의 형식에 맞는가(아래 KIND_CHECK). 틀린 체계의 답은 버린다
  (2) 그 필드 이름이 툴 반환에 실리는가(c23_profile.returned_fields). 표시만 한다
결정: 두 체계가 같으면 그대로. 갈리면 **넓은 쪽**(값 범위 제약이 없는 kind). 둘 다 제약이 있고 다르면 unknown.
둘 다 되받기에 실패하면 unknown. unknown도 편집 대상에서 빼지 않는다.
q 상수의 의미 타입은 Q 쪽 일이라 q를 보여 주고 따로 묻는다(QCONST).

출력: data/paper-checks/c23/semtype_raw.jsonl(원출력), semtype.json(결정)
사용: .venv/bin/python scripts/paper/c23_semtype.py
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import aa  # noqa: E402
import c23_profile as P  # noqa: E402

OUT = aa.ROOT / "data" / "paper-checks" / "c23"
ENVS = ("store_procurement_and_inventory", "flight_and_travel_management")
KINDS = ["count", "money", "duration", "date", "datetime", "time_of_day", "month", "year", "day_of_month",
         "rank", "ratio", "rate", "currency", "unit", "boolean", "identifier", "name", "code", "category",
         "contact", "free_text", "other"]
# 값 범위 제약이 있는 kind (환경 독립 고정표 초판: count ≥ 0, month 1..12, date ISO, currency ISO 4217)
CONSTRAINED = {"count", "month", "date", "datetime", "currency"}
QCONST = {  # (환경, q 파일 또는 문장, 상수 구간)
    "store_procurement_and_inventory": (aa.ROOT / "data/delegations/D01/q_minus.txt", "100 cans"),
    "flight_and_travel_management": (aa.ROOT / "data/gen-v0/flight_preview_023.q_plus.txt", "3 checked bags"),
}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _iso_date(v):
    try:
        dt.date.fromisoformat(v)
        return True
    except Exception:  # noqa: BLE001
        return False


def _iso_dt(v):
    try:
        dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return True
    except Exception:  # noqa: BLE001
        return False


KIND_CHECK = {
    "count": lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0,
    "money": _num, "duration": _num, "rank": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "ratio": _num, "rate": _num,
    "date": lambda v: isinstance(v, str) and _iso_date(v),
    "datetime": lambda v: isinstance(v, str) and _iso_dt(v),
    "time_of_day": lambda v: isinstance(v, str) and bool(re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?.*", v)),
    "month": lambda v: isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 12,
    "year": lambda v: isinstance(v, int) and not isinstance(v, bool) and 1000 <= v <= 9999,
    "day_of_month": lambda v: isinstance(v, int) and 1 <= v <= 31,
    "currency": lambda v: isinstance(v, str) and bool(re.fullmatch(r"[A-Z]{3}", v)),
    "boolean": lambda v: isinstance(v, bool),
}


def field_values(env: str) -> dict[str, dict[str, list]]:
    """컬렉션 → {경로: 코퍼스 값 목록}. 경로는 'f', 'f[].g'(목록 속 dict), 'f.*'(dict 값)."""
    out: dict[str, dict[str, list]] = {}
    for coll in P.collection_classes(env):
        acc: dict[str, list] = {}
        for st in P.corpus(env):
            for r in st.get(coll, []) or []:
                if not isinstance(r, dict):
                    continue
                for f, v in r.items():
                    if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                        for x in v:
                            for g, w in x.items():
                                if not isinstance(w, (list, dict)):
                                    acc.setdefault(f"{f}[].{g}", []).append(w)
                    elif isinstance(v, dict) and v and all(not isinstance(w, (list, dict)) for w in v.values()):
                        for w in v.values():
                            acc.setdefault(f"{f}.*", []).append(w)
                    elif not isinstance(v, (list, dict)):
                        acc.setdefault(f, []).append(v)
                    else:
                        acc.setdefault(f, []).append(v)
        out[coll] = acc
    return out


def class_source(env: str, cls: str) -> str:
    src = (aa.AD / "environments" / env / "schema.py").read_text()
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == cls:
            seg = ast.get_source_segment(src, n)
            return seg.split("    def to_dict")[0].rstrip()
    return ""


def readers(env: str, coll: str) -> list[tuple[str, str]]:
    """self.state["coll"]을 읽는 lookup·verify 툴과 docstring."""
    kinds = P.aa.env_class(env).tool_kinds
    out = []
    for fn in P._tools(env):
        if kinds.get(fn.name) not in ("lookup", "verify"):
            continue
        if any(isinstance(m, ast.Subscript) and isinstance(m.slice, ast.Constant) and m.slice.value == coll
               for m in ast.walk(fn)):
            out.append((fn.name, (ast.get_docstring(fn) or "").strip()[:700]))
    return out


def examples(vals: list, n: int = 5) -> list:
    seen, out = set(), []
    for v in vals:
        k = json.dumps(v, sort_keys=True, default=str)
        if k not in seen:
            seen.add(k)
            out.append(v)
    if len(out) <= n:
        return out
    step = len(out) / n
    return [out[int(i * step)] for i in range(n)]


SPEC = ('Answer with JSON only, inside a ```json block. Use keys "kind", "of", "unit".\n'
        f'- "kind": exactly one of {KINDS}\n'
        '- "of": what is counted or measured, as a short noun phrase (for non-quantities: what the value denotes)\n'
        '- "unit": the unit of measurement as a short plural noun (e.g. "cans", "days", "USD", "stops", "seats"), '
        'or "" if the value has no unit')


def prompt_field(env, coll, cls, path, declared, vals):
    tools = "\n".join(f"- {t}: {d}" for t, d in readers(env, coll)) or "- (none found)"
    return (f"You are annotating the data schema of a software environment. Below is one field of one record type, "
            f"how the record type is declared, which tools read it, and example values of the field from real records.\n\n"
            f"Record type (collection `{coll}`):\n```python\n{class_source(env, cls)}\n```\n"
            f"Field: `{path}` (declared type: {declared})\n\nTools that read this collection:\n{tools}\n\n"
            f"Example values of `{path}`: {json.dumps(examples(vals), default=str)}\n\n"
            f"Question: what does the value of this field count or measure?\n{SPEC}")


def prompt_record(env, coll, cls, paths, recs):
    tools = "\n".join(f"- {t}: {d}" for t, d in readers(env, coll)) or "- (none found)"
    spec = SPEC.replace('Use keys "kind", "of", "unit".',
                        'Return one JSON object whose keys are exactly these field paths: '
                        f'{json.dumps(paths)}; each value is an object with keys "kind", "of", "unit".')
    return (f"You are annotating the data schema of a software environment. Below is a record type, "
            f"the tools that read it, and example records.\n\nRecord type (collection `{coll}`):\n"
            f"```python\n{class_source(env, cls)}\n```\n\nTools that read this collection:\n{tools}\n\n"
            f"Example records:\n```json\n{json.dumps(recs, indent=1, default=str)[:6000]}\n```\n\n"
            f"Paths like `a[].b` mean field b of the dicts inside list a; `a.*` means the values of dict a.\n"
            f"Question: for each field, what does its value count or measure?\n{spec}")


def parse_json(text: str):
    b = aa.extract_block(text, "json")
    for cand in ([b] if b else []) + [text]:
        try:
            return json.loads(cand)
        except Exception:  # noqa: BLE001
            m = re.search(r"\{.*\}", cand or "", re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:  # noqa: BLE001
                    pass
    return None


def verify(kind: str, vals: list) -> bool:
    if kind not in KINDS:
        return False
    chk = KIND_CHECK.get(kind)
    if chk is None:
        return True
    vv = [v for v in vals if v not in ("", None)]
    return bool(vv) and all(chk(v) for v in vv)


def decide(f: dict | None, r: dict | None, vals: list) -> dict:
    okf = bool(f) and verify(f.get("kind"), vals)
    okr = bool(r) and verify(r.get("kind"), vals)
    if not okf and not okr:
        return {"kind": "unknown", "of": "", "units": [], "how": "둘 다 되받기 실패"}
    if okf and okr:
        units = sorted({(f.get("unit") or "").strip().lower(), (r.get("unit") or "").strip().lower()} - {""})
        if f["kind"] == r["kind"]:
            return {"kind": f["kind"], "of": f.get("of", ""), "units": units, "how": "일치"}
        cf, cr = f["kind"] in CONSTRAINED, r["kind"] in CONSTRAINED
        if cf and not cr:
            return {"kind": r["kind"], "of": r.get("of", ""), "units": units, "how": f"갈림 F={f['kind']} R={r['kind']} → 넓은 쪽 R"}
        if cr and not cf:
            return {"kind": f["kind"], "of": f.get("of", ""), "units": units, "how": f"갈림 F={f['kind']} R={r['kind']} → 넓은 쪽 F"}
        if cf and cr:
            return {"kind": "unknown", "of": "", "units": units, "how": f"갈림 F={f['kind']} R={r['kind']} → 둘 다 제약, unknown"}
        return {"kind": f["kind"], "of": f.get("of", ""), "units": units, "how": f"갈림 F={f['kind']} R={r['kind']} → 둘 다 무제약, F"}
    one = f if okf else r
    return {"kind": one["kind"], "of": one.get("of", ""), "units": [(one.get("unit") or "").strip().lower()] if one.get("unit") else [],
            "how": f"{'R' if okf else 'F'} 되받기 실패 → {'F' if okf else 'R'}"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = open(OUT / "semtype_raw.jsonl", "w")
    jobs = []
    for env in ENVS:
        cc = P.collection_classes(env)
        fv = field_values(env)
        cf = P.class_fields(env)
        for coll, cls in cc.items():
            paths = sorted(fv.get(coll, {}))
            if not paths:
                continue
            for path in paths:
                top = path.split("[")[0].split(".")[0]
                declared = cf.get(cls, {}).get(top, {}).get("type", "?")
                jobs.append(("F", env, coll, path, prompt_field(env, coll, cls, path, declared, fv[coll][path])))
            recs = []
            for st in P.corpus(env):
                recs += [r for r in st.get(coll, []) or [] if isinstance(r, dict)]
            jobs.append(("R", env, coll, None, prompt_record(env, coll, cls, paths, examples(recs))))
        cp, span = QCONST[env]
        q = cp.read_text()
        jobs.append(("Q", env, None, span,
                     f"Here is an instruction given to an agent:\n\n\"\"\"\n{q}\n\"\"\"\n\n"
                     f"Consider the constant `{span}` in it. What does this constant count or measure?\n{SPEC}"))

    def run(job):
        scheme, env, coll, path, prompt = job
        res = aa.ask(prompt, max_tokens=12000)
        return job, res, parse_json(res["content"])

    results = {}
    with ThreadPoolExecutor(16) as ex:
        for (scheme, env, coll, path, prompt), res, parsed in ex.map(run, jobs):
            raw.write(json.dumps({"scheme": scheme, "env": env, "collection": coll, "path": path, "prompt": prompt,
                                  "content": res["content"], "finish": res["finish"],
                                  "parsed": parsed}, ensure_ascii=False) + "\n")
            results[(scheme, env, coll, path)] = parsed
    raw.close()

    decided = {}
    for env in ENVS:
        fv = field_values(env)
        rf = P.returned_fields(env)
        decided[env] = {"fields": {}, "qconst": results.get(("Q", env, None, QCONST[env][1]))}
        for coll in P.collection_classes(env):
            rec = results.get(("R", env, coll, None)) or {}
            for path, vals in fv.get(coll, {}).items():
                f = results.get(("F", env, coll, path))
                r = rec.get(path) if isinstance(rec, dict) else None
                d = decide(f if isinstance(f, dict) else None, r if isinstance(r, dict) else None, vals)
                leaf = path.split(".")[-1].replace("[]", "")
                d.update({"F": f, "R": r, "returned": leaf in rf or path.split("[")[0].split(".")[0] in rf})
                decided[env]["fields"][f"{coll}.{path}"] = d
    (OUT / "semtype.json").write_text(json.dumps(decided, ensure_ascii=False, indent=1, default=str))
    n = sum(len(v["fields"]) for v in decided.values())
    print(f"jobs {len(jobs)}, fields {n} → {OUT / 'semtype.json'}")


if __name__ == "__main__":
    main()
