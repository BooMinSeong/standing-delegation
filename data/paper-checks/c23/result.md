후보/딸린 컬렉션: {'D01': (['supplier_listings'], ['purchase_orders', 'supplier_contracts']), '항공': (['flights', 'payment_instruments', 'traveler_profiles'], ['orders', 'reservations', 'visa_applications'])}

## 검사 2
| 판 | # | 바뀐 것 | 기각 규칙 | I= 변형 | 재생 | 조회 | 무의미 목록 | §10 범위 |
|---|---|---|---|---|---|---|---|---|
| D01 | P01 | authenticity_records[0].brand: 'Coca-Cola'→'Lays' | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P02 | authenticity_records[0].official_identifier: 'CC-US-355-SINGLE-2026'→' | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P03 | authenticity_records[0].packaging_signature: 'Red can with white Coca- | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P04 | catalog_products[0].brand: 'Coca-Cola'→'Lays' | I: catalog_products.brand (같은 키 PROD-001) | I=: catalog_products.brand (같은 키 PROD-001) | ○ | ○ | 닻 식별 속성(브랜드 → Lays) | 범위 밖 |
| D01 | P05 | catalog_products[0].package_details: '355ml aluminum can, single can'→ | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P06 | catalog_products[0].ingredients: 'Carbonated water, high fructose corn | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P07 | catalog_products[0].allergen_info: 'Contains no major allergens. Manuf | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P08 | catalog_products[0].category: 'Beverages'→'Snacks' | I: catalog_products.category (같은 키 PROD-001) | I=: catalog_products.category (같은 키 PROD-001) | ○ | ○ | 닻 식별 속성(분류 → Snacks) | 범위 밖 |
| D01 | P09 | inventory_items[0].quantity_on_hand: 42→0 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P10 | inventory_items[0].quantity_on_hand: 42→420 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P11 | inventory_items[0].unit: 'cans'→'cases' | 통과 |  | ○ | ○ |  | 단위·통화(§4) |
| D01 | P12 | inventory_items[0].location: 'Warehouse A, Row 3, Shelf 2'→'Warehouse  | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P13 | inventory_items[0].counterfeit_flag: False→True | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P14 | inventory_items[0].handling_notes: 'Store at room temperature, away fr | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P15 | sales_history[0].year: 2025→2024 | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P16 | sales_history[0].year: 2025→2026 | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P17 | sales_history[0].units_sold: 4200→99 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P18 | sales_history[0].units_sold: 4200→100 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P19 | sales_history[0].units_sold: 4200→500 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P20 | sales_history[0].revenue: 5040.0→504.0 | 통과 |  | ○ | ○ | 범위: revenue | 범위 밖 |
| D01 | P21 | sales_history[0].revenue: 5040.0→50400.0 | 통과 |  | ○ | ○ | 범위: revenue | 범위 밖 |
| D01 | P22 | sales_history[0].monthly_breakdown[0].month: 1→0 | V: monthly_breakdown[].month=0 (month 1..12) |  | ○ | ○ | 월 0 | 범위 밖 |
| D01 | P23 | sales_history[0].monthly_breakdown[0].month: 1→2 | 통과 |  | ○ | ○ |  | 범위 밖 |
| D01 | P24 | sales_history[0].monthly_breakdown[0].units_sold: 300→99 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P25 | sales_history[0].monthly_breakdown[0].units_sold: 300→100 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P26 | sales_history[0].monthly_breakdown[0].units_sold: 300→500 | 통과 |  | ○ | ○ |  | 3차 |
| D01 | P27 | sales_history[0].monthly_breakdown[0].revenue: 360.0→36.0 | 통과 |  | ○ | ○ | 범위: monthly revenue | 범위 밖 |
| D01 | P28 | sales_history[0].monthly_breakdown[0].revenue: 360.0→3600.0 | 통과 |  | ○ | ○ | 범위: monthly revenue | 범위 밖 |
| D01 | P29 | supplier_contracts[0].active: True→False | 통과 |  | ○ | ○ |  | 1차 |
| D01 | P30 | supplier_contracts[0].start_date: '2026-01-01'→'2025-01-01' | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P31 | supplier_contracts[0].start_date: '2026-01-01'→'2027-01-01' | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P32 | supplier_contracts[0].end_date: '2026-12-31'→'2025-12-31' | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P33 | supplier_contracts[0].end_date: '2026-12-31'→'2027-12-31' | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P34 | supplier_contracts[0].ordering_permitted: True→False | 통과 |  | ○ | ○ |  | 1차 |
| D01 | P35 | supplier_contracts[0].restrictions: 'Standard beverage replenishment t | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P36 | supplier_contracts[0].restrictions: 'Standard beverage replenishment t | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P37 | supplier_contracts[0].restrictions: 'Standard beverage replenishment t | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P38 | supplier_contracts: 3→1 (첫 레코드만) | 통과 |  | ○ | — |  |  |
| D01 | P39 | supplier_listings[1].price: 0.75→0.72 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P40 | supplier_listings[1].price: 0.75→0.7272 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P41 | supplier_listings[0].available_quantity: 80→99 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P42 | supplier_listings[0].available_quantity: 80→100 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P43 | supplier_listings[0].available_quantity: 80→500 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P44 | supplier_listings[0].lead_time_days: 2→0 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P45 | supplier_listings[0].lead_time_days: 2→20 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P46 | supplier_listings: 3→1 (첫 레코드만) | K: supplier_contracts.supplier_id=SUP-002 → supplier_listings 없음; K: supplier_contracts.supplier_id=SUP-003 → supplier_listings 없음 |  | ○ | — | 단독 후보 뒤 남은 계약(FK 연쇄) |  |
| D01 | P47 | available_quantity: 전부 99 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P48 | available_quantity: 전부 33 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P49 | price 오름차순에 available_quantity 를 내림차순 재배정 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P50 | price 오름차순에 lead_time_days 를 내림차순 재배정 | 통과 |  | ○ | ○ |  | 2차 |
| D01 | P51 | available_quantity 오름차순에 price 를 내림차순 재배정 | 통과 |  | ○ | ○ |  | 2차 |
| 항공 | P01 | airports[0].city: 'New York'→'Seattle' | I: airports.city (같은 키 JFK) | I=: airports.city (같은 키 JFK) | ○ | ○ |  |  |
| 항공 | P02 | airports[0].is_international: True→False | 통과 |  | ○ | ○ |  |  |
| 항공 | P03 | airports[0].is_accessible: True→False | 통과 |  | ○ | ○ |  |  |
| 항공 | P04 | airports[0].distance_rank_by_city.New York: 1→0 | 통과 |  | ○ | ○ |  |  |
| 항공 | P05 | airports[0].distance_rank_by_city.New York: 1→10 | 통과 |  | ○ | ○ |  |  |
| 항공 | P06 | airports: 3→1 (첫 레코드만) | C: airports 3→1 (후보 컬렉션 아님) |  | ○ | — | 공항 3→1로 목적지 삭제 |  |
| 항공 | P07 | flights[0].origin: 'JFK'→'LGA' | 통과 | I=: flights.origin (같은 키 flt_jfk_sea_1205_1stop) | ○ | ○ |  |  |
| 항공 | P08 | flights[0].date: '2026-05-20'→'2025-05-20' | 통과 | I=: flights.date (같은 키 flt_jfk_sea_1205_1stop) | ○ | ○ |  |  |
| 항공 | P09 | flights[0].date: '2026-05-20'→'2027-05-20' | 통과 | I=: flights.date (같은 키 flt_jfk_sea_1205_1stop) | ○ | ○ |  |  |
| 항공 | P10 | flights[0].stops: 1→2 | Q: stops 단위 ['stops'] ≠ q 상수 'bags' |  | ○ | ○ | q 상수 3(bags)을 stops에 |  |
| 항공 | P11 | flights[0].stops: 1→3 | Q: stops 단위 ['stops'] ≠ q 상수 'bags' |  | ○ | ○ | q 상수 3(bags)을 stops에 |  |
| 항공 | P12 | flights[0].stops: 1→15 | Q: stops 단위 ['stops'] ≠ q 상수 'bags' |  | ○ | ○ | q 상수 3(bags)을 stops에 |  |
| 항공 | P13 | flights[0].cabins[0].fare: 210.0→21.0 | 통과 |  | ○ | ○ |  |  |
| 항공 | P14 | flights[0].cabins[0].fare: 210.0→2100.0 | 통과 |  | ○ | ○ |  |  |
| 항공 | P15 | flights[0].cabins[0].available_seats: 5→0 | 통과 |  | ○ | ○ |  |  |
| 항공 | P16 | flights[0].cabins[0].available_seats: 5→50 | 통과 |  | ○ | ○ |  |  |
| 항공 | P17 | flights[0].cabins[0].fare_class: 'E'→'Y' | 통과 |  | ○ | ○ |  |  |
| 항공 | P18 | flights: 5→1 (첫 레코드만) | 통과 |  | ○ | — |  |  |
| 항공 | P19 | stops: 전부 2 | Q: stops 단위 ['stops'] ≠ q 상수 'bags'; Q: stops 단위 ['stops'] ≠ q 상수 'bags'; Q: stops 단위 ['stops'] ≠ q 상수 'bags'; Q: stops 단위 ['stops'] ≠ q 상수 'bags' |  | ○ | ○ | q 상수 3(bags)을 stops에(N−1) |  |
| 항공 | P20 | stops: 전부 1 | Q: stops 단위 ['stops'] ≠ q 상수 'bags'; Q: stops 단위 ['stops'] ≠ q 상수 'bags'; Q: stops 단위 ['stops'] ≠ q 상수 'bags'; Q: stops 단위 ['stops'] ≠ q 상수 'bags' |  | ○ | ○ | q 상수 3(bags)을 stops에(N//3) |  |
| 항공 | P21 | stops 오름차순에 cabins[0].fare 를 오름차순 재배정 | 통과 |  | ○ | ○ |  |  |
| 항공 | P22 | stops 오름차순에 cabins[0].fare 를 내림차순 재배정 | 통과 |  | ○ | ○ |  |  |
| 항공 | P23 | stops 오름차순에 cabins[0].available_seats 를 오름차순 재배정 | 통과 |  | ○ | ○ |  |  |
| 항공 | P24 | stops 오름차순에 cabins[0].available_seats 를 내림차순 재배정 | 통과 |  | ○ | ○ |  |  |
| 항공 | P25 | payment_instruments[0].type: 'credit_card'→'travel_certificate' | 통과 |  | ○ | ○ |  |  |
| 항공 | P26 | payment_instruments[0].brand: 'Visa'→'AirlineCredit' | 통과 |  | ○ | ○ |  |  |
| 항공 | P27 | payment_instruments[0].last4: '7447'→'0120' | 통과 |  | ○ | ○ |  |  |
| 항공 | P28 | payment_instruments[0].balance: 5000.0→500.0 | 통과 |  | ○ | ○ |  |  |
| 항공 | P29 | payment_instruments[0].balance: 5000.0→50000.0 | 통과 |  | ○ | ○ |  |  |
| 항공 | P30 | payment_instruments[0].is_default: True→False | 통과 |  | ○ | ○ |  |  |
| 항공 | P31 | payment_instruments: 3→1 (첫 레코드만) | 통과 |  | ○ | — |  |  |
| 항공 | P32 | traveler_profiles[0].date_of_birth: '1992-04-11'→'1991-04-11' | 통과 |  | ○ | ○ |  |  |
| 항공 | P33 | traveler_profiles[0].date_of_birth: '1992-04-11'→'1993-04-11' | 통과 |  | ○ | ○ |  |  |
| 항공 | P34 | traveler_profiles[0].passport_expiry: '2031-04-10'→'2030-04-10' | 통과 |  | ○ | ○ |  |  |
| 항공 | P35 | traveler_profiles[0].passport_expiry: '2031-04-10'→'2032-04-10' | 통과 |  | ○ | ○ |  |  |
| 항공 | P36 | traveler_profiles[0].documents[0].expiry_date: '2031-04-10'→'2030-04-1 | 통과 |  | ○ | ○ |  |  |
| 항공 | P37 | traveler_profiles[0].documents[0].expiry_date: '2031-04-10'→'2032-04-1 | 통과 |  | ○ | ○ |  |  |

D01: 편집 51, 무의미 4 중 기각 4 ['P04', 'P08', 'P22', 'P46'], 놓침 [], 무의미 목록 밖 기각 0 []

항공: 편집 37, 무의미 6 중 기각 6 ['P06', 'P10', 'P11', 'P12', 'P19', 'P20'], 놓침 [], 무의미 목록 밖 기각 1 ['P01']

## 검사 3
| 상태 | 기각 규칙 | I= 변형 | 재생 | 조회 | 비고 |
|---|---|---|---|---|---|
| CASE R1 | 통과 |  | ○ | ○ |  |
| CASE R2 | 통과 |  | ○ | ○ |  |
| CASE R3 | 통과 |  | ○ | ○ |  |
| CASE R4 | 통과 |  | ○ | ○ |  |
| CASE R5 | 통과 |  | ○ | ○ |  |
| CASE R6 | 통과 |  | ○ | ○ |  |
| CASE R7 | 통과 |  | ○ | ○ |  |
| CASE R8 | 통과 |  | ○ | ○ |  |
| 할당 01 CONTROL B_one: 답 업체 계약 비활성 | 통과 |  | ○ | ○ |  |
| 할당 02 CONTROL B_one: 답 업체 가용량 60 | 통과 |  | ○ | ○ |  |
| 할당 03 CLOSE B_many: 쌍둥이 한쪽 계약 비활성 | 통과 |  | ○ | ○ |  |
| 할당 04 OPEN B_one: SUP-003 가격 0.75 (동률) (R2) | 통과 |  | ○ | ○ |  |
| 할당 05 OPEN B_one: 후보 업체 0 (FK 연쇄 삭제) | 통과 |  | ○ | — |  |
| 할당 06 FILL B_many: 쌍둥이 둘 다 가용량 60 (R3) | 통과 |  | ○ | ○ |  |
| 할당 07 FILL B_many: 쌍둥이 둘 다 가용량 40 (R8) | 통과 |  | ○ | ○ |  |
| 할당 08 SILENT B_one: 답 업체 가용량 = 100 (R6) | 통과 |  | ○ | ○ |  |
| 할당 09 SILENT B_one: 답 업체 리드타임 3→10 (R4) | 통과 |  | ○ | ○ |  |
| 할당 10 SILENT B_one: 답 업체 계약 만료일 2025-12-31 (active 그대로) | 통과 |  | ○ | ○ | 실행 시각 패치 없음 |
| 할당 11 SILENT B_one: 답 업체 제한 문구: 200캔 이상 (R7) | 통과 |  | ○ | ○ |  |
| 할당 12 SILENT B_one: 재고 450 (R5) | 통과 |  | ○ | ○ |  |
| 할당 13 SILENT B_one: 지난 실행의 미입고 발주 100 | 통과 |  | ○ | ✗ [None, False] | 자기 커밋 읽기 패치 없음 |

검사 3 판정: 통과
