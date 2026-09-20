"""data/runs/b2-d01/<model_key>/*.jsonl 을 읽어 B2a·B2b 표를 마크다운으로 낸다 (D-034 읽는 법).

  - 셀 = 상태 × arm 의 행동 분포 (k 표본). 최빈 행동과 그 비율(안정성, D-035 척도).
  - B2b − B2a: 같은 상태에서 최빈 행동이 다른 행 수 (한 컨텍스트 효과).
  - CASE-D01 §2 (2026-09-16 응답) 와의 일치.
사용: .venv/bin/python scripts/b2_d01_report.py [model_key ...]
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "runs" / "b2-d01"
SPEC = json.loads((ROOT / "data" / "delegations" / "D01" / "case_states.json").read_text(encoding="utf-8"))
STATE_IDS = [s["id"] for s in SPEC["states"]]
ORDER_RE = re.compile(r"(?:SUP-)?(\d{3})\s*[x×X\*]\s*(\d+)")
ROW_RE = re.compile(r"^\|\s*(R?\d)\s*\|\s*(.*?)\s*\|?\s*$", re.M)


def reparse(content: str) -> dict[str, str]:
    cells: dict[str, list[str]] = {}
    for run, cell in ROW_RE.findall(content):
        c = cell.strip()
        if c.startswith("---") or c.lower().startswith("order"):
            continue
        cells.setdefault(run if run.startswith("R") else "R" + run, []).append(c)
    return {k: " / ".join(v) for k, v in cells.items()}


def norm(text: str) -> str:
    o = ORDER_RE.findall(text)
    return "+".join(f"SUP-{s}x{int(q)}" for s, q in sorted(o)) if o else ("NONE" if re.search(r"\bNONE\b|\bno order\b", text, re.I) else "UNPARSED:" + text.strip()[:40])


CASE = {k: norm(v) for k, v in SPEC["case_response_2026_09_16"].items()}


def load(model_key: str) -> dict[str, dict[str, list[str]]]:
    """arm → state_id → [parsed action per sample]. 같은 arm 에 파일이 여럿이면 전부 합친다."""
    out: dict[str, dict[str, list[str]]] = {"b2a": collections.defaultdict(list), "b2b": collections.defaultdict(list)}
    meta = collections.Counter()
    for p in sorted((RUNS / model_key).glob("*.jsonl")):
        if re.search(r"-k\d+-\d{8}-\d{6}-.+\.jsonl$", p.name):  # 꼬리표 붙은 재실행 파일은 본 표에서 뺀다 (§7 부록)
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            meta["calls"] += 1
            if "error" in r:
                meta["errors"] += 1; continue
            if r.get("finish_reason") == "length":
                meta["truncated"] += 1
            table = r.get("raw_cells") or {}
            if not any(table.values()):
                table = reparse(r.get("content", ""))
            for sid in r["parsed"]:
                raw = table.get(sid, "") if r["arm"] == "b2b" else (table.get("R1") or next(iter(table.values()), ""))
                act = norm(raw) if raw else "UNPARSED:<no row>"
                out[r["arm"]][sid].append(act)
                if act.startswith("UNPARSED"):
                    meta["unparsed_cells"] += 1
    return out, meta


def modal(acts: list[str]) -> tuple[str, float]:
    if not acts:
        return "—", 0.0
    c = collections.Counter(acts).most_common(1)[0]
    return c[0], c[1] / len(acts)


def dist(acts: list[str]) -> str:
    c = collections.Counter(acts)
    return ", ".join(f"{a} {n}/{len(acts)}" for a, n in c.most_common())


def report(model_key: str) -> None:
    data, meta = load(model_key)
    print(f"\n### {model_key}\n")
    print(f"호출 {meta['calls']}, 전송 오류 {meta['errors']}, 길이 절단 {meta['truncated']}, 미파싱 셀 {meta['unparsed_cells']}\n")
    print("| 상태 | B2a 분포 (k) | B2a 최빈 · 비율 | B2b 분포 (k) | B2b 최빈 · 비율 | B2b = B2a | CASE §2 | B2a = CASE |")
    print("|---|---|---|---|---|---|---|---|")
    agree = 0; n_rows = 0; agree_case = 0
    for sid in STATE_IDS:
        a, b = data["b2a"].get(sid, []), data["b2b"].get(sid, [])
        ma, fa = modal(a); mb, fb = modal(b)
        same = "○" if (a and b and ma == mb) else ("✗" if (a and b) else "—")
        same_case = "○" if (a and ma == CASE[sid]) else ("✗" if a else "—")
        if a and b:
            n_rows += 1; agree += (ma == mb)
        if a:
            agree_case += (ma == CASE[sid])
        print(f"| {sid} | {dist(a)} | {ma} · {fa:.0%} | {dist(b)} | {mb} · {fb:.0%} | {same} | {CASE[sid]} | {same_case} |")
    if n_rows:
        print(f"\n행 단위 일치(B2a 최빈 = B2b 최빈): {agree}/{n_rows}. B2a 최빈 = CASE §2: {agree_case}/{len(STATE_IDS)}.")
    stab_a = [modal(data['b2a'][s])[1] for s in STATE_IDS if data['b2a'].get(s)]
    stab_b = [modal(data['b2b'][s])[1] for s in STATE_IDS if data['b2b'].get(s)]
    if stab_a:
        print(f"안정성(셀 내 최빈 비율 평균): B2a {sum(stab_a)/len(stab_a):.2f}" + (f", B2b {sum(stab_b)/len(stab_b):.2f}" if stab_b else ""))


if __name__ == "__main__":
    keys = sys.argv[1:] or sorted(p.name for p in RUNS.iterdir() if p.is_dir())
    for k in keys:
        report(k)
