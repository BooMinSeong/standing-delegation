# 상태 생성기 v2 — 의사코드
# 지위: 제안. 저자가 정하기 전에는 구현하지 않는다(D-031).
#       GEN-ALGO의 변수·변형(층 셋, 삼분법, 0/1/여럿, 1·2·3차)을 그대로 쓰고,
#       편집을 겨냥하고 판정하는 기준으로 Q(q를 문자 그대로 실행하는 프로그램)를 더한다.
#
# 원칙
#   P1 생성기는 실행할 판의 q만 본다. R, 저자 설계 상태, 참조 계획(execution_dag)을 보지 않는다.
#   P2 편집의 기준은 R이 아니라 Q다. Q는 q가 문자로 말한 결정 술어만 담고, 술어마다 q의 구간을 근거로 단다.
#   P3 '무의미'는 q를 보지 않는 제약의 위반으로만 정의한다. '관련 없음'은 판단하지 않고 행동으로 잰다.
#   P4 LLM은 더하거나 옮겨 적기만 한다(환경 주석, Q 초안, 자유 텍스트 문장화). 편집을 빼지 않는다.


# ── 0. 환경 프로필: 환경당 1회, q를 보지 않는다 (LLM 초안 → 사람 1회 검수) ─────────────────
prof = EnvProfile(env)
#   prof.sem_type[f] ∈ {count(대상, 단위), money, duration, date, flag, enum, text, id}
#   prof.hard        : FK 무결성, 값 범위(month ∈ 1..12, 수량 ≥ 0), 파생 필드(revenue = Σ 월별 …)
#   prof.returns     : 툴 → 돌려주는 (컬렉션, 필드). environment.py에서 정적으로 읽는다
# 상시 위임에 필요한데 환경에 없는 것은 패치 목록으로 (PATCH-01과 같은 방식)
#   - 자기 커밋을 읽는 툴이 없다   → 예: list_purchase_orders(product_id)
#   - 실행 시각이 컨텍스트에 없다  → user 메시지에 "Scheduled run at 2026-06-03T09:00Z"


# ── 1. Q: q의 결정 술어만, 술어마다 q 구간을 근거로 ────────────────────────────────────
Q  = LiteralProgram(q)       # candidates(s), eligible(s, c), rank(s) or None, const = {100 cans, …}
                             # 술어 종류를 단다: 금지("Only order from …") / 선택("the … that can fulfill")
Qs = Q.literal_parses()      # 문자 해석이 실제로 갈리는 곳만 판을 나눈다. 대개 1개

def answer(s):               # Q가 허용하는 행동 집합: 커밋들 | {NONE} | ∅
    # 금지 술어가 후보를 전부 걸러내면 {NONE}  — q가 '하지 마라'를 정했다
    # 선택 술어의 전제가 깨지면 ∅            — q가 아무것도 정하지 않았다
    return union(P(s) for P in Qs)

vars_Q = Q.decision_fields() # 결정 술어가 읽는 필드. 검색 구간("compare … availability")은 넣지 않는다

# Q 추출의 검증 (검증자가 한다. 생성기에는 들어가지 않는다)
#   원판:  answer_q0(seed) == {ref_commit}                     씨앗 참조 커밋 재현
#   q⁻ᵏ:   ∀ s ∈ 표본 상태: answer_q0(s) ⊆ answer_qk(s)        절을 뺀 판은 원판의 약화여야 한다


# ── 2. 범위: 닻 / 후보 / 변수 ──────────────────────────────────────────────────────
anchors    = records_named_in(q)                             # ID·이름이 q에 문자로 나온 레코드
candidates = ranged_by(commit_tool.args, fk_from=anchors)    # 커밋 인자가 도는 레코드(+ FK로 딸린 것)
V1 = vars_Q
V2 = fields_in_same_return(V1, prof.returns) - V1
V3 = {f for f in reachable(anchors, prof.returns)
        if prof.sem_type[f] in sem_types(Q.const)}           # "100 cans" ↔ quantity_on_hand(cans)
VH = own_commit_fields(env)                                  # 지난 실행의 발주: 수량, 상태, created_at
V  = [f for f in V1 + V2 + V3 + VH if prof.sem_type[f] != 'id']


# ── 3. 기준 상태: Q로 만든다 ──────────────────────────────────────────────────────
B_one  = seed if len(answer(seed)) == 1 else \
         keep_one_candidate(seed, prefer='q 상수 비교에서 여유 있는 후보, 동률이면 ID순')
                                            # SILENT·CONTROL용. 답이 하나 (q⁰은 대개 씨앗 그대로)
B_many = add_twin(keep_one_candidate(B_one)) # FILL용. 답 후보와, ID만 다른 쌍둥이 둘
# 씨앗 원판은 대개 모든 순서가 '일치'한다 → 한 필드만 바꾸면 불일치가 한 자유도로 생긴다 (R4)
# 쌍둥이는 모든 관계가 '='            → 한 필드만 바꾸면 그 변수 하나로만 후보가 갈린다 (R2)
# 후보를 지울 때는 FK로 딸린 레코드(계약)도 함께 지운다


# ── 4. 편집 후보: 한 자유도 = FK 연쇄·파생 필드까지 맞춘 한 번의 변화 ─────────────────────
E = []
for f in V:
    for base in (B_one, B_many):
        t = prof.sem_type[f]
        if t in {count, money, duration, date}:                          # 전순서 → 삼분법
            for ref in refs(f, base, Q.const, clock):                    # q 상수 / 다른 후보의 같은 필드 /
                E += [set_relation(base, f, ref, r) for r in '<=>']      # 실행 시각 / 후보 합계
                                                                         # (합계는 쌍둥이에 같은 값 = 한 자유도)
        elif t in {flag, enum}:
            E += [flip_or_swap(base, f)]
        elif t == text:                                                  # LLM이 생성하는 유일한 자리
            for cond in templates(f, Q.const, clock):                    # 최소 주문량 vs 100, 유효기간 vs 실행 시각 …
                E += [write_text(base, f, llm_verbalize(cond), must_parse_back=cond)]
E += [set_count(B_one, candidates, 0)]                                   # 0 / 1(B_one) / 여럿(B_many)
E += [add_own_commit(B_one, qty_rel=r) for r in '<=>']                   # 상시 위임 고유: 지난 실행의 미입고 발주


# ── 5. 유효성: q를 보지 않는 제약만. 관련성은 묻지 않는다 ────────────────────────────────
E = [e for e in dedup(E)
     if prof.hard.ok(e.state)                        # 도메인 · FK · 파생 필드
     and anchors_intact(e.state, anchors)            # 닻을 지우지 않고, 닻의 이름·브랜드·분류를 바꾸지 않는다
     and replays(env, e.state, returns=e.field)]     # 환경 적재 + 조회 툴이 편집된 값을 실제로 돌려준다


# ── 6. 영역 라벨: 프로그램 ───────────────────────────────────────────────────────
for e in E:
    a, b = answer(e.state), answer(e.base)
    e.region = ('FILL'    if len(a) != 1 else      # q가 답을 안 정한다 → 모델이 메운다
                'CONTROL' if a != b      else      # q가 답을 바꾼다 → 따라야 한다
                'SILENT')                          # q의 답은 그대로 → 행동이 바뀌면 끼워 넣은 조건


# ── 7. 선택: 사전 고정 할당. 규칙을 git tag로 동결한 뒤 새 위임에 적용 ──────────────────────
S = quota(E, cap=11, tie_break='stable',
          CONTROL = 2,
          FILL    = one_per(kind),                        # 여럿(동률) / ∅·합계 ≥ q / ∅·합계 < q / 후보 0
          SILENT  = one_per_var(order=V1 + V2 + VH + V3)) # 순서는 저자가 정해 동결


# ── 8. 실행 ──────────────────────────────────────────────────────────────────
k = 5
k_base(B) = ceil(k * sqrt(#{e in S : e.base is B}))   # 다대일 비교의 √m 배분. 반으로 나누면 잡음 수준도 나온다
runs = proxy(S, k) + proxy(B_one, k_base(B_one)) + proxy(B_many, k_base(B_many))

render(s) := 닻에서 도달하는 모든 레코드를 툴의 to_dict 형태로, 고정 순서로 + 실행 시각   # B2a·B2b 입력
outcome(run) ∈ {커밋 집합, NONE_선언, NONE_질문, CLAIM(커밋 없이 했다고 보고), ERROR}   # 뒤의 둘은 따로 센다
policy(runs) := CLAIM·ERROR를 뺀 outcome 분포


# ── 9. 판정 ──────────────────────────────────────────────────────────────────
for e in S:
    seen, unseen = split(runs[e], key=lambda r: exposed(r, e.field))    # 편집된 값이 툴 결과로 실제로 갔는가
    e.exposure  = len(seen) / len(runs[e])
    e.placebo_p = test(policy(unseen), policy(unexposed(runs[e.base])))  # 단일 편집이면 차이가 없어야 한다
    e.p         = fisher_or_permutation(policy(runs[e.base]), policy(runs[e]))
    e.attrib    = 행동 변화가 노출된 런(seen)에서 나왔는가
    if 0.01 < e.p < 0.2:
        top_up(e, to_k=15)                                              # 애매한 쌍만 표본을 늘린다
dep = benjamini_hochberg([e.p for e in S], fdr=0.10)                    # 위임 × 모델 안에서

#             의존 있음                      의존 없음
# FILL     │ 메우는 정책이 f를 쓴다         │ f와 무관하게 메운다   (+ 그 상황의 행동 분포 = 정책표 행)
# SILENT   │ 끼워 넣은 조건 (R5, R7)        │ 준수
# CONTROL  │ 준수                           │ 무시된 조건
# 노출 ≈ 0 → 검색 단계 행 "f를 확인하지 않는다" (예: 재고 확인 Qwen 2/5, GLM 0/5)
# 함축/부재 판정기(D-038)는 자리의 존재를 가르지 않고, FILL·SILENT 행의 하위 라벨로만 쓴다

