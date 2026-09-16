"""정책표 판독기 합성 검사.

검사 항목 (S0-5 요구): 일관 / 비일관 / 집합 밖 / 동률 / n ≤ 3 보류 / 못 본 행 제외 /
후보 1개 행 / 다중집합 부분·초과 / 옛 임계 대 새 임계의 귀속 차이 표(D-013).
"""

from __future__ import annotations

import copy

from conftest import ROOT
from instruments.policy_reader import compare_modes, read, render_comparison_table

CASE_ORDER = [
    "consistent",
    "single_candidate_row",
    "n5_threshold_gap",
    "tie",
    "hold_n3",
    "out_of_set",
    "unseen_rows",
    "multiset_partial_excess",
    "n4_best3_single",
    "n4_best3_tie",
]


def _case(tables: dict, name: str) -> tuple[list[dict], list[str]]:
    return tables["cases"][name]["rows"], tables["rules"]


def test_consistent(policy_tables):
    rows, rules = _case(policy_tables, "consistent")
    r = read(rows, rules)
    assert r["attribution"] == "첫 번째"
    assert r["attribution_kind"] == "single"
    assert r["n_discriminating"] == 8
    assert r["threshold"] == 7
    assert r["match_counts"]["첫 번째"] == 8
    # 행별 근거가 남는다
    assert all(rec["verdicts"]["첫 번째"] == "정확" for rec in r["rows"])


def test_inconsistent_when_single_candidate_row_counted(policy_tables):
    rows, rules = _case(policy_tables, "single_candidate_row")
    new = read(rows, rules, mode="d013")
    old = read(rows, rules, mode="legacy")
    assert new["n_discriminating"] == 8 and new["attribution"] == "비일관"
    assert old["n_discriminating"] == 7 and old["attribution"] == "첫 번째"
    assert old["excluded_counts"]["single_candidate_legacy"] == 1


def test_single_candidate_row_is_discriminating_under_new_definition(policy_tables):
    rows, rules = _case(policy_tables, "single_candidate_row")
    new = read(rows, rules, mode="d013")
    f07 = next(rec for rec in new["rows"] if rec["state_id"] == "f07")
    assert f07["discriminating"] is True          # {없음}이 ∅을 내므로 구분 행
    assert f07["matched_rules"] == ["없음"]        # ∅ commit은 없음 규칙만 맞힌다


def test_threshold_gap_at_n5(policy_tables):
    rows, rules = _case(policy_tables, "n5_threshold_gap")
    new = read(rows, rules, mode="d013")
    old = read(rows, rules, mode="legacy")
    assert new["n_discriminating"] == 5 and new["threshold"] == 4
    assert new["attribution"] == "첫 번째"
    assert old["threshold"] == 5 and old["attribution"] == "비일관"


def test_tie_is_set_attribution(policy_tables):
    rows, rules = _case(policy_tables, "tie")
    new = read(rows, rules, mode="d013")
    assert new["attribution_kind"] == "set"
    assert set(new["attribution"]) == {"최대", "최근"}
    assert new["recommend_more_rows"] is True
    old = read(rows, rules, mode="legacy")
    assert old["attribution_kind"] == "tie_undefined"


def test_hold_when_three_or_fewer_rows(policy_tables):
    rows, rules = _case(policy_tables, "hold_n3")
    new = read(rows, rules, mode="d013")
    assert new["n_discriminating"] == 3
    assert new["attribution"] == "보류" and new["attribution_kind"] == "hold"
    old = read(rows, rules, mode="legacy")
    assert old["attribution"] == "첫 번째"


def test_out_of_set(policy_tables):
    rows, rules = _case(policy_tables, "out_of_set")
    for mode in ("d013", "legacy"):
        r = read(rows, rules, mode=mode)
        assert r["attribution"] == "집합 밖", mode
        assert r["best_count"] == 0


def test_unseen_rows_excluded_from_denominator(policy_tables):
    rows, rules = _case(policy_tables, "unseen_rows")
    kept = read(rows, rules, drop_unseen=True)
    all_rows = read(rows, rules, drop_unseen=False)
    assert kept["n_discriminating"] == 5 and kept["attribution"] == "첫 번째"
    assert kept["excluded_counts"]["unseen"] == 3
    assert all_rows["n_discriminating"] == 8 and all_rows["attribution"] == "비일관"


def test_undetermined_row_excluded(policy_tables):
    rows, rules = _case(policy_tables, "consistent")
    rows = copy.deepcopy(rows)
    rows[0]["commit_target"] = None          # 전송 오류로 대상 판정 불가
    r = read(rows, rules)
    assert r["excluded_counts"]["undetermined"] == 1
    assert r["n_discriminating"] == 7
    assert r["attribution"] == "첫 번째"


def test_missing_prediction_row_excluded(policy_tables):
    rows, rules = _case(policy_tables, "consistent")
    rows = copy.deepcopy(rows)
    rows[1]["predictions"]["최대"] = None    # 그 행에서 규칙 예측이 정의되지 않음
    r = read(rows, rules)
    assert r["excluded_counts"]["predictions_missing"] == 1
    assert r["n_discriminating"] == 7


def test_multiset_partial_and_excess_are_not_matches(policy_tables):
    rows, rules = _case(policy_tables, "multiset_partial_excess")
    r = read(rows, rules, mode="d013")
    by_id = {rec["state_id"]: rec for rec in r["rows"]}
    assert by_id["f01"]["verdicts"]["전부"] == "부분"
    assert by_id["f02"]["verdicts"]["전부"] == "초과"
    assert by_id["f04"]["verdicts"]["전부"] == "정확"
    assert by_id["f06"]["verdicts"]["전부"] == "혼합"
    assert by_id["f02"]["matched_rules"] == []


def test_threshold_comparison_table(policy_tables, capsys):
    """D-013이 요구한 옛 정의/새 정의의 귀속 차이 표. spec/metrics.md 부록 A와 같은 내용."""
    rules = policy_tables["rules"]
    comparisons = [
        compare_modes(policy_tables["cases"][name]["rows"], rules, label=name)
        for name in CASE_ORDER
    ]
    table = render_comparison_table(comparisons)
    print("\n" + table)

    got = {c["label"]: (c["line"]["귀속 (새)"], c["line"]["귀속 (옛)"]) for c in comparisons}
    assert got["consistent"] == ("첫 번째", "첫 번째")
    assert got["single_candidate_row"] == ("비일관", "첫 번째")
    assert got["n5_threshold_gap"] == ("첫 번째", "비일관")
    assert got["tie"] == ("{최근, 최대}", "동률 미정의 {최근, 최대}")
    assert got["hold_n3"] == ("보류", "첫 번째")
    assert got["out_of_set"] == ("집합 밖", "집합 밖")
    assert got["unseen_rows"] == ("첫 번째", "첫 번째")
    assert got["n4_best3_single"] == ("첫 번째", "비일관")
    assert got["n4_best3_tie"] == ("{첫 번째, 최근}", "비일관")

    differing = sorted(c["label"] for c in comparisons if c["differs"])
    assert differing == ["hold_n3", "n4_best3_single", "n4_best3_tie", "n5_threshold_gap",
                         "single_candidate_row", "tie"]
    out = capsys.readouterr().out
    assert "귀속 (새)" in out


def test_rule_id_mapping_matches_data_convention():
    """상태 파일의 predictions는 규칙 ID로 키를 쓴다(docs/SCHEMA.md §4). 두 표기가 모두 돈다."""
    from instruments.policy_reader import RULE_ID_V0, RULE_IDS_V0, DEFAULT_RULES_V0

    assert tuple(RULE_ID_V0) == DEFAULT_RULES_V0
    assert RULE_IDS_V0 == ("first", "max", "recent", "all", "none")

    rows = [
        {"state_id": "f01", "perturbation_row": "P01", "candidate_count": 3, "exposure_seen": True,
         "commit_target": [{"supplier_id": "SUP-001", "quantity": 358}],
         "predictions": {
             "first": [{"supplier_id": "SUP-001", "quantity": 358}],
             "max": [{"supplier_id": "SUP-001", "quantity": 358}],
             "recent": [{"supplier_id": "SUP-005", "quantity": 358}],
             "all": [{"supplier_id": "SUP-001", "quantity": 358},
                     {"supplier_id": "SUP-004", "quantity": 358},
                     {"supplier_id": "SUP-005", "quantity": 358}],
             "none": []}},
    ]
    r = read(rows, RULE_IDS_V0, min_rows=1)
    assert r["match_counts"] == {"first": 1, "max": 1, "recent": 0, "all": 0, "none": 0}
    assert r["attribution_kind"] == "set"          # first와 max가 동률 → 집합 귀속
    assert r["attribution"] == ["first", "max"]


# ---------------------------------------------------- L47: n = 4 경계와 우선순위

def test_n4_best3_single_attribution(policy_tables):
    """구분 행 4, 최고 일치 3 → 임계 n−1 = 3을 채워 단일 귀속."""
    rows, rules = _case(policy_tables, "n4_best3_single")
    r = read(rows, rules)
    assert r["n_discriminating"] == 4 and r["threshold"] == 3 and r["best_count"] == 3
    assert r["attribution"] == "첫 번째" and r["attribution_kind"] == "single"
    old = read(rows, rules, mode="legacy")
    assert old["threshold"] == 4 and old["attribution"] == "비일관"


def test_n4_best3_tie_is_set(policy_tables):
    """같은 3행에서 두 규칙이 동률 → 집합 귀속 + 구분 행 추가 권고."""
    rows, rules = _case(policy_tables, "n4_best3_tie")
    r = read(rows, rules)
    assert r["n_discriminating"] == 4 and r["best_count"] == 3
    assert r["attribution_kind"] == "set"
    assert r["attribution"] == ["첫 번째", "최근"]
    assert r["recommend_more_rows"] is True


def test_hold_precedes_out_of_set(policy_tables):
    """n ≤ 3이고 최고 일치 0이어도 보류가 먼저다 (L47 우선순위)."""
    rows, rules = _case(policy_tables, "hold_n3")
    rows = copy.deepcopy(rows)
    for rec in rows:
        if rec["candidate_count"]:
            rec["commit_target"] = ["sup_009"]      # 어느 규칙도 못 맞힘
    r = read(rows, rules)
    assert r["n_discriminating"] == 3 and r["best_count"] == 0
    assert r["attribution_kind"] == "hold"          # out_of_set이 아니다


def test_min_rows_default_is_four(policy_tables):
    """게이트 계산은 min_rows 기본값 4를 쓴다. 인자는 합성 검사에서만 바꾼다 (D-013)."""
    import inspect

    from instruments.policy_reader import read as read_fn

    assert inspect.signature(read_fn).parameters["min_rows"].default == 4
    rows, rules = _case(policy_tables, "hold_n3")
    assert read(rows, rules, min_rows=3)["attribution"] == "첫 번째"   # 기본값이 아니면 달라진다
    assert read(rows, rules)["attribution"] == "보류"


def test_tie_undefined_is_comparison_mode_only(policy_tables):
    """tie_undefined는 비교 모드에서만 나오고 기록되는 attribution_kind에 없다."""
    from instruments.policy_reader import ATTRIBUTION_KINDS

    for name in policy_tables["cases"]:
        r = read(policy_tables["cases"][name]["rows"], policy_tables["rules"])
        assert r["attribution_kind"] != "tie_undefined", name
        assert r["attribution_kind"] in ATTRIBUTION_KINDS
    tie = read(policy_tables["cases"]["tie"]["rows"], policy_tables["rules"], mode="legacy")
    assert tie["attribution_kind"] == "tie_undefined"


# ------------------------------- L35: 구분 행 정의를 두 프로그램이 공유하는가

def test_read_uses_the_single_discriminating_definition(policy_tables):
    """판정에 쓴 구분 행 ⊆ 상태 수준 구분 행. 롤아웃 사유가 없으면 같다."""
    from instruments.policy_reader import discriminating_row_ids

    for name, case in policy_tables["cases"].items():
        rows, rules = case["rows"], policy_tables["rules"]
        judged = read(rows, rules)["discriminating_rows"]
        state_level = discriminating_row_ids(rows, rules)
        assert set(judged) <= set(state_level), name
        if name != "unseen_rows":                      # 못 본 행이 있는 사례만 부분집합
            assert judged == state_level, name


def test_inapplicable_row_is_discriminating(policy_tables):
    """적용 불가 행도 예측이 갈리면 구분 행이다. excluded에 inapplicable 칸은 없다 (L35)."""
    from instruments.policy_reader import EXCLUSION_REASONS, discriminating_row_ids

    assert "inapplicable" not in EXCLUSION_REASONS
    rows, rules = _case(policy_tables, "consistent")
    rows = copy.deepcopy(rows)
    rows[3]["applicable"] = False           # 섭동이 환경에 적용되지 않은 행
    rows[3]["is_baseline"] = True
    assert "f04" in discriminating_row_ids(rows, rules)
    r = read(rows, rules)
    assert r["n_discriminating"] == 8
    f04 = next(rec for rec in r["rows"] if rec["state_id"] == "f04")
    assert f04["discriminating"] is True and f04["applicable"] is False


def test_d01_shares_the_definition():
    """D01의 fork index.yaml로 정의 일치를 확인한다(읽기만).

    현재는 `src/gen/checks.py`가 적용 불가 행(f04)을 구분 행에서 빼므로 파일의 목록이
    판독기보다 적다(6 대 7). L35 통일 후 D01을 다시 생성하면 같아진다. 이 검사는 값을
    고정하지 않고 **차이가 적용 불가 행에서만 난다**는 것을 확인한다.
    """
    import pytest

    yaml = pytest.importorskip("yaml")
    path = ROOT / "data" / "delegations" / "D01" / "states" / "fork" / "index.yaml"
    if not path.exists():
        pytest.skip("D01 없음 (delegation-author 산출물)")

    from instruments.policy_reader import discriminating_row_ids

    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = list(doc["rule_ids"].values())
    rows = doc["states"]
    ours = set(discriminating_row_ids(rows, rules))
    theirs = set(doc.get("discriminating_rows") or [])
    assert ours, "판독기가 구분 행을 하나도 못 찾았다(상태 파일의 predictions 형 확인)"

    by_id = {str(st["state_id"]): st for st in rows}
    only_theirs = theirs - ours
    only_ours = ours - theirs
    assert not only_theirs, f"파일에만 있는 구분 행: {sorted(only_theirs)}"
    assert all(by_id[i].get("applicable") is False for i in only_ours), (
        f"적용 불가가 아닌 행에서 차이: {sorted(only_ours)}"
    )
