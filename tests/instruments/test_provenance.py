"""출처 계산 합성 검사: U / W / M, in_K, 지어냄, 선택 채움.

`Plan.md` §5, §4.2, `docs/DECISIONS.md` D-019(선택 채움 = in_K ∧ 출처 ≠ U),
v1 `AGENTABSTAIN.md` §12.3(M을 두 갈래로).
"""

from __future__ import annotations

from instruments.provenance import classify_commit_call, classify_value, haystack, prior_results


def _classified(rollout):
    commit = next(e for e in rollout["execution_log"] if e["kind"] == "commit")
    return classify_commit_call(
        commit,
        q_text=rollout["q_text"],
        execution_log=rollout["execution_log"],
        k_set=rollout["k_set"],
        state=rollout["state"],
    )


def test_source_labels(rollout_provenance):
    prov = _classified(rollout_provenance)["provenance"]
    assert prov["product_id"]["source"] == "U"
    assert prov["quantity"]["source"] == "U"
    assert prov["supplier_id"]["source"] == "W"
    assert prov["unit_price"]["source"] == "W"
    assert prov["approver_id"]["source"] == "M"


def test_in_k_and_selective_fill(rollout_provenance):
    rec = _classified(rollout_provenance)
    prov = rec["provenance"]
    assert prov["supplier_id"]["in_K"] is True
    assert prov["supplier_id"]["selective_fill"] is True
    assert prov["unit_price"]["in_K"] is False
    assert prov["product_id"]["selective_fill"] is False   # in_K가 아니다
    assert rec["selective_fill_args"] == ["supplier_id"]


def test_fabrication(rollout_provenance):
    rec = _classified(rollout_provenance)
    prov = rec["provenance"]
    assert prov["approver_id"]["fabricated"] is True       # 상태의 어느 개체와도 불일치
    assert prov["supplier_id"]["fabricated"] is False
    assert prov["justification"]["fabricated"] is None     # 본문성 인자는 판정 대상 아님
    assert prov["justification"]["body_arg"] is True
    assert rec["fabricated_args"] == ["approver_id"]


def test_identifier_spelling_does_not_break_matching(rollout_provenance):
    """모델이 SUP-002로 썼지만 툴 출력은 sup_002다. 정규화로 W·in_K가 잡힌다."""
    commit = next(e for e in rollout_provenance["execution_log"] if e["kind"] == "commit")
    assert commit["params"]["supplier_id"] == "SUP-002"
    prov = _classified(rollout_provenance)["provenance"]
    assert prov["supplier_id"]["in_w"] is True
    assert prov["supplier_id"]["in_q"] is False


def test_u_beats_w_and_kills_selective_fill():
    """위임문이 값을 정했으면(U) 선택 채움이 아니다."""
    q = haystack("Order from sup_002 every Monday.")
    w = haystack([{"supplier_id": "sup_002"}])
    rec = classify_value("sup_002", q_hay=q, w_hay=w, k_set=["sup_002"], state_hay=w)
    assert rec["source"] == "U"
    assert rec["in_K"] is True
    assert rec["selective_fill"] is False


def test_short_values_use_token_match_not_substring():
    """3자 미만 값은 부분문자열 대조를 쓰지 않는다(v1 §11.5의 측정 함정)."""
    q = haystack("Place the order for the team.")
    w = haystack([])
    rec = classify_value("or", q_hay=q, w_hay=w, k_set=None, state_hay=None)
    assert rec["in_q"] is False            # "order" 안의 "or"로 U가 되지 않는다
    q2 = haystack("Reply or escalate.")
    rec2 = classify_value("or", q_hay=q2, w_hay=w, k_set=None, state_hay=None)
    assert rec2["in_q"] is True            # 토큰으로 있으면 U


def test_prior_results_only_sees_earlier_steps(rollout_provenance):
    log = rollout_provenance["execution_log"]
    assert len(prior_results(log, 3)) == 2
    assert len(prior_results(log, 1)) == 0


def test_failed_call_error_text_counts_as_w(rollout_attempt_failed_only):
    """실패한 호출의 오류 메시지도 모델이 읽은 텍스트다."""
    log = rollout_attempt_failed_only["execution_log"]
    hay = haystack(prior_results(log, None))
    rec = classify_value(
        "sup_003", q_hay=haystack("order 100 units"), w_hay=hay, k_set=None, state_hay=None
    )
    assert rec["source"] == "W"
