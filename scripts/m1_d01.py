"""M1 (프록시 툴 실행)을 D01 여덟 상태에 돌린다. D-034 세 번째 arm. 상태당 k 런, 런마다 새 환경.

사용: PYTHONPATH=/home3/b.ms/projects/standing-delegation/data/agentabstain-code:data \
      .venv/bin/python -u scripts/m1_d01.py --model-key qwen3.8-27B-FP8 --k 5 [--states R1,R5] [--tag x]
출력: data/runs/m1-d01/<model_key>/m1-k<k>-<stamp>[-tag].jsonl (런 하나가 한 줄)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.runner.run import run_episode  # noqa: E402

STATES_DIR = ROOT / "data" / "delegations" / "D01" / "states" / "case"
Q_MINUS = ROOT / "data" / "delegations" / "D01" / "q_minus.txt"
P0 = ROOT / "data" / "contracts" / "P0.txt"
ENV_MODULE = "envs.store_procurement_and_inventory.environment"
OUT_DIR = ROOT / "data" / "runs" / "m1-d01"


def summarize(rec: dict) -> str:
    ok = [c for c in rec["commits"] if c["success"]]
    if not ok:
        return "NONE"
    return "+".join(sorted(f"{c['params'].get('supplier_id')}x{c['params'].get('quantity')}" for c in ok))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-key", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--states", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--max-steps", type=int, default=30)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    base_url = args.base_url or (ROOT / "runs" / "serve" / f"{args.model_key}.endpoint").read_text().strip()
    client = openai.OpenAI(base_url=base_url, api_key="EMPTY", timeout=1800, max_retries=2)
    q = Q_MINUS.read_text(encoding="utf-8"); contract = P0.read_text(encoding="utf-8")
    wanted = set(args.states.split(",")) if args.states else None
    state_files = sorted(p for p in STATES_DIR.glob("R*.json") if not wanted or p.stem in wanted)
    jobs = [(p.stem, i) for p in state_files for i in range(args.k)]
    states = {p.stem: json.loads(p.read_text()) for p in state_files}

    out_dir = OUT_DIR / args.model_key; out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"m1-k{args.k}-{stamp}{('-' + args.tag) if args.tag else ''}.jsonl"
    print(f"{len(jobs)} runs → {out_path} (base_url={base_url})", flush=True)

    def one(job):
        sid, idx = job
        rec = run_episode(client, args.model_key, ENV_MODULE, states[sid], contract, q, args.max_steps, args.max_tokens)
        return {"arm": "m1", "model_key": args.model_key, "state_id": sid, "sample_idx": idx, "contract": "P0",
                "q_file": str(Q_MINUS.relative_to(ROOT)), "state_file": str((STATES_DIR / f"{sid}.json").relative_to(ROOT)), **rec}

    n = 0
    with out_path.open("w", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, j): j for j in jobs}
        for fut in as_completed(futs):
            j = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"arm": "m1", "model_key": args.model_key, "state_id": j[0], "sample_idx": j[1], "error": repr(e)}
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n"); f.flush()
            n += 1
            tag = summarize(rec) if "commits" in rec else rec.get("error")
            tools = [tc["name"] for t in rec.get("turns", []) for tc in t["tool_calls"]]
            print(f"[{n}/{len(jobs)}] {j[0]}#{j[1]} steps={rec.get('n_steps')} finish={rec.get('finish')} commit={tag} tools={tools}", flush=True)
    print("done:", out_path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
