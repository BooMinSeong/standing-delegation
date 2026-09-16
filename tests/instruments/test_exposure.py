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


# ------------------------------------- L39: overcount_risk와 깨끗한 단일 편집 대조

def _fs(forksets, name):
    case = forksets["cases"][name]
    return (
        case["rows"],
        case.get("a_feature_ids", forksets["a_feature_ids"]),
        case.get("row_feature_map"),
    )


def test_same_feature_a_rows_are_a_clean_pair(forksets):
    rows, feats, fmap = _fs(forksets, "a_rows_same_feature")
    out = e_expose(rows, feats, row_feature_map=fmap)
    assert out["e_expose"] is True
    assert out["within_same_feature_diff"] is True
    assert out["witness_kind"] == "within_same_feature"
    assert out["overcount_risk"] is False


def test_cross_feature_a_rows_are_not_a_clean_pair(forksets):
    """A 행이 둘이어도 특징이 다르면 깨끗하지 않다 (L39)."""
    rows, feats, fmap = _fs(forksets, "a_rows_cross_feature")
    out = e_expose(rows, feats, row_feature_map=fmap)
    assert out["e_expose"] is True
    assert out["within_same_feature_diff"] is False
    assert out["within_cross_feature_diff"] is True
    assert out["clean_comparison_possible"] is False
    assert out["overcount_risk"] is True


def test_baseline_row_makes_cross_feature_clean(forksets):
    rows, feats, fmap = _fs(forksets, "a_rows_cross_feature_with_baseline")
    out = e_expose(rows, feats, row_feature_map=fmap)
    assert out["baseline_used"] is True and out["baseline_row"] == "f00"
    assert out["witness_kind"] == "a_vs_baseline"
    assert out["overcount_risk"] is False


def test_baseline_is_found_from_is_baseline_flag(forksets):
    """`baseline_row_id`를 주지 않아도 is_baseline 행을 쓴다. P00을 우선한다."""
    rows = copy.deepcopy(forksets["cases"]["a_rows_cross_feature_with_baseline"]["rows"])
    rows.append({"state_id": "f09", "perturbation_row": "P09", "exposure_seen": True,
                 "is_baseline": True, "commit_target": ["sup_002"]})   # 적용 불가 행도 기준 행
    fmap = forksets["cases"]["a_rows_cross_feature_with_baseline"]["row_feature_map"]
    out = e_expose(rows, ["cand_uniqueness", "num_extremum"], row_feature_map=fmap)
    assert out["n_baseline_rows"] == 2 and out["baseline_row"] == "f00"


# --------------------------------------------- L40: 커버리지 3값과 미대표 특징

def test_coverage_three_values(forksets):
    rows, feats, fmap = _fs(forksets, "partial_coverage")
    out = e_expose(rows, feats, row_feature_map=fmap)
    assert out["coverage"] == "partial"
    assert out["unrepresented_feature_ids"] == ["num_extremum"]
    assert out["n_unrepresented"] == 1
    assert out["e_expose"] is True                      # 부분 커버리지에서도 계산은 된다

    full = e_expose(rows, ["cand_uniqueness"], row_feature_map=fmap)
    assert full["coverage"] == "in" and full["n_unrepresented"] == 0

    none = e_expose(rows, ["num_extremum"], row_feature_map=fmap)
    assert none["coverage"] == "out" and none["e_expose"] is None
    assert none["reason"] == "coverage_out"


def test_coverage_of_standalone():
    from instruments.exposure import coverage_of

    assert coverage_of([])["coverage"] == "out"
    assert coverage_of(["cand_uniqueness"])["coverage"] == "in"
    got = coverage_of(["cand_uniqueness", "num_extremum"])
    assert got["coverage"] == "partial" and got["unrepresented_feature_ids"] == ["num_extremum"]


# ---------------------------------------------- L38: 오경보율의 조건부 분모

def _dplus_rows(policy_tables, r_rule):
    rows = copy.deepcopy(policy_tables["cases"]["consistent"]["rows"])
    for row in rows:
        row["R_s"] = row["predictions"][r_rule]
        row["r_defined"] = True
    return rows


def test_false_alarm_only_counts_pairs_where_attribution_equals_r(policy_tables):
    from instruments.exposure import false_alarm_input

    rows = _dplus_rows(policy_tables, "첫 번째")          # 귀속 = R
    r = read(rows, policy_tables["rules"])
    yes = false_alarm_input(r, rows, "yes")
    no = false_alarm_input(r, rows, "no")
    assert yes["in_denominator"] is True and yes["false_alarm"] is False
    assert no["in_denominator"] is True and no["false_alarm"] is True


def test_false_alarm_excludes_pairs_where_attribution_ne_r(policy_tables):
    """옛 정의에서 구조적으로 100%가 되던 경우가 분모 밖으로 빠진다 (L38)."""
    from instruments.exposure import false_alarm_input

    rows = _dplus_rows(policy_tables, "최대")             # 귀속(첫 번째) ≠ R(최대)
    out = false_alarm_input(read(rows, policy_tables["rules"]), rows, "no")
    assert out["equals_r"] is False
    assert out["in_denominator"] is False and out["false_alarm"] is False
    assert out["excluded_reason"] == "attribution_ne_r"


def test_false_alarm_separates_r_outside_v(policy_tables):
    from instruments.exposure import false_alarm_input

    rows = copy.deepcopy(policy_tables["cases"]["consistent"]["rows"])
    for row in rows:
        row["R_s"] = ["sup_009"]                          # R이 V로 표현되지 않는다
        row["r_defined"] = True
    out = false_alarm_input(read(rows, policy_tables["rules"]), rows, "no")
    assert out["r_expressible_in_v"] is False
    assert out["in_denominator"] is False
    assert out["excluded_reason"] == "r_not_expressible"


def test_false_alarm_hold_and_unjudgeable_are_excluded(policy_tables):
    from instruments.exposure import false_alarm_input

    hold_rows = copy.deepcopy(policy_tables["cases"]["hold_n3"]["rows"])
    for row in hold_rows:
        row["R_s"] = row["predictions"]["첫 번째"]
        row["r_defined"] = True
    out = false_alarm_input(read(hold_rows, policy_tables["rules"]), hold_rows, "no")
    assert out["in_denominator"] is False and out["excluded_reason"] == "hold"

    ok_rows = _dplus_rows(policy_tables, "첫 번째")
    out2 = false_alarm_input(read(ok_rows, policy_tables["rules"]), ok_rows, "unjudgeable")
    assert out2["in_denominator"] is False and out2["excluded_reason"] == "judge_unjudgeable"


# ============================== D-027 (3): 촉발률과 자리 노출은 다른 사건이다
#
# 상수 정책('첫 번째')은 자리 값이 바뀌어도 대상이 안 바뀌므로 자리 노출이 구조적으로 거짓인데,
# 그 정책표는 기준 행에서 R과 다른 대상을 내므로 주인의 비준·보강은 촉발된다(D01 실물, L41).
# 이 절의 검사가 D-027 (3)의 근거다.

RULES_V0 = ("첫 번째", "최대", "최근", "전부", "없음")


def _pair(forksets, case, *, delegation_id="D01", model=None, method="M1"):
    from instruments.exposure import pair_record

    return pair_record(
        forksets["cases"][case]["rows"],
        forksets["a_feature_ids"],
        method=method,
        delegation_id=delegation_id,
        model=model or case,
        rules=RULES_V0,
    )


def test_constant_policy_hides_the_slot_but_triggers_ratification(forksets):
    """자리 노출 false + 불일치 행 true. 두 사건이 갈리는 실물 (D-027 (3), L41)."""
    rec = _pair(forksets, "d01_constant_first_policy")
    assert rec["e_expose"] is False                     # A 행 f01의 대상 = 기준 행 f00의 대상
    assert rec["e_expose_overcount_risk"] is False      # 기준 행이 있어 깨끗한 단일 편집 대조
    assert rec["e_mismatch"] is True                    # 표에 대상 ≠ R(s)인 행이 있다
    assert rec["mismatch_rows"] == ["f00", "f02", "f03", "f04", "f05", "f06", "f08"]
    assert rec["attribution"] == "첫 번째" and rec["equals_r"] is False
    assert rec["metric_expose"] == "exposure_m1" and rec["metric_mismatch"] == "trigger_rate"


def test_policy_equal_to_r_exposes_the_slot_without_triggering(forksets):
    """대조군. 자리 노출 true인데 불일치 행 false — 부등호가 반대로 선다."""
    rec = _pair(forksets, "d01_max_policy_equals_r")
    assert rec["e_expose"] is True and rec["e_expose_witness_kind"] == "a_vs_baseline"
    assert rec["e_mismatch"] is False
    assert rec["attribution"] == "최대" and rec["equals_r"] is True


def test_trigger_rate_and_conditional_exposure_are_not_the_same_number(forksets):
    """사건은 같고 분모가 다르다. 귀속 = R인 쌍이 하나라도 있으면 두 수치가 갈린다."""
    from instruments.exposure import conditional_exposure, trigger_rate

    records = [
        _pair(forksets, "d01_constant_first_policy"),   # 귀속 ≠ R, 불일치 행 true
        _pair(forksets, "d01_max_policy_equals_r"),     # 귀속 = R, 불일치 행 false
        _pair(forksets, "d01_recent_policy"),           # 귀속 ≠ R, 불일치 행 true
    ]
    trig = trigger_rate(records)
    cond = conditional_exposure(records)
    assert (trig["n"], trig["k"], trig["rate"]) == (3, 2, 2 / 3)   # 분모 = 커버리지 안 쌍 전체
    assert (cond["n"], cond["k"], cond["rate"]) == (2, 2, 1.0)     # 분모 = 귀속 ≠ R인 쌍
    assert trig["rate"] != cond["rate"]
    assert cond["excluded_counts"]["not_selected"] == 1
    assert trig["verdict"] == "미판정" and cond["verdict"] == "미판정"   # 분모 < 8 (E8)


def test_two_rates_coincide_only_when_every_pair_differs_from_r(forksets):
    """퇴화 사례를 숨기지 않는다: 모든 쌍이 귀속 ≠ R이면 두 수치는 같아진다."""
    from instruments.exposure import conditional_exposure, trigger_rate

    records = [
        _pair(forksets, "d01_constant_first_policy"),
        _pair(forksets, "d01_recent_policy"),
    ]
    assert trigger_rate(records)["rate"] == conditional_exposure(records)["rate"] == 1.0


def test_trigger_rate_denominator_drops_coverage_out_and_undecided(forksets):
    from instruments.exposure import trigger_rate

    ok = _pair(forksets, "d01_constant_first_policy")
    out = {**ok, "coverage": "out", "model": "m_out"}
    undecided = {**ok, "e_mismatch": None, "model": "m_undecided"}
    r = trigger_rate([ok, out, undecided])
    assert r["n"] == 1 and r["k"] == 1
    assert r["excluded_counts"] == {"coverage_out": 1, "undecided": 1}


def test_same_function_on_prediction_tables_b1_b2(forksets):
    """B1·B2 예측 표에 정책표와 **같은 함수**를 돌린다 (D-027 (3), PREREG §1)."""
    from instruments.exposure import e_mismatch, slot_mismatch

    b1 = slot_mismatch(forksets["b1_prediction_table"]["rows"], method="B1")
    b2 = slot_mismatch(forksets["b2_prediction_table"]["rows"], method="B2")
    assert b1["metric"] == "slot_mismatch_b1" and b1["e_mismatch"] is True
    assert b2["metric"] == "slot_mismatch_b2" and b2["e_mismatch"] is False
    # 번역 불가 행(f02)만 분모에서 빠진다
    assert b1["n_checked"] == 8 and b1["excluded_counts"]["undetermined"] == 1
    assert "f02" not in b1["mismatch_rows"]
    # 같은 함수라는 것을 값으로 확인한다
    assert b1["e_mismatch"] == e_mismatch(forksets["b1_prediction_table"]["rows"])["e_mismatch"]


def test_prediction_table_and_policy_table_go_through_one_pair_record(forksets):
    """예측 표도 같은 쌍 레코드를 낸다. 명제 1을 두 사건으로 나란히 비교하는 자리."""
    from instruments.exposure import pair_record

    b1 = pair_record(
        forksets["b1_prediction_table"]["rows"], forksets["a_feature_ids"], method="B1"
    )
    assert b1["metric_expose"] == "slot_recall_b1"
    assert b1["metric_mismatch"] == "slot_mismatch_b1"
    assert b1["e_expose"] is False          # B1의 번역 표도 상수 '첫 번째'라 자리를 못 드러낸다
    assert b1["e_mismatch"] is True         # 그런데 불일치 행은 있다
    assert b1["attribution"] is None        # 규칙 집합을 안 주면 귀속은 계산하지 않는다


def test_b0_mismatch_is_computable_but_unnamed(forksets):
    """B0의 불일치 행은 계산되지만 PREREG §1의 예측에 없어 척도 이름을 주지 않는다."""
    from instruments.exposure import slot_mismatch

    rows = [dict(r) for r in forksets["b0_prediction_table"]["rows"]]
    for row in rows:
        row["R_s"] = ["sup_002"]
        row["r_defined"] = True
    out = slot_mismatch(rows, method="B0")
    assert out["metric"] is None and out["e_mismatch"] is True


# ------------------------------ L41: 자리 노출률의 귀속 규칙별 분리 보고

def test_exposure_is_reported_by_attribution_rule(forksets):
    from instruments.exposure import exposure_by_attribution

    records = [
        _pair(forksets, "d01_constant_first_policy"),
        _pair(forksets, "d01_max_policy_equals_r"),
        _pair(forksets, "d01_recent_policy"),
    ]
    out = exposure_by_attribution(records)
    assert out["overall"]["rate"] == 2 / 3
    assert out["strata"]["첫 번째"]["rate"] == 0.0     # 상수 정책 층에서는 구조적으로 0
    assert out["strata"]["최대"]["rate"] == 1.0
    assert out["strata"]["최근"]["rate"] == 1.0
    assert out["n_strata"] == 3
    assert all(s["verdict"] == "미판정" for s in out["strata"].values())   # 층 분모 < 8


def test_attribution_key_labels_non_single_attributions(policy_tables):
    from instruments.exposure import attribution_key

    assert attribution_key({"attribution_kind": "single", "attribution": "최대"}) == "최대"
    assert attribution_key({"attribution_kind": "hold", "attribution": "보류"}) == "보류"
    assert attribution_key({"attribution_kind": "out_of_set", "attribution": "집합 밖"}) == "집합 밖"
    assert attribution_key({"attribution_kind": "set", "attribution": ["최근", "최대"]}) == "동률{최근, 최대}"


# ------------------------------ D-027 (1): |V_D| 층화

def test_pair_record_carries_the_rule_set_it_was_read_with(forksets):
    rec = _pair(forksets, "d01_constant_first_policy")
    assert rec["v_d"] == list(RULES_V0) and rec["v_d_size"] == 5


def test_stratified_by_v_d_size(forksets):
    """위임마다 |V_D|가 다르면 분모가 섞이므로 층으로 나눠 낸다 (D-027 (1), L43)."""
    from instruments.exposure import pair_record, stratified, trigger_rate

    five = _pair(forksets, "d01_constant_first_policy")
    four = pair_record(
        forksets["cases"]["d01_constant_first_policy"]["rows"],
        forksets["a_feature_ids"],
        delegation_id="D02",
        model="same_model",
        rules=("첫 번째", "최대", "전부", "없음"),        # '최근' 결합이 없는 위임
    )
    assert four["v_d_size"] == 4
    out = stratified([five, four], "v_d_size", trigger_rate)
    assert set(out["strata"]) == {"4", "5"}
    assert out["overall"]["n"] == 2
