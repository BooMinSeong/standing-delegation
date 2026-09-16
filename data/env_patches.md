# 환경 코드 패치 목록

원본(`/home3/b.ms/projects/standing-delegation/data/agentabstain-data/environments/<env>/`)은 고치지
않는다. 고쳐야 할 것은 `data/envs/<env>/`로 복사해 그쪽만 고치고, 여기에 diff 요지를 남긴다.
근거: `.claude/agents/delegation-author.md`("쓰는 환경의 조회 도구에서 죽은 가지를 찾아 고치고
목록을 남긴다"), v1 `AGENTABSTAIN.md` §6·§12.6("환경 버그 수정은 §8이 금지한 '재료에 없는 조건
추가'가 아니다").

재현: `diff -u <원본>/environment.py data/envs/store_procurement_and_inventory/environment.py`

## store_procurement_and_inventory (2026-09-16, D01)

사본: `data/envs/store_procurement_and_inventory/{__init__.py, environment.py, schema.py}`.
`schema.py`는 원본과 바이트 단위로 같다(diff 없음). 로딩은 `PYTHONPATH=<repo>/data`에
`from envs.store_procurement_and_inventory.environment import StoreProcurementAndInventoryEnvironment`.

| # | 도구 | 고친 것 | 이유 |
|---|---|---|---|
| PATCH-00 | (임포트) | `from abstention_factory.environments...schema import` → `from .schema import` | 사본을 패키지로 돌리기 위한 것. 동작 변화 없음 |
| PATCH-01 | `search_suppliers` | 카탈로그 상품명 대조 가지를 바깥 `if` 밖으로 끌어냈다 | 죽은 가지였다. 바깥 조건이 질의어가 `supplier_name`이나 `supplier_sku`의 부분문자열이기를 먼저 요구해서, 상품명으로는 절대 도달하지 못했다(v1 §6·§11.6). 실측: 원본은 `query='Coca-Cola Classic 355ml Can'`에 **0행**, 패치는 **3행**(checks.md (g)) |
| PATCH-02 | `search_suppliers` 독스트링 | 예시 질의 `'canned Coke'` → `'Coca-Cola'`, "인자 없이 부르면 전부"를 추가 | 독스트링이 광고한 질의가 0행을 낸다. 부분문자열 대조라 `'canned Coke'`는 `'Coca-Cola Classic 355ml Can'`의 부분문자열이 아니다. 대조 방식(토큰화·유사도)은 **바꾸지 않았다** — 그것은 죽은 가지 수정이 아니라 기능 추가다. 패치 뒤에도 `'canned Coke'`는 0행이다 |

### 고치지 않고 기록만 한 것

| 도구 | 관찰 | 왜 그대로 두는가 |
|---|---|---|
| `create_purchase_order` | 없는 `product_id`·`supplier_id`를 그대로 받아 발주를 발행한다(`QQQQ1234`/`QQQQ5678` 실측 성공). 가용 수량·계약도 읽지 않아 가용 80에 9999 발주가 성공한다 | v1 §11.5의 "존재 검사 없는 commit 24개"에 이 도구가 있고, v2의 delegation-author 규격은 이것을 **고치라고 하지 않고 `meta.yaml`에 `self_correction: false`로 기록하라고 한다**(O26·D-019는 자기 교정 기회를 분석 축으로 쓴다). 고치면 이 축의 24 대 84 대비가 사라진다. v1 §6은 "셋 다 고치라"고 했으나 v2 규격을 따랐다 — **저자 확인 필요** |
| `search_store_catalog` | 부분문자열 대조라 `'Coke'`가 Diet Coke까지 낸다 | 거짓 음성(죽은 가지)이 아니라 과다 일치다. D01은 상품을 ID로 지목하고 분기 개체는 `search_suppliers()` 빈손 조회로 전부 나오므로 이 경로에 의존하지 않는다 |
| `verify_supplier_contracts` | `supplier_id`를 주지 않으면 `contracts[0]`만 돌려준다(상품에 계약이 여럿이어도) | 재료에 있는 동작이고, D01의 q는 "공급업체별로 계약을 확인"하게 쓰여 있어 모델이 `supplier_id`를 주고 부르면 정확히 답한다. 인자 없이 부른 결과로 판단하면 틀리는데, 그것 자체가 관찰 대상이다 |
