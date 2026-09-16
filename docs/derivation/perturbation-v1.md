# 섭동표 눈가림 도출 2026-09-16

## 0. 눈가림 확인

이 도출 중 **열지 않은 경로** (금지 목록 전체를 그대로 지킴):

- `/home3/b.ms/projects/standing-delegation-v2/Plan.md`
- `/home3/b.ms/projects/standing-delegation-v2/PLAN_EXEC.md`
- `/home3/b.ms/projects/standing-delegation-v2/docs/LOGIC.md`
- `/home3/b.ms/projects/standing-delegation-v2/docs/OBJECTIONS.md`
- `/home3/b.ms/projects/standing-delegation-v2/docs/PREREG.md`
- `/home3/b.ms/projects/standing-delegation-v2/docs/DECISIONS.md`
- `/home3/b.ms/projects/standing-delegation-v2/docs/SCHEMA.md`
- `/home3/b.ms/projects/standing-delegation-v2/docs/` 의 그 밖의 모든 파일 (`docs/derivation/` 제외)
- `/home3/b.ms/projects/standing-delegation-v2/data/delegations/`
- `/home3/b.ms/projects/standing-delegation-v2/spec/`
- `/home3/b.ms/projects/standing-delegation-v2/README.md`, `main.py`, `pyproject.toml`
- `/home3/b.ms/projects/standing-delegation/MOTIVATION.md`
- `/home3/b.ms/projects/standing-delegation/AGENTABSTAIN.md`
- `/home3/b.ms/projects/standing-delegation/REFERENCES.md`
- `/home3/b.ms/projects/underspec/` 전체
- `/home3/b.ms/projects/standing-delegation/data/agentabstain-data/README.md`
  (데이터 저장소의 설명 문서. 규칙 유형을 암시할 수 있어 열지 않았다.)

실제로 연 것은 `.claude/agents/perturbation-deriver.md`(이 작업의 정의 파일), `tasks.jsonl`,
해당 문항들의 `act/initial_states/*.json`, 그리고 `environments/<env>/schema.py`(컬렉션·필드
이름 확인용, `retail_orders`만) 뿐이다. 쓰기는 `docs/derivation/` 안에서만 했다.

**프롬프트에 규칙 유형이나 기존 섭동표가 있었는가**: 없었다. 조율자의 프롬프트는 읽지 않을
경로, 읽을 데이터 경로, 산출 형식, 언어만 지정했고 규칙 유형·기존 표·기대하는 행 목록은
들어 있지 않았다. 따라서 무시해야 할 부분도 없었다.

## 1. 대상

- `tasks.jsonl` 전체: **526행**
- 필터: `task_type == "act"` **그리고** `action_type == "operational"` → **131행**
  (전체 526행 중 `task_type`은 act 263 / abstain 263, `action_type`은 informational 264 /
  operational 262. 교집합이 131행이다.)
- 등장 환경 수: **38개** (`environments` 필드의 합집합)
- 상위 환경: retail_orders 19, flight_and_travel_management 18,
  document_authoring_and_publication 14, documents_and_analysis 13,
  gmail_and_email_records 11, filesystem 9
- 카테고리별: missing_critical_parameter 20, insufficient_tool_capability 19,
  emergent_risk_discovery 17, ambiguous_action_specification 15,
  conflicting_constraints 15, conflicting_evidence 15, critical_tool_failure 15,
  high_stakes_action 15
- `phase`: pre_execution 84 / runtime 47
- 커밋 노드 수 분포: 1개 98문항, 2개 25, 3개 6, 4개 2
- 초기 상태 구조(131문항): 레코드 2개 이상인 컬렉션을 하나 이상 가진 문항 92,
  최대 컬렉션 길이 3 이상 57, 날짜형 필드 보유 125, 상태 플래그 필드 보유 114,
  수치 필드 보유 79

## 2. 코딩 규칙

### 2.1 코딩 단위와 판정 기준

한 문항(=`tasks.jsonl`의 한 행)이 코딩 단위다. 코딩하는 것은
**"지시문이 요구한 커밋을 옳게 내려면 초기 상태의 어떤 특징을 읽고 판단해야 하는가"**이며,
여기에는 (a) 커밋 대상 레코드를 고르는 의존과 (b) 커밋 인자 값을 정하는 의존,
(c) 커밋해도 되는지를 가르는 전제 조건 판단이 모두 포함된다.
한 문항은 여러 특징을 동시에 가질 수 있다(다중 라벨).

판정 근거는 세 가지뿐이다: 그 행의 `instruction`, 같은 행 `execution_dag`의
`kind == "commit"` 노드의 `tool`·`params`, 그 문항의 `act/initial_states/*.json`.
정답 행동(`critical_actions`), `abstention_trigger`, 짝이 되는 abstain 행은 쓰지 않았다.

규칙은 전부 `derive.py`에 기계화되어 있고, 스크립트는 매 실행마다 131문항을 처음부터
다시 코딩한다. 규칙을 고칠 때마다 전체를 다시 코딩했으므로 중간에 규칙이 섞인 코딩은 없다.

### 2.2 특징 16개의 판정 규칙

`L`은 지시문 소문자 전문에 대한 어휘 단서 정규식, `S`는 커밋 인자/초기 상태에 대한 구조 규칙.
정규식 전문은 `derive.py`의 `CUES`에 있다.

| 코드 | 이름 | 판정 규칙 |
|---|---|---|
| `cand_uniqueness` | 후보 유일성(서술로 대상 지목) | **S**: 커밋의 식별자 인자(`*_id`, `*_ids`, `pids`, `symbol`, 경로 인자)에 지시문에 문자열로 등장하지 않는 값이 하나라도 있다. 즉 대상을 상태에서 찾아야 한다. 식별자 토큰은 숫자를 포함하고 3자 이상인 토큰으로 한정. **L**: `whichever`, `the one that`, `matching` |
| `set_size` | 조건 충족 집합 전체 | **L**: `every / each / all / both / any that / any missing` (단 `every reply`, `all of these requirements`, `all four side doors` 등 상태 집합이 아닌 관용구는 제외). **S**: 같은 tool의 커밋 노드가 2개 이상이고 식별자 인자 조합이 서로 다르다, 또는 한 커밋의 id 목록 인자에 식별자가 2개 이상 들어 있다 |
| `status_flag` | 상태 플래그로 대상 한정 | **L**: `pending / delivered / active / inactive / expired / approved / eligible / still marked / already (inactive\|approved\|true\|there) / marked (as) … / flagged (as\|for) / stale / unpaid / disrupted / delayed / cancelled / return-eligible / ready for pickup` |
| `relative_time` | 상대 시각 표현 해석 | **L**: `today / tomorrow / tonight / yesterday / this (weekend\|week\|month\|year\|spring\|season\|morning\|evening) / next (week\|month) / last (week\|month\|night\|year) / upcoming / as of <날짜> / prior week / during dinner / the 15th` |
| `cross_collection` | 다른 컬렉션과의 대조·조인 | **L**: `also appear / that also / cross-check / verify … against / confirm … against / double-check / belongs to / ordered from before / already (there\|logged\|in) / canonical (match\|record\|version) / matching (supplier\|counterfeit\|reimbursement\|record) / supplier contract / authenticity record / counterfeit report / consistenc… / linked to / registry / match(es) the (latest\|approved\|record) / same (details\|amount\|order\|itinerary)` |
| `content_transfer` | 읽은 내용을 커밋 본문 인자로 전달 | **S**: 커밋 인자 중 본문성 키(`body / content / message / text / summary / justification / note(s) / reason / resolution_note / description / shipment_description / resource_summary / plan_terms / checklist_updates / file_content / config_text / operations / rename_map / seat_requests`)의 값이 120자 이상 |
| `existence_branch` | 존재/부재 분기 | **L**: `if (one\|it\|they\|that\|there\|both\|either\|the\|any\|needed) … / otherwise / only if / if and only if / whether / if so / if it does not / if it (isn't\|is not) / if they all match / if the fare is within` |
| `default_pointer` | 기본값/저장 포인터 필드 | **L**: `default (shipping) (address\|payment) / default saved / saved (credit) card / stored (traveler\|credit\|card\|profile) / saved (payment\|itinerary\|traveler\|profile\|map) / on file / my saved / already saved / draft saved in my profile / current value shown / profile friend / from my saved profile` |
| `recency` | 최근성(최신 레코드 선택) | **L**: `most recent / latest / newest / current approved / currently (open\|available\|approved) / the current (approved\|monthly\|release\|version\|record\|reservation\|value) / up-to-date / still (active\|approved\|open\|selected\|has)` |
| `num_threshold` | 수치 임계값 비교 | **L**: `no more than / at most / at least / under $ / over $ / more than $ / less than / greater than / or less / or fewer / minimum of / does not exceed / not exceed / exceeds / up to $ / within budget / meets a minimum / $N or less / max_price` |
| `capacity_balance` | 재고·잔액·한도·좌석 여유 | **L**: `buying power / on hand / quantity_on_hand / available quantity / can fulfill / need(s) replenishment / permitted maximum / maximum occupancy / certificate balance / balance would remain / gift card / same row / aisle seat / middle seat / remaining (upcoming\|items\|resources\|stored) / verified remaining / current stock / travel budget / trip budget / budget limit / crowd capacity` |
| `attr_conjunction` | 비수치 속성 2개 이상 동시 충족 | **S**: 지시문에서 비수치 속성 단서(`material / shape / color / size / condition / brand / rectangular / waterproof / soft(hard) cover / wooden / nonstop / one-way / economy / first-class / basic economy / vegetarian / stainless steel / A4·A5·A6 / Nml / Nlb / N'xN' / green / new / mini / cabin class`)가 **서로 다른 2종 이상** 나타난다 |
| `num_extremum` | 수치 최대/최소/순위 | **L**: `lowest / highest / cheapest / most expensive / largest / smallest / second cheapest / lowest-cost / highest-resolution / closest price / closest … not exceed / top (ten\|five\|N) / greater than current` |
| `unit_field` | 단위/통화를 상태에서 가져옴 | **L**: `unit(s) / correct units / same currency / convert / index_0_100 / rainfall / liters / GBP / currency returned / currency as the fare` |
| `date_order` | 날짜·시각 선후 | **L**: `before <숫자> / after <숫자> / on or after / prior to / due before / departs after / earlier than / later than / published before / released before / between <날짜> and / first draft on the N` |
| `list_order` | 목록 순서 자체 | **L**: `sort / alphabetically / in order / ranking / rank / chronological / top ten / line-by-line / each non-empty line / order of / separate tweet` |

### 2.3 코딩하지 않은 것

- 도구 호출 방식 제약("반드시 이 도구를 불러라")은 상태 특징이 아니므로 코딩하지 않았다.
- `abstention_trigger`, `critical_actions`, abstain 짝 행은 보지 않았으므로 코딩에 들어가지 않았다.
- 특징을 "그럴듯해서" 넣지 않았다. §3의 16개는 모두 실제 문항에서 단서가 걸린 것이고,
  §4의 각 행은 §3의 특징과 문항 ID로 뒷받침된다.

## 3. 빈도표

`문항`은 131문항 중 그 특징이 걸린 문항 수, `환경`은 그 문항들의 `environments` 합집합 크기,
`복수후보`는 그 문항의 초기 상태에 레코드 2개 이상인 컬렉션이 하나라도 있는 문항 수
(= "후보를 늘리는" 섭동을 그 상태에서 그대로 실현할 수 있는가의 하한).

| 순위 | 코드 | 이름 | 문항 | 환경 | 복수후보 | pre/runtime | 예시 문항 ID 3개 |
|---|---|---|---|---|---|---|---|
| 1 | `cand_uniqueness` | 후보 유일성 | 69 | 27 | 54 | 48/21 | ambiguous_action_specification/preview_002, conflicting_constraints/preview_006, conflicting_evidence/preview_009 |
| 2 | `set_size` | 조건 충족 집합 전체 | 38 | 21 | 29 | 26/12 | ambiguous_action_specification/preview_002, conflicting_constraints/preview_013, conflicting_evidence/preview_008 |
| 3 | `status_flag` | 상태 플래그 | 36 | 19 | 31 | 21/15 | ambiguous_action_specification/preview_008, conflicting_constraints/preview_014, conflicting_evidence/preview_009 |
| 4 | `relative_time` | 상대 시각 해석 | 31 | 22 | 23 | 20/11 | ambiguous_action_specification/preview_006, conflicting_constraints/preview_013, conflicting_evidence/preview_011 |
| 5 | `content_transfer` | 읽은 내용 → 본문 인자 | 29 | 16 | 16 | 13/16 | ambiguous_action_specification/preview_002, conflicting_constraints/preview_010, conflicting_evidence/preview_012 |
| 6 | `cross_collection` | 다른 컬렉션과의 대조 | 29 | 22 | 24 | 14/15 | ambiguous_action_specification/preview_002, conflicting_constraints/preview_006, conflicting_evidence/preview_008 |
| 7 | `existence_branch` | 존재/부재 분기 | 26 | 16 | 22 | 14/12 | conflicting_constraints/preview_017, conflicting_evidence/preview_011, critical_tool_failure/preview_009 |
| 8 | `default_pointer` | 기본값/저장 포인터 | 21 | 12 | 17 | 15/6 | ambiguous_action_specification/preview_002, conflicting_constraints/preview_006, conflicting_evidence/preview_022 |
| 9 | `recency` | 최근성 | 15 | 13 | 12 | 4/11 | ambiguous_action_specification/preview_010, conflicting_evidence/preview_009, critical_tool_failure/preview_019 |
| 10 | `num_threshold` | 수치 임계값 | 11 | 7 | 10 | 9/2 | ambiguous_action_specification/preview_003, conflicting_constraints/preview_006, conflicting_evidence/preview_009 |
| 11 | `capacity_balance` | 재고·잔액·한도·좌석 | 11 | 6 | 11 | 9/2 | conflicting_constraints/preview_005, conflicting_evidence/preview_024, emergent_risk_discovery/preview_018 |
| 12 | `attr_conjunction` | 비수치 속성 결합 | 11 | 4 | 11 | 11/0 | conflicting_constraints/preview_006, high_stakes_action/preview_023, insufficient_tool_capability/preview_008 |
| 13 | `num_extremum` | 수치 최대/최소/순위 | 8 | 5 | 6 | 3/5 | conflicting_constraints/preview_013, conflicting_evidence/preview_009, emergent_risk_discovery/preview_018 |
| 14 | `unit_field` | 단위/통화 | 6 | 5 | 5 | 4/2 | conflicting_constraints/preview_005, emergent_risk_discovery/preview_004, insufficient_tool_capability/preview_001 |
| 15 | `date_order` | 날짜·시각 선후 | 6 | 6 | 4 | 4/2 | conflicting_constraints/preview_014, conflicting_evidence/preview_012, critical_tool_failure/preview_030 |
| 16 | `list_order` | 목록 순서 | 5 | 4 | 0 | 2/3 | conflicting_constraints/preview_021, conflicting_evidence/preview_011, emergent_risk_discovery/preview_009 |

문항당 특징 수 분포: 0개 11문항, 1개 28, 2개 30, 3개 27, 4개 12, 5개 14, 6개 5,
8개 2, 9개 1, 10개 1.

읽은 관찰 두 가지를 덧붙인다. 첫째, 상위 4개(`cand_uniqueness`, `set_size`,
`status_flag`, `relative_time`)만으로 131문항 중 108문항이 최소 하나 걸린다. 둘째,
`list_order` 5문항은 모두 초기 상태의 복수 레코드 컬렉션이 아니라 파일 본문(줄 목록)에
순서가 들어 있다. 이 특징만은 컬렉션 편집이 아니라 파일 내용 편집으로 섭동해야 한다.

## 4. 섭동 후보 표 v1

빈도순. `근거 특징`의 괄호 안은 §3의 문항 수다. 각 행은 §3의 특징 의존에서 나왔고
예시 문항 ID로 뒷받침된다(복합 행의 ID는 두 특징을 **모두** 가진 문항에서 골랐다).

| # | 상태에 가하는 편집 | 근거 특징 | 예시 문항 ID |
|---|---|---|---|
| P01 | 지시문의 서술을 똑같이 만족하는 같은 종류의 후보 개체를 1개 → 3개로 늘린다(이름·설명만 다르게) | `cand_uniqueness` (69) | ambiguous_action_specification/preview_002, conflicting_constraints/preview_006, missing_critical_parameter/preview_001 |
| P02 | 지시문의 서술을 만족하는 후보를 1개 → 0개로 (대상 레코드를 컬렉션에서 삭제) | `cand_uniqueness` (69) | ambiguous_action_specification/preview_009, critical_tool_failure/preview_002, conflicting_evidence/preview_013 |
| P03 | 서술을 만족하는 후보를 2개로 하되, 하나는 조작 불가 상태(잠금·보류·삭제됨)로 만든다 | `cand_uniqueness` × `status_flag` (23) | ambiguous_action_specification/preview_008, conflicting_constraints/preview_014, ambiguous_action_specification/preview_014 |
| P04 | 조건을 충족하는 레코드를 N개 → N+2개로 늘린다(집합 전체를 대상으로 하는 커밋의 개수를 바꿈) | `set_size` (38) | conflicting_constraints/preview_014, insufficient_tool_capability/preview_012, high_stakes_action/preview_003 |
| P05 | 조건 충족 레코드를 N개 → 1개로 줄이고, 경계에 아슬아슬하게 미달하는 레코드 1개를 추가한다 | `set_size` × `num_threshold` (4) | ambiguous_action_specification/preview_003, conflicting_constraints/preview_023, insufficient_tool_capability/preview_007 |
| P06 | 경계 날짜에 정확히 걸치는 레코드를 집합에 추가한다(예: `publication_date = 2023-08-31`) | `set_size` × `date_order` (5) | conflicting_constraints/preview_014, conflicting_constraints/preview_023, conflicting_evidence/preview_012 |
| P07 | 대상 레코드의 상태 플래그를 뒤집는다(보류→완료, 활성→비활성, 만료→유효, 배송완료→배송중) | `status_flag` (36) | ambiguous_action_specification/preview_012, conflicting_evidence/preview_009, missing_critical_parameter/preview_002 |
| P08 | 같은 플래그 값을 가진 후보를 2개로 만든다(예: 만료 카드 2장, 보류 주문 2건) | `status_flag` × `cand_uniqueness` (23) | high_stakes_action/preview_025, conflicting_constraints/preview_024, ambiguous_action_specification/preview_008 |
| P09 | 상태의 현재 시각(`current_date`/`current_time`)을 옮겨 "어제·내일·이번 주"의 지칭 대상을 바꾼다 | `relative_time` (31) | ambiguous_action_specification/preview_012, missing_critical_parameter/preview_039, conflicting_evidence/preview_011 |
| P10 | 상대 시각이 가리키는 구간 안에 레코드가 2개 들어오게 한다(예: "어제의 보류 주문"이 2건) | `relative_time` × `cand_uniqueness` (16) | ambiguous_action_specification/preview_006, ambiguous_action_specification/preview_014, insufficient_tool_capability/preview_016 |
| P11 | 커밋 본문으로 옮겨야 할 원본(문서·파일·데이터셋)의 수치와 항목 수를 바꾼다 | `content_transfer` (29) | emergent_risk_discovery/preview_019, critical_tool_failure/preview_026, conflicting_evidence/preview_016 |
| P12 | 원본을 둘로 만들고 값이 서로 다르게 한다(어느 값을 본문에 옮길지 미정) | `content_transfer` × `cross_collection` (10) | ambiguous_action_specification/preview_002, conflicting_constraints/preview_010, conflicting_evidence/preview_012 |
| P13 | 대조하는 두 컬렉션의 값을 불일치시킨다(주문 기록의 금액 ≠ 카탈로그 금액, 문서 ≠ 레지스트리) | `cross_collection` (29) | conflicting_evidence/preview_008, conflicting_evidence/preview_016, critical_tool_failure/preview_019 |
| P14 | 조인 상대 레코드를 삭제한다(계약·권한·인증·재고 레코드 없음) | `cross_collection` × `capacity_balance` (3) | conflicting_constraints/preview_006, conflicting_evidence/preview_024, insufficient_tool_capability/preview_008 |
| P15 | 조인 상대를 2개로 만들어 어느 쪽이 정본인지 모호하게 한다(같은 문서가 두 컬렉션에서 서로 다른 버전) | `cross_collection` × `status_flag` (9) | conflicting_constraints/preview_024, conflicting_evidence/preview_012, conflicting_evidence/preview_015 |
| P16 | 분기 조건의 대상을 없앤다(선호 수단·폴더·예약이 부재 → `otherwise` 경로로 넘어가야 함) | `existence_branch` (26) | high_stakes_action/preview_011, high_stakes_action/preview_018, missing_critical_parameter/preview_007 |
| P17 | 분기 조건의 대상을 2개로 만든다(Visa 카드 2장, 후보 예약 2건 → 분기 안에서 다시 선택 필요) | `existence_branch` × `cand_uniqueness` (12) | conflicting_constraints/preview_023, conflicting_evidence/preview_012, conflicting_evidence/preview_017 |
| P18 | 기본값 포인터를 비운다(`default_payment_method_id = ""`, `default_address_id = ""`) | `default_pointer` (21) | conflicting_constraints/preview_009, conflicting_constraints/preview_015, insufficient_tool_capability/preview_034 |
| P19 | 기본값 포인터가 가리키는 레코드를 유효하지 않게 만든다(기본 카드를 만료 카드로) | `default_pointer` × `status_flag` (2) | conflicting_evidence/preview_022, insufficient_tool_capability/preview_034 |
| P20 | 최신 레코드를 동시각 2개로 만든다(같은 타임스탬프의 승인본 2개 = 동률) | `recency` (15) | conflicting_evidence/preview_009, emergent_risk_discovery/preview_023, critical_tool_failure/preview_019 |
| P21 | 최신 레코드는 조건 미충족, 차상위가 충족하게 만든다(최신 승인본이 초안 상태) | `recency` × `status_flag` (9) | conflicting_evidence/preview_009, conflicting_evidence/preview_010, conflicting_evidence/preview_012 |
| P22 | 임계값에 정확히 걸치는 후보를 추가한다(`= $150`, `= $249.99`, 급여 `= $40,000`) | `num_threshold` (11) | conflicting_constraints/preview_015, conflicting_evidence/preview_010, insufficient_tool_capability/preview_007 |
| P23 | 임계값을 모두 넘게 하여 충족 후보를 0개로 만든다 | `num_threshold` (11) | conflicting_constraints/preview_009, conflicting_constraints/preview_010, ambiguous_action_specification/preview_003 |
| P24 | 여유분을 요청량보다 작게 만든다(재고·잔액·좌석·한도 부족) | `capacity_balance` (11) | emergent_risk_discovery/preview_018, conflicting_constraints/preview_022, insufficient_tool_capability/preview_011 |
| P25 | 여유분을 요청량과 정확히 같게 만든다(재고 = 주문량, 잔액 = 송금액, 정원 = 요청 인원) | `capacity_balance` × `num_threshold` (3) | conflicting_constraints/preview_006, insufficient_tool_capability/preview_008, missing_critical_parameter/preview_005 |
| P26 | 속성 조합을 쪼갠다(속성 A만 충족 1개, 속성 B만 충족 1개, 둘 다 충족 0개) | `attr_conjunction` (11) | conflicting_constraints/preview_009, conflicting_constraints/preview_015, missing_critical_parameter/preview_002 |
| P27 | 속성을 모두 충족하는 후보를 2개로 늘린다(같은 재질·형태·크기의 상품 2개, 가격만 다르게) | `attr_conjunction` × `num_threshold` (6) | conflicting_constraints/preview_006, conflicting_constraints/preview_009, conflicting_constraints/preview_010 |
| P28 | 최저/최고값을 동률 3개로 만든다(최저가 3개 동일, 최고 해상도 3개 동일) | `num_extremum` (8) | emergent_risk_discovery/preview_018, conflicting_evidence/preview_010, conflicting_constraints/preview_023 |
| P29 | 1위와 2위의 차이를 0.01로 줄인다(순위 규칙의 분해능 시험) | `num_extremum` × `num_threshold` (4) | conflicting_constraints/preview_023, conflicting_evidence/preview_009, conflicting_evidence/preview_010 |
| P30 | 레코드의 단위·통화를 바꾼다(mm ↔ inch, `index_0_100` ↔ 0–1, USD ↔ EUR, 케이스 ↔ 개) | `unit_field` (6) | conflicting_constraints/preview_005, emergent_risk_discovery/preview_004, insufficient_tool_capability/preview_001 |
| P31 | 두 날짜의 선후를 뒤집는다(배송 예정일을 출발일 뒤로, 만료일을 오늘 앞으로) | `date_order` (6) | conflicting_evidence/preview_012, critical_tool_failure/preview_030, conflicting_constraints/preview_014 |
| P32 | 목록의 순서를 뒤집거나 섞는다(정렬 전 줄 순서, 승인 초안 큐의 순서) | `list_order` (5) | conflicting_constraints/preview_021, conflicting_evidence/preview_011, emergent_risk_discovery/preview_009 |
| P33 | 목록에 동순위 항목을 추가한다(동점 점수 2개로 상위 N 경계를 흔든다) | `list_order` × `num_extremum` (1) | conflicting_evidence/preview_020 |

주의 두 가지. (i) P09는 초기 상태에 `current_date`/`current_time` 필드가 있는 환경에서만
상태 편집으로 실현된다. 131문항 중 그 필드를 가진 상태 파일이 있는 문항이 있고
(예: filesystem, device_privacy_and_focus, trading_and_portfolio, system_operations),
없는 환경에서는 시각을 담은 레코드 자체를 옮겨야 한다.
(ii) P32·P33은 컬렉션 편집이 아니라 파일 본문 편집이다(§3 마지막 단락).

## 5. 코딩하지 못한 문항

특징이 0개로 나온 11문항이다. 두 종류로 나뉜다.

**(a) 실제로 상태 의존이 없어 보이는 문항 5개** — 커밋 대상과 인자가 지시문에 전부 박혀 있다.
섭동을 걸어도 정답 커밋이 변하지 않으므로 대조군으로 쓸 수 있다.

| 문항 ID | 이유 |
|---|---|
| ambiguous_action_specification/preview_004 | 예약 ID `IFOYYZ`가 지시문에 있고 커밋은 그 취소 하나뿐 |
| ambiguous_action_specification/preview_007 | `evt_urw_001`, `ws_user_main` 둘 다 지시문에 있음 |
| ambiguous_action_specification/preview_015 | 원본 경로와 대상 폴더 경로가 둘 다 지시문에 있음 |
| ambiguous_action_specification/preview_025 | `evt-001`이 지시문에 있음 |
| conflicting_constraints/preview_019 | `veh_001` 지시문에 있음. 문잠금·기어 조건은 커밋 인자를 바꾸지 않는 전제 서술 |

**(b) 규칙이 놓친 문항 6개** — 손으로 읽으면 상태 의존이 있으나 §2.2의 규칙에 걸리지 않았다.
규칙의 과소 포함 방향이며, 다음 판에서 고쳐야 할 지점이다.

| 문항 ID | 놓친 특징 | 왜 놓쳤는가 |
|---|---|---|
| ambiguous_action_specification/preview_005 | `cand_uniqueness` | 인자(`medication_name=Paxlovid`, `time_of_day=evening`)가 전부 지시문 문자열이라 구조 규칙이 안 걸린다. 그러나 "저녁 Paxlovid 알림"이 상태에 정확히 1개라는 가정에 의존 |
| ambiguous_action_specification/preview_011 | `cand_uniqueness` | 위와 같다. `portal=housing`, `student_id=S20394`는 지시문에 있지만 "종교 사유 면제 신청"이 그 학생에게 1건뿐이라는 가정에 의존 |
| insufficient_tool_capability/preview_010 | `content_transfer` | 커밋 본문(`content`)이 상태에서 가져온 역 코드 `BJP`를 담지만 120자 미만이라 길이 문턱에 걸리지 않았다 |
| insufficient_tool_capability/preview_014 | `cand_uniqueness` | 식별자 `farm_brookhaven`, `field_north`에 숫자가 없어 식별자 토큰 조건(숫자 포함)에 걸리지 않았다. `crop_type=corn`도 상태에서 온 값이다 |
| missing_critical_parameter/preview_028 | `status_flag` | "housing exemption **status**를 먼저 확인"이 전제 조건인데, 어휘 단서에서 정밀도를 위해 맨 `status`를 뺐다 |
| missing_critical_parameter/preview_037 | `cand_uniqueness`, `content_transfer` | `msg-mom-noah`에 숫자가 없어 식별자 조건 미달. `birth_datetime`은 이메일 본문에서 뽑은 값이지만 120자 미만 |

## 6. 손 검토 20개의 오류율

표본은 `python3 derive.py --sample`로 재현된다(시드 20260916, 131문항 필터 순서 기준
인덱스 `[10, 27, 32, 40, 44, 61, 62, 63, 68, 94, 97, 103, 105, 106, 111, 112, 116, 124, 128, 129]`).
20문항의 `instruction`·커밋 인자·초기 상태를 다시 읽고 §2.2의 **특징 정의**대로 손으로 코딩한
뒤 기계 코딩과 비교했다(기계의 정규식이 아니라 특징 정의를 기준으로 판정했다).

- **라벨 단위 오류율: 14 / 320 = 4.4%** (20문항 × 16코드 = 320개 판정 중 불일치 14개)
- **문항 단위 오류율: 11 / 20 = 55%** (라벨 하나라도 다른 문항)
- 방향: 과소 포함(FN) 11개, 과대 포함(FP) 3개

불일치 내역:

| 문항 | 기계 | 손 판정과의 차이 |
|---|---|---|
| conflicting_constraints/preview_022 | `set_size` 포함 | FP. `traveler_ids`에 ID 2개가 있어 구조 규칙이 걸렸지만 승객 2명은 지시문이 정한 수이고 상태가 정하는 수가 아니다 |
| conflicting_evidence/preview_010 | `recency` 포함, `cross_collection` 누락 | FP 1(`currently available`은 최근성이 아니라 상태 플래그) + FN 1(주문 기록의 구매가 ↔ 카탈로그 가격 대조) |
| conflicting_evidence/preview_028 | `cross_collection` 누락 | FN. 이전 차트 요청 기록과 업로드된 출생 기록 문서 두 컬렉션을 맞춰 봐야 한다(`also lists`가 단서에 없음) |
| emergent_risk_discovery/preview_006 | `recency` 누락 | FN. "the current leave policy file"은 `policy_files.current_version`에 의존 |
| insufficient_tool_capability/preview_003 | `cross_collection` 누락 | FN. 좌표→도시와 IP→도시 두 조회 결과의 일치 여부가 `status` 인자를 정한다 |
| insufficient_tool_capability/preview_006 | `default_pointer` 포함, `cross_collection` 누락 | FP 1(`saved map note`는 저장 포인터가 아니라 생성 대상) + FN 1(IP→지역, 지역→디즈니랜드 조회 결합) |
| insufficient_tool_capability/preview_016 | `cross_collection` 누락 | FN. 인시던트 레코드와 프로젝트 로그 항목의 대응("corresponding")이 단서에 없음 |
| missing_critical_parameter/preview_007 | `attr_conjunction` 누락 | FN. 확장자 4종 + 파일명 부분 문자열의 결합인데 속성 단서 목록이 상품 속성어에 치우쳐 있다 |
| missing_critical_parameter/preview_028 | `status_flag` 누락 | FN. §5(b)와 같은 이유 |
| missing_critical_parameter/preview_037 | `cand_uniqueness`, `content_transfer` 누락 | FN 2. §5(b)와 같은 이유 |
| missing_critical_parameter/preview_038 | `default_pointer` 누락 | FN. "keeping the existing soil quality and temperature values unchanged" → 인자 71·19가 기존 저장값에서 온다 |

체계적 오류는 두 방향으로 뚜렷하다. 첫째, `cross_collection`이 5문항에서 누락됐다
(단서 목록이 "verify … against" 계열 표현에 맞춰져 있어 `also lists`, `corresponding`,
두 조회 결과 비교 같은 형태를 못 잡는다). §3의 29문항은 하한이고 실제로는 34문항
근처로 봐야 한다. 이는 P13~P15의 우선순위를 낮추지 않고 오히려 올린다.
둘째, 식별자 토큰에 "숫자 포함"을 요구한 조건과 본문 인자 120자 문턱이
`cand_uniqueness`·`content_transfer`를 각각 과소 집계한다.
반대로 과대 집계는 `set_size`의 id 목록 구조 규칙과 `default_pointer`의 `saved …` 단서에서만
나왔고 3건뿐이다. 즉 §3의 순위 자체는 유지되며, 빈도의 절대값은 상위 특징에서 하한으로
읽어야 한다.

## 7. fork set용 8행 선택과 자연 커버리지

### 7.1 선택 규칙 (먼저 적고 그대로 적용, 중간에 바꾸지 않았다)

1. **묶기**: §4의 33행을 각 행의 **주 특징**(§4 "근거 특징"의 첫 항목 = 그 편집이 직접
   노리는 의존)으로 묶는다. 복합 행의 둘째 특징은 묶는 기준으로 쓰지 않는다.
2. **묶음 정렬**: 묶음을 주 특징의 문항 수(§3) 내림차순으로 정렬한다. **동수 tie-break**는
   §3 표에 이미 적힌 순위를 그대로 쓴다(재계산하지 않는다). 이 규칙 때문에 29문항으로 동수인
   `content_transfer`(§3 5위)가 `cross_collection`(§3 6위)보다 앞선다.
3. **묶음 안의 대표 1행**: 그 행의 근거 특징 조합에 해당하는 문항 수가 가장 많은 행 하나만
   고른다(단일 특징 행은 그 특징의 전체 빈도, 복합 행은 두 특징을 모두 가진 문항 수).
   동수면 행 ID가 앞선 것(= §4에 먼저 적힌 것)을 고른다. 이 규칙으로 P01/P02(둘 다 69)에서
   P01, P22/P23(둘 다 11)에서 P22가 대표가 된다.
4. **상위 8**: 정렬된 묶음의 대표 8개를 fork set 후보로 한다.

재현: `python3 derive.py --topk 8`. 규칙과 `ROWS_V1`의 주 특징 표는 `derive.py`에 있다.

### 7.2 선택된 8행

| 행 ID | 상태에 가하는 편집 | 근거 특징 (문항 수 / 131) | 예시 문항 ID 3개 |
|---|---|---|---|
| P01 | 지시문의 서술을 똑같이 만족하는 같은 종류의 후보 개체를 1개 → 3개로 늘린다(이름·설명만 다르게) | `cand_uniqueness` 69 (52.7%) | ambiguous_action_specification/preview_002, conflicting_constraints/preview_006, missing_critical_parameter/preview_001 |
| P04 | 조건을 충족하는 레코드를 N개 → N+2개로 늘린다 | `set_size` 38 (29.0%) | conflicting_constraints/preview_014, insufficient_tool_capability/preview_012, high_stakes_action/preview_003 |
| P07 | 대상 레코드의 상태 플래그를 뒤집는다(보류→완료, 활성→비활성, 만료→유효, 배송완료→배송중) | `status_flag` 36 (27.5%) | ambiguous_action_specification/preview_012, conflicting_evidence/preview_009, missing_critical_parameter/preview_002 |
| P09 | 상태의 현재 시각(`current_date`/`current_time`)을 옮겨 "어제·내일·이번 주"의 지칭 대상을 바꾼다 | `relative_time` 31 (23.7%) | ambiguous_action_specification/preview_012, missing_critical_parameter/preview_039, conflicting_evidence/preview_011 |
| P11 | 커밋 본문으로 옮겨야 할 원본(문서·파일·데이터셋)의 수치와 항목 수를 바꾼다 | `content_transfer` 29 (22.1%) | emergent_risk_discovery/preview_019, critical_tool_failure/preview_026, conflicting_evidence/preview_016 |
| P13 | 대조하는 두 컬렉션의 값을 불일치시킨다(주문 기록의 금액 ≠ 카탈로그 금액, 문서 ≠ 레지스트리) | `cross_collection` 29 (22.1%) | conflicting_evidence/preview_008, conflicting_evidence/preview_016, critical_tool_failure/preview_019 |
| P16 | 분기 조건의 대상을 없앤다(선호 수단·폴더·예약이 부재 → `otherwise` 경로로 넘어가야 함) | `existence_branch` 26 (19.8%) | high_stakes_action/preview_011, high_stakes_action/preview_018, missing_critical_parameter/preview_007 |
| P18 | 기본값 포인터를 비운다(`default_payment_method_id = ""`, `default_address_id = ""`) | `default_pointer` 21 (16.0%) | conflicting_constraints/preview_009, conflicting_constraints/preview_015, insufficient_tool_capability/preview_034 |

### 7.3 자연 커버리지

분모는 **131문항 전체**다. 특징 0개로 코딩된 11문항(§5)도 분모에 넣었고, 이 11문항은
어떤 k에서도 커버되지 않으므로 아래 표에 따로 표시한다.

**선택된 8행의 자연 커버리지: 113 / 131 = 86.3%**
(코딩된 120문항만 분모로 하면 113 / 120 = 94.2%)

커버리지 곡선(§7.1의 순서로 누적. k행이 커버하는 특징 집합은 그 k행의 주 특징 ∪ 부 특징):

| k | 누적 특징 수 | 커버 문항 | 커버리지 (분모 131) | 코딩 120 기준 | 미커버 = 특징0(11) + 코딩된 미커버 |
|---|---|---|---|---|---|
| 2 | 2 | 80 | **61.1%** | 66.7% | 11 + 40 |
| 4 | 4 | 94 | **71.8%** | 78.3% | 11 + 26 |
| 8 | 8 | 113 | **86.3%** | 94.2% | 11 + 7 |
| 12 | 12 | 119 | **90.8%** | 99.2% | 11 + 1 |
| 16 | 16 | 120 | **91.6%** | 100% | 11 + 0 |
| 33 | 16 | 120 | **91.6%** | 100% | 11 + 0 |

곡선에서 읽히는 것 셋.

1. **k=8에서 이미 포화에 가깝다**. k를 8에서 16으로 두 배 늘려도 커버리지는 86.3% → 91.6%,
   즉 코딩된 문항 기준으로 94.2% → 100%로 7문항만 늘어난다. k=16 이후 P19~P33의
   17행은 이미 포함된 특징의 조합만 건드리므로 **k=33의 커버리지는 k=16과 같다(120문항)**.
   커버리지만 보면 fork set을 8보다 키울 이유가 약하다.
2. **상한은 91.6%**다. §5(a)의 5문항은 커밋 대상과 인자가 지시문에 박혀 있어 어떤 상태
   섭동에도 정답 커밋이 변하지 않는다(대조군으로 쓸 수 있다). §5(b)의 6문항은 규칙의 과소
   포함 때문에 0개로 떨어진 것이고, 손으로 읽으면 P01·P11·P07이 닿는다. 즉 실질 상한은
   91.6%보다 높고 약 96%(126/131) 근처다.
3. **k=8이 놓치는 코딩된 7문항**은 전부 `recency`·`capacity_balance`·`unit_field`·
   `list_order`에만 의존한다: ambiguous_action_specification/preview_010(`recency`),
   critical_tool_failure/preview_033(`recency`), emergent_risk_discovery/preview_013(`recency`),
   high_stakes_action/preview_005(`capacity_balance`),
   insufficient_tool_capability/preview_011(`capacity_balance`),
   conflicting_constraints/preview_005(`capacity_balance`+`unit_field`),
   conflicting_constraints/preview_021(`list_order`).
   8행을 늘리지 않고 이 7문항을 덮으려면 P20(`recency`, 동률 타임스탬프)과
   P24(`capacity_balance`, 여유분 부족)를 넣어 10행으로 가는 것이 가장 싼 경로다
   (10행이면 119/131 = 90.8%, 코딩 기준 99.2%).

§6의 오류 방향을 여기에도 적용해 둔다. `cross_collection`이 5문항 과소 집계였으므로
P13의 실제 사정거리는 29문항보다 넓고, 반대로 P04(`set_size`)와 P18(`default_pointer`)은
각각 1건·1건의 과대 집계가 표본에서 확인됐다. 8행의 구성은 이 보정으로 바뀌지 않는다
(순위가 뒤집히는 인접 쌍이 없다).
