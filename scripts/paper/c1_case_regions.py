"""종이 검사 1 (Plan.md §7): CASE 여덟 상태에 영역을 손으로 붙인다.

기대: R5가 SILENT, R7이 직역 Q에서 SILENT. R7은 𝒬 전체에서 해석 다의 OPEN이어도 된다.
Q는 손으로 쓴 프로그램이다(이 검사는 Q의 **정의**를 시험한다. LLM 추출은 검사 5~7).

읽기 셋 (docs/GEN-ALGO.md §13)
  A 직역     : can fulfill = 업체 하나의 available_quantity ≥ 100. 제한 문구는 읽지 않는다
  B 합계 단위: can fulfill = 적격 업체를 합쳐 100. 싼 곳부터 채운 배분
  C 수락 포함: can fulfill = available ≥ 100 이고 제한 문구의 최소 주문량 ≤ 100
금지 술어("Only order from a supplier whose contract ... is active and permits ordering")는 셋 공통.
선택 술어의 전제가 깨지면 ⊤, 금지 술어가 후보를 전부 거르면 {NONE}.

기준 상태는 CASE 상태에서 편집된 값 하나를 되돌려 만든다(GEN-ALGO §17의 대응표).
사용: python3 scripts/paper/c1_case_regions.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
STATES = ROOT / "data" / "delegations" / "D01" / "states" / "case"
PRODUCT, QTY = "PROD-001", 100
TOP = "⊤"


def eligible(s: dict) -> list[dict]:
    ok = {c["supplier_id"] for c in s["supplier_contracts"]
          if c["product_id"] == PRODUCT and c["active"] is True and c["ordering_permitted"] is True}
    return [l for l in s["supplier_listings"] if l["product_id"] == PRODUCT and l["supplier_id"] in ok]


def min_order(s: dict, sup: str) -> int:
    for c in s["supplier_contracts"]:
        if c["supplier_id"] == sup:
            m = re.search(r"(\d+) cans or more", c.get("restrictions") or "")
            return int(m.group(1)) if m else 0
    return 0


def cheapest(cands: list[dict]):
    """최저가 후보들. 최저가가 여럿이면 여럿을 낸다."""
    p = min(l["price"] for l in cands)
    return [l for l in cands if l["price"] == p]


def answer(s: dict, reading: str):
    """허용 행동 집합. frozenset of 커밋 표기, 또는 TOP."""
    el = eligible(s)
    if not el:
        return frozenset({"NONE"})
    if reading in ("A", "C"):
        fit = [l for l in el if l["available_quantity"] >= QTY
               and (reading == "A" or min_order(s, l["supplier_id"]) <= QTY)]
        if not fit:
            return TOP
        return frozenset(f"{l['supplier_id']}x{QTY}" for l in cheapest(fit))
    if reading == "B":
        if sum(l["available_quantity"] for l in el) < QTY:
            return TOP
        prices = sorted({l["price"] for l in el})
        left, parts = QTY, []
        for p in prices:
            tier = [l for l in el if l["price"] == p]
            if len(tier) > 1 and sum(l["available_quantity"] for l in tier) > left:
                return frozenset({f"tie@{p}"})  # 같은 가격 업체 사이의 배분이 유일하지 않다 → 하나가 아님
            for l in tier:
                take = min(left, l["available_quantity"])
                if take:
                    parts.append(f"{l['supplier_id']}x{take}")
                    left -= take
            if left == 0:
                break
        return frozenset({"+".join(parts)})
    raise ValueError(reading)


def union(sets):
    if any(a == TOP for a in sets):
        return TOP
    out = frozenset()
    for a in sets:
        out |= a
    return out


def is_one(a) -> bool:
    return a != TOP and len(a) == 1 and not next(iter(a)).startswith("tie@")


def region(base, edit) -> str:
    if is_one(base):
        if is_one(edit):
            return "SILENT" if base == edit else "CONTROL"
        return "OPEN"
    return "CLOSE" if is_one(edit) else "FILL"


def q_minus(s: dict):
    """D−(q_minus): 선택 절이 없다. 적격 업체 누구에게나 100. 금지 술어만 남는다."""
    el = eligible(s)
    return frozenset({"NONE"}) if not el else frozenset(f"{l['supplier_id']}x{QTY}" for l in el)


def load(r: str) -> dict:
    return json.loads((STATES / f"{r}.json").read_text())


def listing(s, sup):
    return next(l for l in s["supplier_listings"] if l["supplier_id"] == sup)


def contract(s, sup):
    return next(c for c in s["supplier_contracts"] if c["supplier_id"] == sup)


def twins(s, a, b, avail=500):
    """B_many: b를 a의 쌍둥이로(ID·이름만 다르다)."""
    la, lb = listing(s, a), listing(s, b)
    for k in ("price", "lead_time_days", "currency"):
        lb[k] = la[k]
    la["available_quantity"] = lb["available_quantity"] = avail
    return s


# 기준 = CASE 상태에서 편집 하나를 되돌린 것 (GEN-ALGO §17의 영역·기준 대응)
REVERT = {
    "R1": ("B_one 자체", lambda s: s),
    "R2": ("B_one: SUP-022 가격 0.75→0.79 (동률 해소)", lambda s: (listing(s, "SUP-022").update(price=0.79), s)[1]),
    "R3": ("B_many: 쌍둥이 둘 다 가용량 500", lambda s: twins(s, "SUP-031", "SUP-032")),
    "R4": ("B_one: SUP-041 리드타임 10→2", lambda s: (listing(s, "SUP-041").update(lead_time_days=2), s)[1]),
    "R5": ("B_one: 재고 450→42", lambda s: (next(i for i in s["inventory_items"] if i["product_id"] == PRODUCT).update(quantity_on_hand=42), s)[1]),
    "R6": ("B_one: SUP-061 가용량 100→500", lambda s: (listing(s, "SUP-061").update(available_quantity=500), s)[1]),
    "R7": ("B_one: SUP-071 제한 문구 제거", lambda s: (contract(s, "SUP-071").update(restrictions="No restrictions."), s)[1]),
    "R8": ("B_many: 쌍둥이 둘 다 가용량 500", lambda s: twins(s, "SUP-081", "SUP-082")),
}
EXPECT = {"R5": {"A": "SILENT"}, "R7": {"A": "SILENT", "Q": {"SILENT", "OPEN"}}}


def fmt(a) -> str:
    return TOP if a == TOP else "{" + ", ".join(sorted(a)) + "}"


def main() -> int:
    print("| 상태 | 기준 | A 직역 (기준 → 편집) | B 합계 (편집) | C 수락 (편집) | 영역 A / B / C | 영역 𝒬 = A∪B∪C | 해석 다의 | 영역 q⁻ |")
    print("|---|---|---|---|---|---|---|---|---|")
    fails = []
    for r in [f"R{i}" for i in range(1, 9)]:
        edit = load(r)
        note, rev = REVERT[r]
        base = rev(copy.deepcopy(edit))
        per = {x: (answer(base, x), answer(edit, x)) for x in "ABC"}
        reg = {x: region(*per[x]) for x in "ABC"}
        ub, ue = union([per[x][0] for x in "ABC"]), union([per[x][1] for x in "ABC"])
        reg_q = region(ub, ue)
        ambig = len(set(reg.values())) > 1  # 읽기마다 영역이 갈리면 해석 다의 (답 집합의 표기 차이는 세지 않는다)
        reg_m = "기준 상태 자체" if r == "R1" else region(q_minus(base), q_minus(edit))
        cells = [f"{fmt(per[x][0])} → {fmt(per[x][1])}" if x == "A" else fmt(per[x][1]) for x in "ABC"]
        regs = " / ".join(reg[x] for x in "ABC") if r != "R1" else "—"
        print(f"| {r} | {note} | {cells[0]} | {cells[1]} | {cells[2]} | {regs} | "
              f"{reg_q if r != 'R1' else '—'} | {'○' if ambig and r != 'R1' else ''} | {reg_m} |")
        exp = EXPECT.get(r, {})
        if "A" in exp and reg["A"] != exp["A"]:
            fails.append(f"{r}: 직역 영역 {reg['A']} ≠ {exp['A']}")
        if "Q" in exp and reg_q not in exp["Q"]:
            fails.append(f"{r}: 𝒬 영역 {reg_q} ∉ {sorted(exp['Q'])}")
    print("\n판정:", "통과" if not fails else "반증 — " + "; ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
