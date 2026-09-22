"""B2a·B2b를 D01의 여덟 상태(docs/CASE-D01.md §1)에 돌린다. D-034 순서, D-035 5(기본 온도, k=5).

  B2a: 상태를 한 건씩 텍스트로 주고 commit 을 묻는다. 상태당 k 회.
  B2b: 여덟 상태를 한 표에 주고 한 번에 답하게 한다 (CASE-D01 §1 재현). k 회.

호출 경로는 Plan.md §2 어댑터(OpenAI 호환 chat completions) 하나. 서버는 vLLM (scripts/vllm_serve.sbatch).
샘플링 파라미터는 보내지 않는다 → 서버가 모델 generation_config 기본값을 쓴다(D-035 5 "제공자 기본값").
로그는 호출 하나가 JSONL 한 줄: 요청 전문, 응답 content, 파싱 결과, usage, finish_reason. 추론은 서버의 reasoning parser가 분리하고 읽지 않는다.

사용:
  .venv/bin/python scripts/b2_d01.py --model-key qwen3.8-27B-FP8 --arm b2a --k 5
  .venv/bin/python scripts/b2_d01.py --model-key qwen3.8-27B-FP8 --arm b2b --k 5
엔드포인트는 runs/serve/<model_key>.endpoint 에서 읽는다 (--base-url 로 직접 줄 수도 있다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATES_PATH = ROOT / "data" / "delegations" / "D01" / "case_states.json"
OUT_DIR = ROOT / "data" / "runs" / "b2-d01"

ORDER_RE = re.compile(r"(SUP-\d{3})\s*[x×X\*]\s*(\d+)")
ROW_RE = re.compile(r"^\|\s*(R?\d)\s*\|\s*(.*?)\s*\|?\s*$", re.M)


def state_row(s: dict) -> str:
    return f"| {s['id']} | {s['stock']} | {s['listings']} | {s['contracts']} |"


def build_prompt(spec: dict, arm: str, state: dict | None = None, single_label: str = "R1") -> str:
    if arm == "b2b":
        rows = "\n".join(state_row(s) for s in spec["states"])
        return spec["header_common"] + "\n" + spec["intro_multi"] + "\n" + spec["table_header"] + "\n" + rows + "\n" + spec["footer_multi"]
    assert state is not None
    # B2a: 행 라벨은 전부 R1 로 준다. 상태 내용은 같고 라벨만 중립화한다(서열 힌트 제거). 진짜 id 는 로그에 남긴다.
    s = dict(state, id=single_label)
    return spec["header_common"] + "\n" + spec["intro_single"] + "\n" + spec["table_header"] + "\n" + state_row(s) + "\n" + spec["footer_single"]


def normalize_order(text: str) -> str:
    """'SUP-031 x 60 / SUP-032 x 40' → 'SUP-031x60+SUP-032x40' (정렬). NONE → 'NONE'. 못 읽으면 'UNPARSED:<원문>'."""
    orders = ORDER_RE.findall(text)
    if orders:
        return "+".join(f"{sid}x{int(q)}" for sid, q in sorted(orders))
    if re.search(r"\bNONE\b", text, re.I) or re.search(r"\bno order\b", text, re.I):
        return "NONE"
    return "UNPARSED:" + text.strip()[:80]


def parse_table(content: str) -> dict[str, str]:
    """응답 표에서 Run 별 원문 셀을 모은다. 같은 Run 이 여러 줄이면 ' / ' 로 잇는다."""
    cells: dict[str, list[str]] = {}
    for run, cell in ROW_RE.findall(content):
        if cell.strip().startswith("---") or cell.strip().lower().startswith("order"):
            continue
        run = run if run.startswith("R") else "R" + run  # '1' → 'R1'
        cells.setdefault(run, []).append(cell.strip())
    return {run: " / ".join(v) for run, v in cells.items()}


def call(client: openai.OpenAI, model_key: str, prompt: str, max_tokens: int) -> dict:
    t0 = dt.datetime.now(dt.timezone.utc)
    resp = client.chat.completions.create(
        model=model_key,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    t1 = dt.datetime.now(dt.timezone.utc)
    d = resp.model_dump()
    msg = d["choices"][0]["message"]
    return {
        "request": {"model": model_key, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
                    "sampling": "server default (no temperature/top_p sent)"},
        "response_id": d.get("id"),
        "served_model": d.get("model"),
        "content": msg.get("content") or "",
        "finish_reason": d["choices"][0].get("finish_reason"),
        "usage": d.get("usage"),
        "t_start": t0.isoformat(), "t_end": t1.isoformat(), "latency_s": (t1 - t0).total_seconds(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-key", required=True)
    ap.add_argument("--arm", choices=["b2a", "b2b"], required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--states", default=None, help="B2a 에서 돌릴 상태 id 를 쉼표로 (예: R8). 기본 전부")
    ap.add_argument("--tag", default="", help="출력 파일명에 붙일 꼬리표 (예: retry32k)")
    ap.add_argument("--dry-run", action="store_true", help="프롬프트만 출력")
    args = ap.parse_args()

    spec = json.loads(STATES_PATH.read_text(encoding="utf-8"))
    jobs: list[tuple[str, int, str]] = []  # (state_id or ALL, sample_idx, prompt)
    if args.arm == "b2b":
        p = build_prompt(spec, "b2b")
        jobs = [("ALL", i, p) for i in range(args.k)]
    else:
        wanted = set(args.states.split(",")) if args.states else None
        for s in spec["states"]:
            if wanted and s["id"] not in wanted:
                continue
            p = build_prompt(spec, "b2a", s)
            jobs += [(s["id"], i, p) for i in range(args.k)]

    if args.dry_run:
        print(jobs[0][2]); print(f"\n[{len(jobs)} calls]"); return 0

    base_url = args.base_url
    if base_url is None:
        ep = ROOT / "runs" / "serve" / f"{args.model_key}.endpoint"
        if not ep.exists():
            print(f"[FATAL] endpoint file not found: {ep}", file=sys.stderr); return 1
        base_url = ep.read_text().strip()
    client = openai.OpenAI(base_url=base_url, api_key="EMPTY", timeout=1800, max_retries=2)

    out_dir = OUT_DIR / args.model_key
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{args.arm}-k{args.k}-{stamp}{('-' + args.tag) if args.tag else ''}.jsonl"
    print(f"{len(jobs)} calls → {out_path}  (base_url={base_url})")

    def run_one(job):
        sid, idx, prompt = job
        rec = call(client, args.model_key, prompt, args.max_tokens)
        table = parse_table(rec["content"])
        if args.arm == "b2a":
            raw = table.get("R1", "")
            parsed = {sid: normalize_order(raw) if raw else "UNPARSED:<no row>"}
            raw_cells = {sid: raw}
        else:
            parsed = {s["id"]: (normalize_order(table[s["id"]]) if s["id"] in table else "UNPARSED:<no row>") for s in spec["states"]}
            raw_cells = table
        return {"arm": args.arm, "model_key": args.model_key, "state_id": sid, "sample_idx": idx,
                "raw_cells": raw_cells, "parsed": parsed, **rec}

    n_done = 0
    with out_path.open("w", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, j): j for j in jobs}
        for fut in as_completed(futs):
            j = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:  # 전송 오류는 기록하고 계속
                rec = {"arm": args.arm, "model_key": args.model_key, "state_id": j[0], "sample_idx": j[1], "error": repr(e)}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            n_done += 1
            tag = rec.get("parsed") or rec.get("error")
            print(f"[{n_done}/{len(jobs)}] {j[0]}#{j[1]} finish={rec.get('finish_reason')} {tag}")
    print("done:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
