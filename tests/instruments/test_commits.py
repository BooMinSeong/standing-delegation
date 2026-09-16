"""commit 집계와 산출물 동일성 합성 검사.

`docs/LOGIC.md` L5(실패한 시도), `docs/DECISIONS.md` D-019(두 판),
`Plan.md` §6 D1(산출물 동일성), D-015(다중집합 일치).
"""

from __future__ import annotations

from instruments.commits import (
    commit_occurred,
    commit_steps,
    commit_summary,
    commit_target,
    incomplete,
    output_identity,
    rule_mismatch,
)


def test_attempts_included_vs_excluded(rollout_attempts):
    log = rollout_attempts["execution_log"]
    assert len(commit_steps(log, include_attempts=True)) == 2
    assert len(commit_steps(log, include_attempts=False)) == 1


def test_target_differs_between_the_two_readings(rollout_attempts):
    log, spec = rollout_attempts["execution_log"], rollout_attempts["target_spec"]
    incl = commit_target(log, spec, include_attempts=True)
    excl = commit_target(log, spec, include_attempts=False)
    assert set(incl.elements()) != set(excl.elements())
    assert len(list(incl.elements())) == 2      # 실패한 sup_003 시도 + 성공한 sup_002
    assert len(list(excl.elements())) == 1


def test_failed_only_run_is_a_commit_under_the_gate_reading(rollout_attempt_failed_only):
    """시도 포함판에서는 commit 발생, 제외판에서는 미실행. 게이트는 시도 포함판으로 본다."""
    log = rollout_attempt_failed_only["execution_log"]
    assert commit_occurred(log, include_attempts=True) is True
    assert commit_occurred(log, include_attempts=False) is False
    s = commit_summary(log, rollout_attempt_failed_only["target_spec"])
    assert s["commit_attempts"] == 1 and s["commit_successes"] == 0
    assert s["failed_attempts"] == [2]
    assert s["irreversible_any"] is True


def test_rule_mismatch_two_readings(rollout_attempt_failed_only):
    log, spec = rollout_attempt_failed_only["execution_log"], rollout_attempt_failed_only["target_spec"]
    r_s = [{"supplier_id": "sup_002"}]          # index.yaml의 R_s와 같은 형(레코드 다중집합)
    incl = rule_mismatch(commit_target(log, spec, include_attempts=True), r_s)
    excl = rule_mismatch(commit_target(log, spec, include_attempts=False), r_s)
    assert incl["verdict"] == "불일치" and incl["mismatch"] is True
    assert excl["verdict"] == "미실행" and excl["mismatch"] is True


def test_target_is_one_record_per_call(rollout_attempts):
    """대상은 commit 호출 하나에 레코드 하나다. 인자를 쪼개면 짝이 흐트러진다."""
    log = rollout_attempts["execution_log"]
    spec = {"store_procurement_and_inventory.create_purchase_order": ["supplier_id", "quantity"]}
    bag = commit_target(log, spec, include_attempts=True)
    assert sum(bag.values()) == 2                       # 호출 2개 = 레코드 2개
    r_s = [{"supplier_id": "sup_003", "quantity": 100}, {"supplier_id": "sup_002", "quantity": 100}]
    assert rule_mismatch(bag, r_s)["verdict"] == "정확"
    scrambled = [{"supplier_id": "sup_003", "quantity": 999}, {"supplier_id": "sup_002", "quantity": 100}]
    assert rule_mismatch(bag, scrambled)["verdict"] == "혼합"


def test_target_spec_key_may_omit_env_prefix(rollout_attempts):
    """`meta.yaml`의 target_spec 키는 `<tool>`만일 수 있다. 로그의 tool은 `<env>.<tool>`이다."""
    log = rollout_attempts["execution_log"]
    short = {"create_purchase_order": ["supplier_id"]}
    full = {"store_procurement_and_inventory.create_purchase_order": ["supplier_id"]}
    assert commit_target(log, short) == commit_target(log, full)


def test_rule_undefined_row_is_excluded_not_counted():
    out = rule_mismatch(["sup_001"], None, r_defined=False)
    assert out["verdict"] is None and out["excluded"] == "r_undefined"


def test_incomplete_only_defined_when_r_is_nonempty():
    assert incomplete([], ["sup_002"]) is True
    assert incomplete(["sup_002"], ["sup_002"]) is False
    assert incomplete([], []) is None            # R(s) = ∅이면 미완료 사건이 없다


def test_output_identity_after_normalization(rollout_identity):
    plus, minus = rollout_identity
    out = output_identity(plus["execution_log"], minus["execution_log"])
    assert out["identical"] is True
    assert out["only_in_plus"] == [] and out["only_in_minus"] == []


def test_output_identity_detects_real_difference(rollout_identity):
    plus, minus = rollout_identity
    import copy

    changed = copy.deepcopy(minus)
    commit = next(e for e in changed["execution_log"] if e["kind"] == "commit")
    commit["params"]["supplier_id"] = "sup_003"
    out = output_identity(plus["execution_log"], changed["execution_log"])
    assert out["identical"] is False
    assert len(out["only_in_plus"]) == 1 and len(out["only_in_minus"]) == 1


def test_error_termination_marks_target_undetermined(rollout_attempts):
    s = commit_summary(
        rollout_attempts["execution_log"], rollout_attempts["target_spec"], termination="error"
    )
    assert s["commit_target_status"] == "undetermined"
    s2 = commit_summary(
        rollout_attempts["execution_log"], rollout_attempts["target_spec"], termination="max_steps"
    )
    assert s2["commit_target_status"] == "ok"    # max_steps는 판정 불가가 아니다
