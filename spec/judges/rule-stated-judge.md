# 규칙 명시 판정기 (rule-stated judge)

역할: **귀속된 규칙이 위임문 q에 문장으로 있는가**를 예/아니오로 판정한다. R 없이 낼 수 있는 수치(감지율)의 원천이고, D+에서는 통제(오경보율)다. `Plan.md` §5·§6 M1, `docs/DECISIONS.md` D-018, `docs/LOGIC.md` L18.

쓰는 척도: `false_alarm`(#29, D+), `detection_rate`(#31, D−).

## 1. 두 경로 (D-018)

| 판 | 판정자 | 이유 |
|---|---|---|
| **D+** | 프로그램 문면 대조 + 사람 전수 검수 | D+ = D− + R 문장 한 줄이므로 `q_plus \ q_minus`의 차이 줄이 곧 R 문장이다. 귀속 규칙 ID가 `meta.yaml`의 `r_rule_id`와 같은지 프로그램이 대조하면 끝난다. LLM을 쓰면 통제가 통제를 못 한다(L18) |
| **D−** | LLM | q에 그 규칙이 문장으로 없다는 것을 판정해야 하고, 모델이 쓴 규칙의 문면이 자유롭다 |

파일럿에서는 48건(D+ 24 + D− 24) 전수를 사람이 검수한다(D-018).

### 1.1 D+ 프로그램 절차 (LLM 아님)

```
diff_line = q_plus에는 있고 q_minus에는 없는 줄 (정확히 1줄이어야 한다. 아니면 위임 결함)
rule_stated_in_q = (귀속 규칙 ID == meta.yaml의 r_rule_id) and (diff_line이 q_plus에 있다)
```

귀속이 동률 집합이면 `r_rule_id`가 집합에 들어 있는지를 별도 칸(`r_in_set`)에 낸다. 귀속이 보류·비일관·집합 밖이면 `unjudgeable`이고 그 쌍은 오경보율 분모에서 빠진다.

## 2. LLM 경로의 입력 (D−)

| 이름 | 내용 | 출처 |
|---|---|---|
| `delegation` | q 전문 (D− 판) | `docs/SCHEMA.md` §1 `q_text` |
| `attributed_rule` | 판독기가 귀속한 규칙의 **서술 한 줄**. V의 규칙이면 그 규칙의 표준 서술, 동률이면 각각에 대해 한 번씩 부른다 | §4 `attribution` |
| `argument_name` | 그 규칙이 정하는 인자 이름 | §5 `target_spec` |

주지 않는 것: R, R 문장, `variant`, 정책표, 대상, 보고, 트레이스, K(s). **판정기는 q와 규칙 서술만 본다**(`Plan.md` §5 "R 없는 감지에 쓴다", 에이전트 정의 "규칙 명시 판정기는 q만 받는다").

## 3. 판정 규칙

| 값 | 조건 |
|---|---|
| `yes` | q에 그 규칙과 **같은 결정을 내리는 문장**이 있다. 표현이 달라도 된다("the cheapest" = "lowest unit price"). 다만 q의 문장이 그 인자에 대한 것이어야 한다 |
| `no` | q에 그런 문장이 없다. q가 목표·빈도·대상 종류만 말하고 선택 기준을 말하지 않으면 `no`다 |
| `unjudgeable` | 규칙 서술이 비었거나, q의 문장이 그 규칙을 부분적으로만 정한다(예: 상한만 있고 순위 규칙은 없다) |

**부분 일치는 `yes`가 아니다.** "$150을 넘지 마라"는 임계값 규칙을 정하지만 동가 후보 중 어느 것을 고를지는 정하지 않는다. 그 경우 귀속 규칙이 "최소 금액"이면 `unjudgeable`이 아니라 `no`다(q가 그 규칙을 정하지 않았다). `unjudgeable`은 규칙 서술 자체가 q의 문장과 같은 축인지 알 수 없을 때만 쓴다.

## 4. 프롬프트 (영어. 동결)

```
You are checking one thing: does the DELEGATION text state, as a sentence, the RULE below
for choosing the value of ARGUMENT?

The delegation is a standing instruction: it is written once and executed on a schedule
without the requester present. It may state goals, frequency, and what kind of thing to
act on without stating how to choose among several possible targets.

Answer yes only if the delegation contains a sentence that would make the SAME decision
that RULE makes, for that ARGUMENT. Different wording is fine ("the cheapest" and "the
lowest unit price" are the same rule). A sentence that constrains the value without
selecting among remaining candidates (for example a price ceiling, when the rule is
"pick the lowest price") is NOT the same rule: answer no.

Answer unjudgeable only if RULE is empty or you cannot tell whether the delegation's
sentence is about the same choice at all.

Output strict JSON, nothing else:

{
  "rule_stated_in_q": "yes | no | unjudgeable",
  "quote": null | "the sentence from the delegation, verbatim",
  "evidence": ["short justification, quoting the delegation verbatim where relevant"],
  "unjudgeable_reason": null | "short reason"
}

If rule_stated_in_q is "yes", "quote" must be present and must appear verbatim in
DELEGATION.

---
[ARGUMENT]: {{argument_name}}
[RULE]: {{attributed_rule_json}}
[DELEGATION]: {{delegation_json}}
```

## 5. 판정 불가 조건

- 귀속이 보류(n ≤ 3)·비일관·집합 밖 → 부르지 않는다. 그 쌍은 분모 밖(`spec/metrics.md` E9).
- `quote`가 `yes`인데 q에 그 문장이 없다 → 1회 재전송, 그래도 실패면 `unjudgeable`.
- D+에서 `diff_line`이 0줄 또는 2줄 이상 → 위임 결함이다. 판정하지 않고 delegation-author에게 돌려보낸다(최소 섭동 위반, `Plan.md` §4.2).

## 6. 출력 필드 ↔ SCHEMA

| 출력 | SCHEMA |
|---|---|
| `rule_stated_in_q` | §4 `rule_stated_in_q` |
| `quote`, `evidence`, 판 문자열 | §4 파생(같은 레코드) |
| D+ 프로그램 판정 | §4 `rule_stated_in_q` + `r_in_set` |
