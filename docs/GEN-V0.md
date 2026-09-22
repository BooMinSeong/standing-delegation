# 생성기 v0 (기계 v2): 최소쌍 상태를 프로그램으로 뽑는다

기록 2026-09-20. 지위: **폐기된 생성기 조건("기계 v2")의 실측 기록이다**(D-037). 본 실험의 생성기는 `docs/GEN-ALGO.md`의 변수·변형이고, 이 표는 그것과 대조할 재료로 남긴다. 입력은 위임문 q, 환경 초기 상태, `schema.py` 셋뿐이고 LLM을 쓰지 않는다. 숨은 규칙 R·규칙 유형·섭동표를 입력받지 않으며 "이 위임이 그 필드를 읽을 것인가"를 판단하지 않는다(`docs/DATA-GEN.md` §6 규칙 5). 코드는 지웠다 — 재현은 `git show 882d095:src/gen/minimal_pairs.py`와 `git show 882d095:scripts/gen_v0.py`, 상태는 `data/delegations/D01/states/gen-v0/`와 `data/gen-v0/`에 있다. **어떤 모델도 이 상태들을 돌리지 않았다.**

`docs/DATA-GEN.md` §6의 검증 기준대로 둘을 봤다. (1) D01에 적용해 CASE-D01의 여덟 상태가 나오는가 — 사후 맞춤이므로 약한 검사. (2) 다른 씨앗 하나(항공 예약)에 적용해 쓸 만한 상태가 나오는가 — 진짜 검사.

## 1. 절차

| 단계 | 규칙 | R을 보는가 |
|---|---|---|
| A 닻 | 상태의 문자열 값 중 q에 그대로 나타나는 것을 가진 레코드. ID꼴 필드 값(`PROD-001`, `JFK`)이거나, 숫자·공백을 품거나 대문자로 시작하는 값만(`New York`, `2026-05-20`). `active`·`cans` 같은 일반 소문자 단어는 닻이 아니다 | 아니오 |
| B 도달 | 닻에서 ID꼴 필드(`*_id`, `*_code`, `*_number`) 값을 공유하는 레코드로 닫힘. 컬렉션을 좁히지 않는다 | 아니오 |
| C 언급 | 필드 이름 토큰이 q 토큰과 어간이 같으면 문자 언급(○). `price`↔prices, `available_quantity`↔availability, `ordering_permitted`↔permits ordering. 함축·부재는 여기서 가르지 않는다(판정기의 일) | 아니오 |
| D 필드 편집 | bool 뒤집기 / 언급 int는 q의 수 N에 대해 N−1·N·N×5 / 미언급 int는 0·×10(달력 정수는 ±1) / 언급 float은 후보끼리 동률·근소차 / 미언급 float ×0.1·×10 / 날짜 ±1년 / 문자열은 같은 필드의 다른 값으로 교체, 문자열 속 수는 q의 단위어("100 cans"의 cans)가 붙은 수에만 N·N+1 | 아니오 |
| E 구조 편집 | 도달 레코드가 2개 이상인 컬렉션(후보 집합)에 단독 후보 / 각각 부족(전부 N−1) / 합쳐도 부족(전부 N÷3) / 정확히 충족(첫 레코드 = N) / 기준 간 충돌(한 수치 필드 오름차순에 다른 수치 필드를 오름·내림차순 재배정) | 아니오 |
| F 등급 | tier 1 = 후보 컬렉션과 닻 개체 레코드의 수치·bool 편집과 구조 편집. tier 2 = 문자열 교체, 날짜, 중첩 항목. 비용 통제용 기계 규칙 | 아니오 |
| G 검사 | 기준 상태와 같거나 이미 나온 상태는 버린다. 환경이 상태를 적재하고 인자 없는 조회 툴이 도는지 확인 | — |

ID·이름·연락처 필드는 편집하지 않는다. 값 풀이 하나뿐인 문자열도 편집하지 않는다.

## 2. D01 (조달, D− 판): 51차원, tier 1 26

닻: PROD-001을 가진 레코드 10개(카탈로그·재고·업체 목록 3·계약 3·판매·정품). 도달 컬렉션 6. q의 수: 100 (단위어 cans).

| # | 컬렉션 | 템플릿 | 필드 | 언급 | tier | 바뀐 것 |
| P01 | authenticity_records | 풀 교체(문자열) | brand | ✗ | 2 | authenticity_records[0].brand: 'Coca-Cola'→'Lays' |
| P02 | authenticity_records | 풀 교체(문자열) | official_identifier | ✗ | 2 | authenticity_records[0].official_identifier: 'CC-US-355-SINGLE-2026'→'DC-US-355-SINGLE-2026' |
| P03 | authenticity_records | 풀 교체(문자열) | packaging_signature | ✗ | 2 | authenticity_records[0].packaging_signature: 'Red can with white Coca-Cola script'→'Silver can with red Diet Coke lettering' |
| P04 | catalog_products | 풀 교체(문자열) | brand | ✗ | 2 | catalog_products[0].brand: 'Coca-Cola'→'Lays' |
| P05 | catalog_products | 풀 교체(문자열) | package_details | ✗ | 2 | catalog_products[0].package_details: '355ml aluminum can, single can'→'355ml aluminum can, 24-pack case' |
| P06 | catalog_products | 풀 교체(문자열) | ingredients | ✗ | 2 | catalog_products[0].ingredients: 'Carbonated water, high fructose corn syrup, caramel color, phosphoric acid, natural flavors, caffeine'→'Carbonated water, caramel color, phosphoric acid, aspartame, potassium benzoate, natural flavors, citric acid, caffeine' |
| P07 | catalog_products | 풀 교체(문자열) | allergen_info | ✗ | 2 | catalog_products[0].allergen_info: 'Contains no major allergens. Manufactured in a facility that also processes milk products.'→'Contains no major allergens.' |
| P08 | catalog_products | 풀 교체(문자열) | category | ✗ | 2 | catalog_products[0].category: 'Beverages'→'Snacks' |
| P09 | inventory_items | 값 갈림(미언급 int) | quantity_on_hand | ✗ | 1 | inventory_items[0].quantity_on_hand: 42→0 |
| P10 | inventory_items | 값 갈림(미언급 int) | quantity_on_hand | ✗ | 1 | inventory_items[0].quantity_on_hand: 42→420 |
| P11 | inventory_items | 풀 교체(문자열) | unit | ○ | 2 | inventory_items[0].unit: 'cans'→'cases' |
| P12 | inventory_items | 풀 교체(문자열) | location | ✗ | 2 | inventory_items[0].location: 'Warehouse A, Row 3, Shelf 2'→'Warehouse A, Row 3, Shelf 4' |
| P13 | inventory_items | 뒤집기 | counterfeit_flag | ✗ | 1 | inventory_items[0].counterfeit_flag: False→True |
| P14 | inventory_items | 풀 교체(문자열) | handling_notes | ✗ | 2 | inventory_items[0].handling_notes: 'Store at room temperature, away from direct sunlight.'→'Handle with care, fragile packaging.' |
| P15 | sales_history | 값 갈림(달력 int ±1) | year | ✗ | 2 | sales_history[0].year: 2025→2024 |
| P16 | sales_history | 값 갈림(달력 int ±1) | year | ✗ | 2 | sales_history[0].year: 2025→2026 |
| P17 | sales_history | 경계(언급 int) | units_sold | ○ | 1 | sales_history[0].units_sold: 4200→99 |
| P18 | sales_history | 경계(언급 int) | units_sold | ○ | 1 | sales_history[0].units_sold: 4200→100 |
| P19 | sales_history | 경계(언급 int) | units_sold | ○ | 1 | sales_history[0].units_sold: 4200→500 |
| P20 | sales_history | 값 갈림(미언급 float) | revenue | ✗ | 1 | sales_history[0].revenue: 5040.0→504.0 |
| P21 | sales_history | 값 갈림(미언급 float) | revenue | ✗ | 1 | sales_history[0].revenue: 5040.0→50400.0 |
| P22 | sales_history | 값 갈림(달력 int ±1) | monthly_breakdown[0].month | ✗ | 2 | sales_history[0].monthly_breakdown[0].month: 1→0 |
| P23 | sales_history | 값 갈림(달력 int ±1) | monthly_breakdown[0].month | ✗ | 2 | sales_history[0].monthly_breakdown[0].month: 1→2 |
| P24 | sales_history | 경계(언급 int) | monthly_breakdown[0].units_sold | ○ | 2 | sales_history[0].monthly_breakdown[0].units_sold: 300→99 |
| P25 | sales_history | 경계(언급 int) | monthly_breakdown[0].units_sold | ○ | 2 | sales_history[0].monthly_breakdown[0].units_sold: 300→100 |
| P26 | sales_history | 경계(언급 int) | monthly_breakdown[0].units_sold | ○ | 2 | sales_history[0].monthly_breakdown[0].units_sold: 300→500 |
| P27 | sales_history | 값 갈림(미언급 float) | monthly_breakdown[0].revenue | ✗ | 2 | sales_history[0].monthly_breakdown[0].revenue: 360.0→36.0 |
| P28 | sales_history | 값 갈림(미언급 float) | monthly_breakdown[0].revenue | ✗ | 2 | sales_history[0].monthly_breakdown[0].revenue: 360.0→3600.0 |
| P29 | supplier_contracts | 뒤집기 | active | ○ | 1 | supplier_contracts[0].active: True→False |
| P30 | supplier_contracts | 값 갈림(미언급 날짜) | start_date | ✗ | 2 | supplier_contracts[0].start_date: '2026-01-01'→'2025-01-01' |
| P31 | supplier_contracts | 값 갈림(미언급 날짜) | start_date | ✗ | 2 | supplier_contracts[0].start_date: '2026-01-01'→'2027-01-01' |
| P32 | supplier_contracts | 값 갈림(미언급 날짜) | end_date | ✗ | 2 | supplier_contracts[0].end_date: '2026-12-31'→'2025-12-31' |
| P33 | supplier_contracts | 값 갈림(미언급 날짜) | end_date | ✗ | 2 | supplier_contracts[0].end_date: '2026-12-31'→'2027-12-31' |
| P34 | supplier_contracts | 뒤집기 | ordering_permitted | ○ | 1 | supplier_contracts[0].ordering_permitted: True→False |
| P35 | supplier_contracts | 풀 교체(문자열) | restrictions | ✗ | 2 | supplier_contracts[0].restrictions: 'Standard beverage replenishment terms.'→'Orders accepted in quantities of 50 cans or more.' |
| P36 | supplier_contracts | 문자열 속 수 경계(단위 일치) | restrictions | ✗ | 1 | supplier_contracts[0].restrictions: 'Standard beverage replenishment terms.'→'Orders accepted in quantities of 100 cans or more.' |
| P37 | supplier_contracts | 문자열 속 수 경계(단위 일치) | restrictions | ✗ | 1 | supplier_contracts[0].restrictions: 'Standard beverage replenishment terms.'→'Orders accepted in quantities of 101 cans or more.' |
| P38 | supplier_contracts | 단독 후보 | — | ○ | 1 | supplier_contracts: 3→1 (첫 레코드만) |
| P39 | supplier_listings | 동률(언급 float) | price | ○ | 1 | supplier_listings[1].price: 0.75→0.72 |
| P40 | supplier_listings | 근소차(언급 float) | price | ○ | 1 | supplier_listings[1].price: 0.75→0.7272 |
| P41 | supplier_listings | 경계(언급 int) | available_quantity | ○ | 1 | supplier_listings[0].available_quantity: 80→99 |
| P42 | supplier_listings | 경계(언급 int) | available_quantity | ○ | 1 | supplier_listings[0].available_quantity: 80→100 |
| P43 | supplier_listings | 경계(언급 int) | available_quantity | ○ | 1 | supplier_listings[0].available_quantity: 80→500 |
| P44 | supplier_listings | 값 갈림(미언급 int) | lead_time_days | ✗ | 1 | supplier_listings[0].lead_time_days: 2→0 |
| P45 | supplier_listings | 값 갈림(미언급 int) | lead_time_days | ✗ | 1 | supplier_listings[0].lead_time_days: 2→20 |
| P46 | supplier_listings | 단독 후보 | — | ○ | 1 | supplier_listings: 3→1 (첫 레코드만) |
| P47 | supplier_listings | 각각 부족(전부 N-1) | available_quantity | ○ | 1 | available_quantity: 전부 99 |
| P48 | supplier_listings | 합쳐도 부족(전부 N//3) | available_quantity | ○ | 1 | available_quantity: 전부 33 |
| P49 | supplier_listings | 기준 간 충돌(desc) | price×available_quantity | ○ | 1 | price 오름차순에 available_quantity 를 내림차순 재배정 |
| P50 | supplier_listings | 기준 간 충돌(desc) | price×lead_time_days | ○ | 1 | price 오름차순에 lead_time_days 를 내림차순 재배정 |
| P51 | supplier_listings | 기준 간 충돌(desc) | available_quantity×price | ○ | 1 | available_quantity 오름차순에 price 를 내림차순 재배정 |

재생 검사 51/51 통과.

### 2.1 CASE-D01의 여덟 상태가 나오는가

대응은 조율자의 판단이고 사후 맞춤이다. 값까지 같지는 않다(예: R2는 두 업체 모두 500개 가용, 생성 동률은 80/500).

| CASE-D01 상태 | 대응하는 생성 템플릿 | 차원 |
|---|---|---|
| R1 단독 업체 | 단독 후보 (supplier_listings) | P46 |
| R2 가격 동률 | 동률(언급 float) price | P39 |
| R3 각각 60, 합쳐 120 | 각각 부족(전부 N-1) | P47 |
| R4 싼데 느림 | 기준 간 충돌 price×lead_time_days | P50 |
| R5 재고 450 | 값 갈림 quantity_on_hand ×10 | P10 |
| R6 가용량 딱 100 | 경계(언급 int) available_quantity = N | P42 |
| R7 최저가에 200개 제한 | 문자열 속 수 경계 restrictions (N, N+1) | P36, P37 |
| R8 40+45, 합쳐도 85 | 합쳐도 부족(전부 N//3) | P48 |

여덟 자리 모두 tier 1 차원에 대응한다. `docs/DATA-GEN.md` §4.1이 "양쪽 생성기가 구조적으로 못 만든다"고 한 R5(재고)가 P10으로 나온 것은 범위를 후보 컬렉션으로 좁히지 않았기 때문이다.

### 2.2 읽을 때 볼 것

- **잘못 걸린 언급.** `sales_history.units_sold`가 q의 "unit prices"와 어간이 겹쳐 언급(○)으로 잡혔다. 그래서 판매량에 99·100·500 경계가 걸렸다(P17~19). 기계 규칙의 거짓 양성이고 언급 등급 판정기가 부재로 되돌릴 자리다.
- **의미 없는 편집.** 카탈로그의 브랜드를 Lays로, 카테고리를 Snacks로 바꾸는 것(P04·P08)은 값 풀 규칙이 낸 것이다. tier 2다.
- **tier 1 26은 계획의 "위임당 약 12"보다 많다.** 기준 1 + 26을 k=5·모델 3으로 돌리면 위임당 약 405런, 파일럿 위임 4면 약 1620런이다(`Plan.md` §7 어림 720). 잘라 낼지, tier 1을 다 돌릴지는 저자가 정한다.

## 3. 항공 예약 (conflicting_constraints/preview_023, D− 판): 37차원, tier 1 23

두 번째 씨앗. 환경·스키마가 다르고 후보(`flights`)의 핵심 값이 중첩 필드(`cabins[0].fare`)에 있다. q에서 "lowest-price "만 지웠다(`data/gen-v0/flight_preview_023.q_plus.txt`). 닻: 사용자 ID, 공항 3(JFK·LGA·SEA, New York·Seattle), 2026-05-20의 항공편 5, 결제 수단. q의 수: 3 ("3 checked bags").

| # | 컬렉션 | 템플릿 | 필드 | 언급 | tier | 바뀐 것 |
| P01 | airports | 풀 교체(문자열) | city | ✗ | 2 | airports[0].city: 'New York'→'Seattle' |
| P02 | airports | 뒤집기 | is_international | ✗ | 1 | airports[0].is_international: True→False |
| P03 | airports | 뒤집기 | is_accessible | ✗ | 1 | airports[0].is_accessible: True→False |
| P04 | airports | 값 갈림(미언급 int) | distance_rank_by_city.New York | ✗ | 1 | airports[0].distance_rank_by_city.New York: 1→0 |
| P05 | airports | 값 갈림(미언급 int) | distance_rank_by_city.New York | ✗ | 1 | airports[0].distance_rank_by_city.New York: 1→10 |
| P06 | airports | 단독 후보 | — | ○ | 1 | airports: 3→1 (첫 레코드만) |
| P07 | flights | 풀 교체(문자열) | origin | ✗ | 2 | flights[0].origin: 'JFK'→'LGA' |
| P08 | flights | 값 갈림(미언급 날짜) | date | ✗ | 2 | flights[0].date: '2026-05-20'→'2025-05-20' |
| P09 | flights | 값 갈림(미언급 날짜) | date | ✗ | 2 | flights[0].date: '2026-05-20'→'2027-05-20' |
| P10 | flights | 경계(언급 int) | stops | ○ | 1 | flights[0].stops: 1→2 |
| P11 | flights | 경계(언급 int) | stops | ○ | 1 | flights[0].stops: 1→3 |
| P12 | flights | 경계(언급 int) | stops | ○ | 1 | flights[0].stops: 1→15 |
| P13 | flights | 값 갈림(미언급 float) | cabins[0].fare | ✗ | 1 | flights[0].cabins[0].fare: 210.0→21.0 |
| P14 | flights | 값 갈림(미언급 float) | cabins[0].fare | ✗ | 1 | flights[0].cabins[0].fare: 210.0→2100.0 |
| P15 | flights | 값 갈림(미언급 int) | cabins[0].available_seats | ✗ | 1 | flights[0].cabins[0].available_seats: 5→0 |
| P16 | flights | 값 갈림(미언급 int) | cabins[0].available_seats | ✗ | 1 | flights[0].cabins[0].available_seats: 5→50 |
| P17 | flights | 풀 교체(문자열) | cabins[0].fare_class | ✗ | 2 | flights[0].cabins[0].fare_class: 'E'→'Y' |
| P18 | flights | 단독 후보 | — | ○ | 1 | flights: 5→1 (첫 레코드만) |
| P19 | flights | 각각 부족(전부 N-1) | stops | ○ | 1 | stops: 전부 2 |
| P20 | flights | 합쳐도 부족(전부 N//3) | stops | ○ | 1 | stops: 전부 1 |
| P21 | flights | 기준 간 충돌(asc) | stops×cabins[0].fare | ○ | 1 | stops 오름차순에 cabins[0].fare 를 오름차순 재배정 |
| P22 | flights | 기준 간 충돌(desc) | stops×cabins[0].fare | ○ | 1 | stops 오름차순에 cabins[0].fare 를 내림차순 재배정 |
| P23 | flights | 기준 간 충돌(asc) | stops×cabins[0].available_seats | ○ | 1 | stops 오름차순에 cabins[0].available_seats 를 오름차순 재배정 |
| P24 | flights | 기준 간 충돌(desc) | stops×cabins[0].available_seats | ○ | 1 | stops 오름차순에 cabins[0].available_seats 를 내림차순 재배정 |
| P25 | payment_instruments | 풀 교체(문자열) | type | ✗ | 2 | payment_instruments[0].type: 'credit_card'→'travel_certificate' |
| P26 | payment_instruments | 풀 교체(문자열) | brand | ✗ | 2 | payment_instruments[0].brand: 'Visa'→'AirlineCredit' |
| P27 | payment_instruments | 풀 교체(문자열) | last4 | ✗ | 2 | payment_instruments[0].last4: '7447'→'0120' |
| P28 | payment_instruments | 값 갈림(미언급 float) | balance | ✗ | 1 | payment_instruments[0].balance: 5000.0→500.0 |
| P29 | payment_instruments | 값 갈림(미언급 float) | balance | ✗ | 1 | payment_instruments[0].balance: 5000.0→50000.0 |
| P30 | payment_instruments | 뒤집기 | is_default | ✗ | 1 | payment_instruments[0].is_default: True→False |
| P31 | payment_instruments | 단독 후보 | — | ○ | 1 | payment_instruments: 3→1 (첫 레코드만) |
| P32 | traveler_profiles | 값 갈림(미언급 날짜) | date_of_birth | ✗ | 2 | traveler_profiles[0].date_of_birth: '1992-04-11'→'1991-04-11' |
| P33 | traveler_profiles | 값 갈림(미언급 날짜) | date_of_birth | ✗ | 2 | traveler_profiles[0].date_of_birth: '1992-04-11'→'1993-04-11' |
| P34 | traveler_profiles | 값 갈림(미언급 날짜) | passport_expiry | ✗ | 2 | traveler_profiles[0].passport_expiry: '2031-04-10'→'2030-04-10' |
| P35 | traveler_profiles | 값 갈림(미언급 날짜) | passport_expiry | ✗ | 2 | traveler_profiles[0].passport_expiry: '2031-04-10'→'2032-04-10' |
| P36 | traveler_profiles | 값 갈림(미언급 날짜) | documents[0].expiry_date | ✗ | 2 | traveler_profiles[0].documents[0].expiry_date: '2031-04-10'→'2030-04-10' |
| P37 | traveler_profiles | 값 갈림(미언급 날짜) | documents[0].expiry_date | ✗ | 2 | traveler_profiles[0].documents[0].expiry_date: '2031-04-10'→'2032-04-10' |

환경 코드를 적재하지 않았으므로 재생 검사는 하지 않았다(스키마 순서·타입만 읽음).

### 3.1 읽을 때 볼 것

- **후보 집합과 구조 템플릿이 그대로 서는가.** 항공편 5개가 후보로 잡혔고 단독 후보(P18), 좌석 부족, 경유 횟수와 운임의 충돌(P21·P22)이 나왔다. "최저가"를 지운 판이므로 운임(`cabins[0].fare`)은 미언급이고 ×0.1·×10 갈림(P13·P14)이 걸렸다. 조달의 단가 자리와 같은 모양이다.
- **q의 수 3이 엉뚱한 필드에 걸렸다.** "3 checked bags"의 3이 경유 횟수(`stops`)에 N−1·N·N×5 경계로 걸렸다(P10~12, P19·P20). 언급 int에 q의 모든 수를 거는 규칙의 한계다. 단위어("bags")와 필드를 잇는 규칙이 없다.
- **말로 된 수는 못 읽는다.** "at most one stop", "exactly 3"의 one·exactly를 보지 않는다.
- **공항 단독 후보(P06)는 목적지 SEA를 지운다.** 구조 템플릿이 조인된 레코드를 함께 정리하지 않으므로 여정이 성립하지 않는 상태가 나온다. 기계 규칙이 내는 무의미한 상태의 예다.

## 4. 판정 (DATA-GEN §6 "나오면 규칙, 안 나오면 직관")

D01에서는 여덟 자리가 전부 나왔다. 항공에서는 후보 집합·경계·충돌·부족이 같은 규칙으로 나왔고, 대신 q의 수 대응과 조인 정리에서 무의미한 상태가 섞였다. 규칙은 서지만 걸러 낼 것이 있다. 걸러 내는 기준은 두 갈래다. 프로그램으로(단위어–필드 대응, 조인 정리) 또는 사람이 표를 읽고(지금 이 문서). 후자는 "저자 설계"와의 경계가 흐려진다.

## 5. v0의 한계

- 등급(tier)은 비용 통제용 기계 규칙이고 자리의 중요도가 아니다.
- 문자열 속 수 경계는 q의 단위어가 바로 뒤에 붙은 수에만 걸린다. 단위 없는 수("100")는 걸리지 않는다.
- 언급 int에 q의 모든 수를 건다. 단위어와 필드를 잇지 않는다.
- 단독 후보는 그 컬렉션만 줄인다. 조인된 레코드(지워진 업체의 계약)는 남는다.
- 중첩 목록은 첫 항목(`[0]`)만 편집한다.
- 언급은 문자 대조뿐이다. 함축·부재는 판정기가 가른다(`Plan.md` §5).
- 기준 상태는 씨앗의 초기 상태다. 다른 기준 상태에서는 다른 차원이 나온다.
