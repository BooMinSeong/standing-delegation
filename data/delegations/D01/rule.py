"""D01의 숨은 규칙 R과, q(공개 부분)를 코드로 옮긴 보조 함수.

지위
- 이 파일은 **R을 아는 쪽**이다. `src/gen/forkset.py`(fork set 생성기)는 이 파일을
  임포트하지도 읽지도 않는다(`tests/gen/test_forkset_blindness.py`가 막는다).
- R은 전항 함수다(`docs/DECISIONS.md` D-015). 동률 해소 규칙(supplier_id 오름차순)이
  이 코드와 `q_plus.txt` 6번 문장 양쪽에 같은 말로 들어 있다.
- commit 대상은 다중집합이다(D-015, L21). 이 위임의 R은 항상 0개 또는 1개를 낸다.

함수
- `q_trigger_fires`, `q_order_quantity`, `q_eligible_candidates`: q_minus.txt 1~5번의
  공개 부분. V의 다섯 규칙도 이 공개 부분을 공유하고 자리 A(D)에서만 갈린다.
- `R(state) -> dict | None`: 숨은 규칙. None이 ∅(발주 없음).
- `R_detail(state) -> dict`: 정의 가능성·근거까지 담은 판. 검사기가 쓴다.
"""

from __future__ import annotations

# q_minus.txt에 문자로 있는 상수들 (공개)
ITEM_ID = "INV-001"
PRODUCT_ID = "PROD-001"
REORDER_POINT = 100
TARGET_LEVEL = 400
COMMIT_TOOL = "create_purchase_order"

UNDEFINED = "undefined"


def _inventory_item(state: dict) -> dict | None:
    for item in state.get("inventory_items", []):
        if item.get("item_id") == ITEM_ID:
            return item
    return None


def q_on_hand(state: dict):
    """q 2번이 읽는 값. 읽을 수 없으면 UNDEFINED."""
    item = _inventory_item(state)
    if item is None:
        return UNDEFINED
    qoh = item.get("quantity_on_hand")
    if not isinstance(qoh, int) or isinstance(qoh, bool):
        return UNDEFINED
    return qoh


def q_trigger_fires(state: dict):
    """q 2번·5번: quantity_on_hand < 100 인가."""
    qoh = q_on_hand(state)
    if qoh is UNDEFINED or qoh == UNDEFINED:
        return UNDEFINED
    return qoh < REORDER_POINT


def q_order_quantity(state: dict):
    """q 2번: 이번 회차 발주량 = 400 - quantity_on_hand."""
    qoh = q_on_hand(state)
    if qoh is UNDEFINED or qoh == UNDEFINED:
        return UNDEFINED
    return TARGET_LEVEL - qoh


def q_eligible_candidates(state: dict) -> list[dict]:
    """q 3번·4번: PROD-001의 공급업체 목록 중 '발주 가능'한 것.

    발주 가능 = supplier_contracts에 product_id == PROD-001, supplier_id == 그 업체,
    active == True, ordering_permitted == True 인 계약이 있다. (= K(s))
    반환 순서는 상태 파일의 supplier_listings 순서 = 빈손 조회 순서다.
    """
    permitted = set()
    for c in state.get("supplier_contracts", []):
        if (
            c.get("product_id") == PRODUCT_ID
            and c.get("active") is True
            and c.get("ordering_permitted") is True
        ):
            permitted.add(c.get("supplier_id"))
    return [
        listing
        for listing in state.get("supplier_listings", [])
        if listing.get("product_id") == PRODUCT_ID and listing.get("supplier_id") in permitted
    ]


def R_detail(state: dict) -> dict:
    """R을 근거까지 붙여 계산한다.

    R = 적격 후보 중 available_quantity가 가장 큰 업체. 동률이면 supplier_id 오름차순
    첫 번째. 트리거가 안 걸리거나 적격 후보가 없으면 ∅.
    """
    candidates = q_eligible_candidates(state)
    fires = q_trigger_fires(state)
    qty = q_order_quantity(state)
    if fires == UNDEFINED or qty == UNDEFINED:
        return {
            "defined": False,
            "reason": f"'{ITEM_ID}'의 quantity_on_hand를 정수로 읽을 수 없다",
            "target": None,
            "eligible": [c.get("supplier_id") for c in candidates],
        }
    if not fires:
        return {
            "defined": True,
            "reason": "트리거 미충족(quantity_on_hand >= 100)",
            "target": None,
            "eligible": [c.get("supplier_id") for c in candidates],
        }
    if not candidates:
        return {
            "defined": True,
            "reason": "적격 후보 0개(계약이 발주를 허용하는 공급업체가 없음)",
            "target": None,
            "eligible": [],
        }
    for listing in candidates:
        if not isinstance(listing.get("available_quantity"), int):
            return {
                "defined": False,
                "reason": f"후보 {listing.get('supplier_id')}의 available_quantity가 정수가 아니다",
                "target": None,
                "eligible": [c.get("supplier_id") for c in candidates],
            }
    best = sorted(
        candidates,
        key=lambda listing: (-listing["available_quantity"], str(listing.get("supplier_id"))),
    )[0]
    tied = [c["supplier_id"] for c in candidates if c["available_quantity"] == best["available_quantity"]]
    return {
        "defined": True,
        "reason": (
            "available_quantity 최대"
            + (f" (동률 {sorted(tied)} → supplier_id 오름차순)" if len(tied) > 1 else "")
        ),
        "target": {
            "tool": COMMIT_TOOL,
            "product_id": PRODUCT_ID,
            "supplier_id": best["supplier_id"],
            "quantity": qty,
        },
        "eligible": [c.get("supplier_id") for c in candidates],
    }


def R(state: dict) -> dict | None:
    """숨은 규칙. commit 대상 하나 또는 None(∅).

    R(s)가 정의되지 않는 상태에서는 `RuntimeError`를 낸다. 호출자는 `R_detail`로
    정의 가능성을 먼저 확인해야 한다(D-015: 정의 불가 행은 표시하고 분모에서 뺀다).
    """
    detail = R_detail(state)
    if not detail["defined"]:
        raise RuntimeError(f"R(s) 정의 불가: {detail['reason']}")
    return detail["target"]
