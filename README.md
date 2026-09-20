# standing-delegation-v2

상시 위임 연구 v2. 계획은 `Plan.md`, 기준점은 `docs/CASE-D01.md`.

**무엇을 하는가.** 지시를 한 번 써 두면 에이전트가 무인으로 반복 실행하는 상시 위임에서, 지시가 정하지 않은 상황을 에이전트가 자기 규칙으로 채우고 그 규칙이 결과에 보이지 않는 문제를 다룬다. 지시를 잘 쓰거나 보고를 시키는 것으로는 닫히지 않는다. 위임을 켜기 전에 여러 상황을 만들어 모의 실행하고, 에이전트의 암묵적 규칙을 정책표로 드러내어 주인이 승인하게 하는 프레임워크를 제안한다. 논제는 `Plan.md` §0.

| 파일 | 내용 |
|---|---|
| `docs/CASE-D01.md` | **기준점.** 위임 한 문장에 규칙 다섯 개가 붙은 실물. 저자가 손으로 돌리고 역추적한 표 |
| `Plan.md` | 연구 계획 v2 (무엇을). 단일 출처. 2026-09-20 전면 개정(D-035): 계측이 정답 규칙 R과의 일치에서 최소쌍 의존·발산으로 바뀌고 명제 1~3이 주장 C1~C4가 됐다 |
| `PLAN_EXEC.md` | 시행계획 원안 + 2026-09-16 재설정 기록 |
| `docs/INTRO.md` | 인트로덕션 초고 v0. §0 논제를 서론 서술로 펼친 것 + 증거 현황·반론 점검 |
| `docs/DECISIONS.md` | 저자가 실제로 내린 결정만 |
| `docs/B2-D01.md` | **첫 실측.** D01 여덟 상태 × 로컬 모델 2 × k=5의 B2a·B2b 표와 읽기. 원자료 `data/runs/b2-d01/` |
| `docs/M1-D01.md` | **M1 실측.** 같은 여덟 상태를 러너 v0로 툴콜링 실행. 세 arm 표, 툴 무대에서만 보이는 자리 셋(가용량 구속력, 보고와 실행의 분리, P0 아래 확인 요청). 러너 `src/runner/`, 상태 `data/delegations/D01/states/case/` |
| `docs/REVIEW-2026-09-20.md` | 외부 심사 피드백 대조와 개선 방향. 결정은 D-035로 갔다 |
| `docs/FEASIBILITY.md` | 모델·API·클러스터 실측 |
| `docs/DATA-GEN.md` | 데이터 생성 감사. 131의 뜻, 위임 저작에 없는 규칙 다섯, 기계적 상태 생성이 CASE-D01을 못 내는 증거, 미결 목록 |
| `docs/derivation/` | 눈가림 섭동표 도출 (Plan §4.3) |
| `docs/related/` | 문헌 실재 확인. `scout-2026-09-20.md`는 D-035가 쓴 서지·인용문의 유일한 출처(ACCORD, 불완전 계약, criteria drift, gulf of envisioning, Daikon, VIPER, ratification) |
| `data/delegations/D01/` | 씨앗 문항에서 유도한 위임 1개의 q·R. 출처는 `meta.yaml` |
| `data/envs/` | AgentAbstain 조달 환경 사본 (조회 죽은 가지 패치, `data/env_patches.md`) |

2026-09-16 첫 시도의 전부(감사·반론·결정·척도·검사·상태)는 브랜치 `stage0-attempt1`에 있다. 새 증거 없이 되살리지 않는다. 서브 에이전트 정의 8개도 그 문서 체계를 전제하므로 지웠다(D-032).

v1 자산(동기·문헌·AgentAbstain 실측)은 `../standing-delegation/`.
