"""생성기 v0 실행기. 위임 q + 기준 상태 + 스키마 → 최소쌍 상태들과 manifest, 대조표(마크다운).

사용:
  PYTHONPATH=<agentabstain-code>:data .venv/bin/python scripts/gen_v0.py \
      --q data/delegations/D01/q_minus.txt --base <seed initial_state.json> \
      --schema data/envs/store_procurement_and_inventory/schema.py \
      --env-module envs.store_procurement_and_inventory.environment \
      --out data/delegations/D01/states/gen-v0
"""
from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.gen.minimal_pairs import Generator, write, markdown_table  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True); ap.add_argument("--base", required=True); ap.add_argument("--schema", required=True)
    ap.add_argument("--env-module", default=None, help="예시 상태(값 풀)와 재생 검사용. 없으면 기준 상태만 풀로 쓴다")
    ap.add_argument("--out", required=True); ap.add_argument("--q-strip", default=None, help="q 에서 지울 구간(D− 판 만들기)")
    args = ap.parse_args()

    q = pathlib.Path(args.q).read_text(encoding="utf-8") if pathlib.Path(args.q).exists() else args.q
    if args.q_strip:
        assert args.q_strip in q, "q-strip 구간이 q 에 없다"
        q = q.replace(args.q_strip, "")
    base = json.loads(pathlib.Path(args.base).read_text())
    example = None; cls = None
    if args.env_module:
        mod = importlib.import_module(args.env_module)
        cls = next(v for k, v in vars(mod).items() if k.endswith("Environment") and k != "BaseEnvironment" and isinstance(v, type))
        try: example = cls.get_example_state()
        except Exception as e: print("[warn] example state 실패:", e, file=sys.stderr)
    g = Generator(q, base, pathlib.Path(args.schema), example)
    dims = g.run()
    out = pathlib.Path(args.out)
    meta = {"q": q, "base": args.base, "schema": args.schema, "q_tokens": g.qtok, "q_numbers": g.nums, "q_dates": g.dates,
            "anchors": sorted(g.anchors), "reachable": {c: i for c, i in g.reach_by_col.items()}}
    write(dims, out, base, meta)
    print(f"q 수: {g.nums}, q 날짜: {g.dates}")
    print("닻:", sorted(g.anchors))
    print("도달:", {c: len(i) for c, i in g.reach_by_col.items()})
    print(f"차원 {len(dims)}개 (tier1 {sum(d['tier']==1 for d in dims)}, tier2 {sum(d['tier']==2 for d in dims)}) → {out}\n")
    print(markdown_table(dims))
    # 재생 검사: 환경이 상태를 적재하고 조회 툴이 도는지
    if cls is not None:
        bad = 0
        for k, d in enumerate(dims):
            try:
                env = cls(d["state"])
                for s in cls.get_tool_schemas():
                    if s["kind"] == "lookup" and not s["input_schema"].get("required"):
                        env.call_tool(s["name"])
            except Exception as e:
                bad += 1; print(f"[재생 실패] P{k+1:02d}: {type(e).__name__}: {str(e)[:120]}")
        print(f"\n재생 검사: {len(dims)-bad}/{len(dims)} 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
