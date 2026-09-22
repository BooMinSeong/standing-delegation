"""종이 검사 5~7의 상태 배터리 (D01).

씨앗 초기 상태, CASE 여덟, GEN-V0 D01 편집 상태(base + P01~P51), 그리고 씨앗에서 한 값씩 바꾼 변형 열.
변형은 R3·R8·R7형과 영역 경계(동률, 합계가 정확히 100, 전부 비활성, 답 업체 탈락)를 덮는다.
사용: python3 scripts/paper/c567_battery.py → data/paper-checks/c567/battery.json
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import aa  # noqa: E402

D01 = aa.ROOT / "data" / "delegations" / "D01"
OUT = aa.ROOT / "data" / "paper-checks" / "c567"
SEED_PAIR = "emergent_risk_discovery/preview_018"


def seed_state() -> dict:
    s = next(x for x in aa.seeds() if x["pair_id"] == SEED_PAIR)
    return aa.initial_state(s)


def _lst(s, sup):
    return next(l for l in s["supplier_listings"] if l["supplier_id"] == sup and l["product_id"] == "PROD-001")


def _con(s, sup):
    return next(c for c in s["supplier_contracts"] if c["supplier_id"] == sup and c["product_id"] == "PROD-001")


def variants(seed: dict) -> dict[str, dict]:
    def v(f):
        s = copy.deepcopy(seed)
        f(s)
        return s
    avail = lambda d: (lambda s: [_lst(s, k).update(available_quantity=q) for k, q in d.items()])  # noqa: E731
    return {
        "V01_all_short_sum_ok": v(avail({"SUP-001": 60, "SUP-002": 60, "SUP-003": 30})),       # R3형
        "V02_all_short_sum_short": v(avail({"SUP-001": 30, "SUP-002": 30, "SUP-003": 30})),    # R8형
        "V03_exact_sum_unique_split": v(avail({"SUP-001": 60, "SUP-002": 40, "SUP-003": 0})),  # D-041 경계
        "V04_answer_min_order_200": v(lambda s: _con(s, "SUP-002").update(restrictions="Orders accepted in quantities of 200 cans or more.")),  # R7형
        "V05_answer_min_order_50": v(lambda s: _con(s, "SUP-002").update(restrictions="Orders accepted in quantities of 50 cans or more.")),
        "V06_tie_among_fulfillers": v(lambda s: _lst(s, "SUP-003").update(price=0.75)),        # R2형
        "V07_all_inactive": v(lambda s: [c.update(active=False) for c in s["supplier_contracts"]]),
        "V08_answer_inactive": v(lambda s: _con(s, "SUP-002").update(active=False)),
        "V09_answer_ordering_forbidden": v(lambda s: _con(s, "SUP-002").update(ordering_permitted=False)),
        "V10_answer_avail_60": v(avail({"SUP-002": 60})),
        "V11_stock_450": v(lambda s: next(i for i in s["inventory_items"] if i["product_id"] == "PROD-001").update(quantity_on_hand=450)),
        "V12_cheapest_avail_exact_100": v(avail({"SUP-001": 100})),                            # R6형
        "V13_answer_lead_20": v(lambda s: _lst(s, "SUP-002").update(lead_time_days=20)),      # R4형
    }


def build() -> dict[str, dict]:
    seed = seed_state()
    bat = {"seed": seed}
    for p in sorted((D01 / "states" / "case").glob("R*.json")):
        bat[f"case_{p.stem}"] = json.loads(p.read_text())
    for p in sorted((D01 / "states" / "gen-v0").glob("*.json")):
        if p.stem == "manifest":
            continue
        bat[f"gv0_{p.stem}"] = json.loads(p.read_text())
    bat.update(variants(seed))
    return bat


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    b = build()
    (OUT / "battery.json").write_text(json.dumps(b, ensure_ascii=False))
    print(len(b), "states →", OUT / "battery.json")
