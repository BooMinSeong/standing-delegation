"""씨앗 필터 다섯을 LLM 슬롯으로 다시 판정한다 (D-043). 기준은 docs/PREREG-SLOTS.md에 먼저 커밋한다.

단계 (순서 고정)
  tags   슬롯 C: 씨앗 131이 쓰는 환경 38의 기록 필드 태그 → tags.json
  exec   태그로 필터 2·3·5 (필터 3은 Qwen3.8 역연산 후보 + 실행) → exec.jsonl
  reach  슬롯 B: 필터 2·3·5 통과 씨앗에 필터 4 → reach.jsonl
  stand  슬롯 A: 필터 2·3·4·5 통과 씨앗에 필터 1 → standing.jsonl
  ident  슬롯 D: D01·항공 환경의 정체성 필드 → identity.json
  c8     태그로 검사 8(역연산 양성·음성 대조)
  report 표: 슬롯 판정과 종이 검사 때의 규칙 판정(data/paper-checks/c48/c4.jsonl)을 나란히
사용: .venv/bin/python scripts/paper/c4_slots.py <단계> [--only PAIR_ID ...]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import aa  # noqa: E402
import c48_exec as X  # noqa: E402
import slots as S  # noqa: E402

OUT = S.OUT
D01_SEED = "emergent_risk_discovery/preview_018"
D01_ENV = "store_procurement_and_inventory"
AIR_ENV = "flight_and_travel_management"
D01_IDENTITY = {("catalog_products", "name"), ("catalog_products", "brand"), ("catalog_products", "category"),
                ("inventory_items", "name"), ("inventory_items", "sku"), ("supplier_listings", "supplier_name"),
                ("supplier_listings", "supplier_sku"), ("counterfeit_reports", "product_name"),
                ("counterfeit_reports", "reported_brand")}


def jl_write(name: str, rows: list[dict]) -> None:
    with open(OUT / name, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def jl_read(name: str) -> dict[str, dict]:
    return {json.loads(x)["pair_id"]: json.loads(x) for x in (OUT / name).read_text().splitlines()}


def load_tags() -> None:
    X.TAGS = S.tag_index(json.loads((OUT / "tags.json").read_text()))


def seeds(only: list[str] | None) -> list[dict]:
    return [s for s in aa.seeds() if not only or s["pair_id"] in only]


def step_tags(a) -> None:
    envs = sorted({e for s in aa.seeds() for e in aa.seed_envs(s)})
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(S.record_tags, envs))
    (OUT / "tags.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    kept = sum(len(r["kept"]) for r in rows)
    dropped = sum(len(r["dropped"]) for r in rows)
    print(f"환경 {len(rows)}, 태그 확인 {kept}, 버림 {dropped}")
    d01 = next(r for r in rows if r["env"] == D01_ENV)
    print("D01 태그:", [(t["path"], t["kind"]) for t in d01["kept"]])


def step_exec(a) -> None:
    load_tags()
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda s: X.seed_filters(s, True), seeds(a.only)))
    jl_write("exec.jsonl", rows)
    for k in ("F2", "F3", "F5"):
        c = collections.Counter(r.get(k) for r in rows)
        print(f"{k}: 통과 {c[True]} 불통 {c[False]} 판정 불가 {c[None]}")


def passing(exec_rows: dict, keys=("F2", "F3", "F5")) -> list[str]:
    return [p for p, r in exec_rows.items() if all(r.get(k) for k in keys)]


def step_reach(a) -> None:
    load_tags()
    ex_rows = jl_read("exec.jsonl")
    todo = [s for s in seeds(a.only) if s["pair_id"] in passing(ex_rows)]
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(S.reach, todo))
    jl_write("reach.jsonl", rows)
    print(f"대상 {len(rows)}, 필터 4 통과 {sum(r['F4'] for r in rows)}")


def step_stand(a) -> None:
    load_tags()
    ex_rows, rc = jl_read("exec.jsonl"), jl_read("reach.jsonl")
    ok = {p for p in passing(ex_rows) if rc.get(p, {}).get("F4")}
    todo = [s for s in seeds(a.only) if s["pair_id"] in ok]
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda s: S.standing(s, a.m), todo))
    jl_write("standing.jsonl", rows)
    print(f"대상 {len(rows)}, 필터 1 통과 {sum(r['F1'] for r in rows)}")


def step_ident(a) -> None:
    with ThreadPoolExecutor(2) as ex:
        rows = list(ex.map(S.identity, [D01_ENV, AIR_ENV]))
    (OUT / "identity.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    for r in rows:
        print(r["env"], "확인", [(k["collection"], k["field"]) for k in r["kept"]], "버림", len(r["dropped"]))


def step_c8(a) -> None:
    load_tags()
    X.OUT = OUT
    X.c8(True)


def cap(rows: list[dict]) -> tuple[int, int, int]:
    e = collections.Counter(r["env"] for r in rows)
    return len(rows), len(e), sum(min(3, n) for n in e.values())


def step_report(a) -> None:
    ex_rows = jl_read("exec.jsonl")
    rc = jl_read("reach.jsonl") if (OUT / "reach.jsonl").exists() else {}
    st = jl_read("standing.jsonl") if (OUT / "standing.jsonl").exists() else {}
    old = {json.loads(x)["pair_id"]: json.loads(x) for x in (aa.ROOT / "data/paper-checks/c48/c4.jsonl").read_text().splitlines()}
    print("## 필터별 통과 / 131 (슬롯 판정 | 종이 검사 규칙 판정)\n")
    print("| 필터 | 슬롯 | 규칙 |\n|---|---|---|")
    for k in ("F2", "F3", "F5"):
        print(f"| {k} | {sum(bool(r.get(k)) for r in ex_rows.values())} | {sum(bool(r.get(k)) for r in old.values())} |")
    print(f"| F4 | {sum(r['F4'] for r in rc.values())} / {len(rc)} 대상 | {sum(bool(r.get('F4')) for r in old.values())} |")
    print(f"| F1 | {sum(r['F1'] for r in st.values())} / {len(st)} 대상 | {sum(bool(r.get('F1')) for r in old.values())} |")
    print("\n## 누적 (슬롯 판정)\n\n| 단계 | 씨앗 | 환경 | 환경당 3 상한 (기준 14) |\n|---|---|---|---|")
    acc = list(ex_rows.values())
    for label, pred in (("F5", lambda r: r.get("F5")), ("+F2", lambda r: r.get("F2")), ("+F3", lambda r: r.get("F3")),
                        ("+F4 (슬롯 B)", lambda r: rc.get(r["pair_id"], {}).get("F4")),
                        ("+F1 (슬롯 A)", lambda r: st.get(r["pair_id"], {}).get("F1"))):
        acc = [r for r in acc if pred(r)]
        n, e, c = cap(acc)
        print(f"| {label} | {n} | {e} | {c} |")
    print("\n## D01 필요조건\n")
    tags = json.loads((OUT / "tags.json").read_text()) if (OUT / "tags.json").exists() else []
    d01t = next((r for r in tags if r["env"] == D01_ENV), None)
    print("- 슬롯 C D01 태그:", [(t["path"], t["kind"]) for t in d01t["kept"]] if d01t else "없음")
    print("- 슬롯 B D01 새 필드에 quantity_on_hand:", "quantity_on_hand" in rc.get(D01_SEED, {}).get("new_fields", []),
          rc.get(D01_SEED, {}).get("new_fields"))
    print("- 슬롯 A D01 통과:", st.get(D01_SEED, {}).get("F1"), "|", st.get(D01_SEED, {}).get("order", "")[:300])
    if (OUT / "identity.json").exists():
        d = next(r for r in json.loads((OUT / "identity.json").read_text()) if r["env"] == D01_ENV)
        got = {(k["collection"], k["field"]) for k in d["kept"]}
        print("- 슬롯 D D01 §15 목록 포함:", D01_IDENTITY <= got, "빠짐", sorted(D01_IDENTITY - got))
    if st:
        print("\n## 필터 1 통과 씨앗의 상시 지시\n\n| 씨앗 | 환경 | 상시 지시 |\n|---|---|---|")
        for p, r in sorted(st.items(), key=lambda x: (not x[1]["F1"], ex_rows[x[0]]["env"])):
            o = r["order"] or "(불통) " + "; ".join(sorted({w for t in r["tries"] for w in (["재현"] if not t.get("V1") else []) +
                                                           (["대상 ID"] if not t.get("V2") else []) + (["지어낸 조건"] if not t.get("V3") else [])}))
            print(f"| {p} | {ex_rows[p]['env']} | {' '.join(o.split())[:200]} |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["tags", "exec", "reach", "stand", "ident", "c8", "report"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--m", type=int, default=2)
    a = ap.parse_args()
    S.load_cache()
    {"tags": step_tags, "exec": step_exec, "reach": step_reach, "stand": step_stand, "ident": step_ident,
     "c8": step_c8, "report": step_report}[a.step](a)


if __name__ == "__main__":
    main()
