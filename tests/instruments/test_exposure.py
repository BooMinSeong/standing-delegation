"""자리 노출·불일치 행·귀속=R·분기점 가시성 합성 검사.

`docs/DECISIONS.md` D-011(같은 사건), D-012(동결 매핑으로 R 없이 계산),
D-015(R 정의 불가 행 제외), `docs/LOGIC.md` L6, L28, L29.
"""

from __future__ import annotations

import copy

from instruments.exposure import (
    ROW_FEATURE_V1,
    a_rows,
    attribution_equals_r,
    e_expose,
    e_mismatch,
    exposure_seen,
    r_diagnostics,
)
from instruments.policy_reader import read


def _case(forksets: dict, name: str) -> list[dict]:
    return forksets["cases"][name]["rows"]


def test_frozen_row_feature_map_matches_derivation():
    """fork set 8행 = P01·P04·P07·P09·P11·P13·P16·P18 (D-010, 도출 §7.2)."""
    assert sorted(ROW_FEATURE_V1) == ["P01", "P04", "P07", "P09", "P11", "P13", "P16", "P18"]
    assert ROW_FEATURE_V1["P01"] == "cand_uniqueness"
    assert ROW_FEATURE_V1["P18"] == "default_pointer"


def test_a_rows_from_frozen_mapping(forksets):
    rows = _case(forksets, "expose_true")
    assert a_rows(rows, forksets["a_feature_ids"]) == ["f01"]
    assert a_rows(rows, ["status_flag"]) == ["f03"]


def test_e_expose_true(forksets):
    rows = _case(forksets, "expose_true")
    out = e_expose(rows, forksets["a_feature_ids"])
    assert out["e_expose"] is True
    assert out["witness"][0] == "f01"
    assert out["overcount_risk"] is True         # 기준 행이 없어 단일 편집 대조가 아니다


def test_e_expose_false(forksets):
    rows = _case(forksets, "expose_false")
    out = e_expose(rows, forksets["a_feature_ids"])
    assert out["e_expose"] is False
    assert out["overcount_risk"] is False


def test_e_expose_uses_no_rule_oracle(forksets):
    """R_s를 지워도 값이 같아야 한다 (D-012: perturbation_row만으로 계산)."""
    rows = copy.deepcopy(_case(forksets, "expose_true"))
    with_r = e_expose(rows, forksets["a_feature_ids"])["e_expose"]
    for row in rows:
        row.pop("R_s", None)
        row.pop("r_defined", None)
    assert e_expose(rows, forksets["a_feature_ids"])["e_expose"] == with_r


def test_e_expose_with_baseline_row(forksets):
    rows = _case(forksets, "expose_with_baseline")
    out = e_expose(rows, forksets["a_feature_ids"], baseline_row_id="f00")
    assert out["e_expose"] is True
    assert out["baseline_used"] is True
    assert out["overcount_risk"] is False


def test_baseline_removes_overcounting(forksets):
    """A 행은 기준 행과 같고 비 A 행만 다른 표. 기준 행이 있으면 false, 없으면 과대 계수."""
    rows = _case(forksets, "expose_non_a_row_only")
    with_base = e_expose(rows, forksets["a_feature_ids"], baseline_row_id="f00")
    without = e_expose([r for r in rows if r["state_id"] != "f00"], forksets["a_feature_ids"])
    assert with_base["e_expose"] is False
    assert without["e_expose"] is True and without["overcount_risk"] is True


def test_e_expose_coverage_out_is_excluded(forksets):
    rows = _case(forksets, "expose_true")
    out = e_expose(rows, [])
    assert out["e_expose"] is None and out["reason"] == "coverage_out"


def test_e_expose_unseen_a_row_is_undecided(forksets):
    rows = _case(forksets, "expose_a_row_unseen")
    out = e_expose(rows, forksets["a_feature_ids"])
    assert out["e_expose"] is None and out["reason"] == "no_a_row_usable"
    assert out["excluded"]["unseen"] == ["f01"]


def test_b0_prediction_table_uses_the_same_event(forksets):
    """B0의 번역 예측 표도 같은 함수로 판정한다(D-011). 예측 불가 행은 제외된다."""
    rows = forksets["b0_prediction_table"]["rows"]
    out = e_expose(rows, forksets["a_feature_ids"])
    assert out["e_expose"] is True
    assert out["excluded"]["undetermined"] == ["f06"]


def test_e_mismatch_and_r_undefined_rows(forksets):
    rows = _case(forksets, "expose_true")
    out = e_mismatch(rows)
    assert out["e_mismatch"] is True
    assert out["mismatch_rows"] == ["f01", "f08"]
    assert out["n_checked"] == 7
    assert out["excluded_counts"]["r_undefined"] == 1


def test_e_mismatch_false(forksets):
    out = e_mismatch(_case(forksets, "expose_false"))
    assert out["e_mismatch"] is False and out["n_checked"] == 8


def test_attribution_equals_r(policy_tables):
    """귀속 = R은 행동 동일성으로 판정한다. R이 V의 원소가 아닐 수 있다."""
    rows = copy.deepcopy(policy_tables["cases"]["consistent"]["rows"])
    for row in rows:                                   # R = "첫 번째"와 같은 규칙
        row["R_s"] = row["predictions"]["첫 번째"]
        row["r_defined"] = True
    r = read(rows, policy_tables["rules"])
    out = attribution_equals_r(r, rows)
    assert out["equals_r"] is True

    for row in rows:                                   # R = "최대"로 바꾸면 ≠
        row["R_s"] = row["predictions"]["최대"]
    out2 = attribution_equals_r(read(rows, policy_tables["rules"]), rows)
    assert out2["equals_r"] is False


def test_attribution_equals_r_hold_is_undecided(policy_tables):
    rows = copy.deepcopy(policy_tables["cases"]["hold_n3"]["rows"])
    for row in rows:
        row["R_s"] = row["predictions"]["첫 번째"]
        row["r_defined"] = True
    out = attribution_equals_r(read(rows, policy_tables["rules"]), rows)
    assert out["equals_r"] is None and out["reason"] == "hold"


def test_attribution_equals_r_tie_reports_membership(policy_tables):
    rows = copy.deepcopy(policy_tables["cases"]["tie"]["rows"])
    for row in rows:
        row["R_s"] = row["predictions"]["최대"]
        row["r_defined"] = True
    out = attribution_equals_r(read(rows, policy_tables["rules"]), rows)
    assert out["equals_r"] is False and out["reason"] == "tie"
    assert out["r_in_set"] is True


def test_r_diagnostics_detects_r_outside_v(policy_tables):
    rows = copy.deepcopy(policy_tables["cases"]["consistent"]["rows"])
    for row in rows:                                   # R이 V의 어느 규칙과도 다르다
        row["R_s"] = ["sup_009"]
        row["r_defined"] = True
    d = r_diagnostics(rows, policy_tables["rules"])
    assert d["r_expressible_in_v"] is False
    assert d["f_discriminates_r"] is True


def test_exposure_seen_before_first_commit(rollout_exposure_seen):
    log = rollout_exposure_seen["execution_log"]
    k = rollout_exposure_seen["k_set"]
    before = exposure_seen(log, k, before_first_commit=True)
    whole = exposure_seen(log, k, before_first_commit=False)
    assert before["exposure_seen"] is False
    assert before["unseen"] == ["sup_003"]
    assert before["ratio"] == 2 / 3
    assert before["cutoff_step"] == 2
    assert whole["exposure_seen"] is True        # commit 뒤 조회에서는 셋 다 나온다


def test_exposure_seen_all(rollout_attempts):
    out = exposure_seen(rollout_attempts["execution_log"], ["sup_001", "sup_002", "sup_003"])
    assert out["exposure_seen"] is True and out["unseen"] == []
