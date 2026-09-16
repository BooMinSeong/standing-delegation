"""자리 노출 E_expose, 불일치 행 E_mismatch, 귀속=R, 분기점 가시성.

이름 분리 (`docs/DECISIONS.md` D-019, `docs/LOGIC.md` L22). 세 수치는 서로 다른 사건이다.
- 자리 노출 `e_expose`: 방법의 산출물만 보고 "A(D)의 값이 v→v′로 바뀌면 대상이 g→g′로
  바뀐다"를 읽을 수 있는가. B0/B1/B2/M1에 같은 사건·같은 분모(D-011). R을 쓰지 않는다.
- 불일치 행 `e_mismatch`: 표에 대상 ≠ R(s)인 행이 있는가. 옛 이름 "조건부 노출률".
  R을 쓴다(채점 오라클). M1 방법 기제 게이트에만 쓴다.
- 분기점 가시성 `exposure_seen`: 그 회차의 조회 결과에 K(s)의 경쟁 개체가 전부 나타났는가.
  v1 `AGENTABSTAIN.md` §12.1, `docs/LOGIC.md` L6.

E_expose를 R 없이 계산하는 방법 (`docs/DECISIONS.md` D-012, `docs/LOGIC.md` L28)
위임마다 delegation-author가 "R이 조건을 거는 섭동표 v1 특징 ID"를 `meta.yaml`에 동결한다.
E_expose는 정책표·예측 표의 `perturbation_row`와 이 동결 매핑만 쓴다. R도 R(s)도 읽지 않는다.

단일 편집 대조와 `overcount_risk` (L33, L39. D-022 ③으로 P00 채택)
F는 같은 기준 상태에 편집 하나씩을 가한 8행 + 기준 행 P00(무편집) = 9행이다. 판정이 "A(D)의
값이 v→v′로 바뀌면 대상이 g→g′로 바뀐다"가 되려면 비교하는 두 행이 **A(D)만 다른 한 쌍**이어야
한다. 깨끗한 쌍은 둘뿐이다.
  (i) A 행 대 기준 행(`is_baseline = true`)  — 편집 하나만 다르다.
  (ii) 같은 특징의 A 행 두 개 — 같은 자리의 두 값이다.
그 밖의 비교(A 행 대 비 A 행, 서로 다른 특징의 A 행 두 개)는 차이의 원인이 A(D)인지 그 행 자신의
편집인지 표 안에서 가릴 수 없으므로 `overcount_risk = True`를 함께 낸다(L39: `|A_rows| ≥ 2`라도
특징이 다르면 깨끗하지 않다). 섭동표 v1의 동결 매핑은 특징 하나에 행 하나이므로 (ii)는 매핑이
한 특징에 여러 행을 주는 경우에만 생긴다.

커버리지 3값 (L40)
`a_feature_ids` 중 동결 매핑(= 그 표의 행들)에 대표 행이 없는 특징을 `unrepresented_feature_ids`로
낸다. `coverage`는 in(전부 대표됨) / partial(일부만) / out(하나도 없음, `a_feature_ids`가 비면
포함)의 3값이다. D01의 `num_extremum`이 partial의 실물이다(8행에 대표 행 P28·P29가 없다).

두 사건을 나란히 놓는다 (`docs/DECISIONS.md` D-027 (3), D-025)
주 주장의 수치는 자리 노출이 아니라 **불일치 행**이다. 상수 정책(예: 언제나 첫 후보)은 자리 값이
바뀌어도 대상이 안 바뀌므로 `e_expose`가 구조적으로 거짓이지만, 그 정책표는 기준 행에서 R과 다른
대상을 내므로 주인의 비준·보강은 촉발된다(D01 실물, L41). 그래서
- `trigger_rate` = D− 정책표에 `e_mismatch`가 참인 (위임, 모델) 비율. 분모는 커버리지 안 D− 쌍
  **전체**. 주 주장(`docs/PREREG.md` §0).
- `conditional_exposure` = **같은 사건**을 귀속 ≠ R인 쌍으로만 조건부화한 것. 방법 기제 게이트.
  사건이 같고 분모만 다르므로 두 수치는 일반적으로 다르다(모든 쌍이 귀속 ≠ R일 때만 같다).
- `slot_mismatch_b1` / `slot_mismatch_b2` = B1·B2의 **예측 표**에 `e_mismatch`를 그대로 돌린 값.
  명제 1을 두 사건(자리 노출, 불일치 행)으로 나란히 비교하기 위한 것이다(`docs/PREREG.md` §1).
  R(s)는 계측기가 상태 파일에서 붙인다. 자리 판정기는 R을 받지 않는다(`spec/judges/slot-judge.md`).

|V_D| 층화 (D-027 (1), L43)
속성 결합이 정의되지 않는 규칙은 그 위임의 V_D에서 빠지므로 위임마다 판독기의 규칙 집합 크기가
다르다. 집합 밖·비일관·보류 비율은 `v_d_size`로 층화해 보고한다. 이 모듈의 `pair_record`가
`v_d`·`v_d_size`를 쌍 레코드에 싣고 `stratified`가 층화를 한다.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from .normalize import as_multiset, match_verdict
from .policy_reader import read as read_policy_table
from .provenance import contains_value, haystack, prior_results

__all__ = [
    "ROW_FEATURE_V1",
    "METHOD_EXPOSE_METRIC",
    "METHOD_MISMATCH_METRIC",
    "MIN_PAIRS",
    "coverage_of",
    "a_rows",
    "e_expose",
    "e_mismatch",
    "slot_mismatch",
    "attribution_equals_r",
    "false_alarm_input",
    "r_diagnostics",
    "exposure_seen",
    "pair_record",
    "attribution_key",
    "trigger_rate",
    "conditional_exposure",
    "exposure_rate",
    "stratified",
    "exposure_by_attribution",
]

# fork set 8행 → 주 특징 ID. `docs/derivation/perturbation-v1.md` §7.2와 `derive.py` ROWS_V1.
# `docs/DECISIONS.md` D-010의 선택 결과 그대로. 이 표를 바꾸려면 DECISIONS를 먼저 고친다.
# P00(무편집 기준 행)은 특징을 건드리지 않으므로 이 표에 없다. A 행이 될 수 없다.
ROW_FEATURE_V1: dict[str, str] = {
    "P01": "cand_uniqueness",
    "P04": "set_size",
    "P07": "status_flag",
    "P09": "relative_time",
    "P11": "content_transfer",
    "P13": "cross_collection",
    "P16": "existence_branch",
    "P18": "default_pointer",
}

# 방법 ↔ 계산 이름. 자리 노출은 네 방법 전부, 불일치 행은 M1·B1·B2에 사전 등록돼 있다
# (`docs/PREREG.md` §1·§2, D-027 (3)). B0의 불일치 행은 같은 함수로 계산은 되지만 예측에
# 없으므로 척도 이름을 주지 않는다(`metric = None`으로 나온다).
METHOD_EXPOSE_METRIC: dict[str, str] = {
    "B0": "slot_recall_b0",
    "B1": "slot_recall_b1",
    "B2": "slot_exposure_b2",
    "M1": "exposure_m1",
}
METHOD_MISMATCH_METRIC: dict[str, str] = {
    "M1": "trigger_rate",
    "B1": "slot_mismatch_b1",
    "B2": "slot_mismatch_b2",
}

# 분모 최소치. `docs/PREREG.md` §2·`spec/metrics.md` §0.1의 E8(D-014, L15).
MIN_PAIRS = 8


def _usable(rows: Iterable[dict], *, target_key: str, drop_unseen: bool) -> tuple[list[dict], dict]:
    keep: list[dict] = []
    dropped = {"undetermined": [], "unseen": []}
    for row in rows:
        rid = str(row.get("state_id") or row.get("perturbation_row"))
        t = row.get(target_key)
        if t is None or row.get("commit_target_status", "ok") == "undetermined":
            dropped["undetermined"].append(rid)
            continue
        if drop_unseen and row.get("exposure_seen") is False:
            dropped["unseen"].append(rid)
            continue
        keep.append(row)
    return keep, {k: v for k, v in dropped.items() if v}


def a_rows(
    rows: Iterable[dict],
    feature_ids: Iterable[str],
    *,
    row_feature_map: dict[str, str] | None = None,
) -> list[str]:
    """A(D)의 값을 바꾸는 행 ID 목록(동결 매핑으로 판정)."""
    fmap = row_feature_map if row_feature_map is not None else ROW_FEATURE_V1
    want = set(feature_ids or ())
    out = []
    for row in rows:
        pr = row.get("perturbation_row")
        if pr is not None and fmap.get(str(pr)) in want:
            out.append(str(row.get("state_id") or pr))
    return out


def coverage_of(
    feature_ids: Iterable[str],
    rows: Iterable[dict] | None = None,
    *,
    row_feature_map: dict[str, str] | None = None,
) -> dict:
    """커버리지 3값과 미대표 특징 (L40).

    `rows`를 주면 그 표에 실제로 있는 행의 특징만 대표로 센다. 주지 않으면 동결 매핑 전체를
    본다. `docs/SCHEMA.md` §4 `coverage`·`unrepresented_feature_ids`.
    """
    fmap = row_feature_map if row_feature_map is not None else ROW_FEATURE_V1
    want = [str(f) for f in (feature_ids or ())]
    if rows is None:
        present = set(fmap.values())
    else:
        present = {fmap.get(str(r.get("perturbation_row"))) for r in rows}
        present.discard(None)
    represented = [f for f in want if f in present]
    unrepresented = [f for f in want if f not in present]
    if not want:
        coverage = "out"
    elif not represented:
        coverage = "out"
    elif unrepresented:
        coverage = "partial"
    else:
        coverage = "in"
    return {
        "coverage": coverage,
        "a_feature_ids": want,
        "represented_feature_ids": represented,
        "unrepresented_feature_ids": unrepresented,
        "n_unrepresented": len(unrepresented),
    }


def e_expose(
    rows: Iterable[dict],
    feature_ids: Iterable[str],
    *,
    row_feature_map: dict[str, str] | None = None,
    target_key: str = "commit_target",
    baseline_row_id: str | None = None,
    drop_unseen: bool = True,
) -> dict:
    """자리 노출 사건. B0/B1/B2/M1 모두 이 함수로 판정한다.

    `rows`는 M1이면 정책표 행, B0/B1/B2면 자리 판정기가 번역한 예측 표 행이다. 형은 같다
    (`docs/SCHEMA.md` §4, §4.1).
    기준 행은 `baseline_row_id`로 주거나, 주지 않으면 `is_baseline = true`인 행에서 찾는다
    (`is_baseline`은 상태 파일 해시가 기준 상태와 같을 때만 true. D-024, L35).
    `feature_ids`가 비면(= 커버리지 밖) 분모에서 뺀다(`e_expose = None`).
    """
    rows = list(rows)
    fmap = row_feature_map if row_feature_map is not None else ROW_FEATURE_V1
    want = set(str(f) for f in (feature_ids or ()))
    cov = coverage_of(feature_ids, rows, row_feature_map=fmap)

    base_out = {
        "e_expose": None,
        "a_rows": [],
        "n_usable": 0,
        "excluded": {},
        "overcount_risk": False,
        **cov,
    }
    # 커버리지 밖 = a_feature_ids가 비었거나, 그 특징들의 대표 행이 표에 하나도 없다(L40).
    if cov["coverage"] == "out":
        return {**base_out, "reason": "coverage_out"}

    usable, dropped = _usable(rows, target_key=target_key, drop_unseen=drop_unseen)

    def rid(row: dict) -> str:
        return str(row.get("state_id") or row.get("perturbation_row"))

    def tgt(row: dict):
        return as_multiset(row.get(target_key))

    def feat(row: dict):
        return fmap.get(str(row.get("perturbation_row")))

    a_set = [r for r in usable if feat(r) in want]
    a_ids = {id(r) for r in a_set}
    rest = [r for r in usable if id(r) not in a_ids]

    # 기준 행이 여럿일 수 있다(P00 + 섭동이 적용 불가여서 상태가 원본인 행). 상태 해시가
    # 같으면 어느 쪽을 써도 같은 판정이지만, P00을 우선해 결정적으로 고른다.
    baselines = [r for r in usable if r.get("is_baseline") is True]
    base = None
    if baseline_row_id is not None:
        base = next((r for r in usable if rid(r) == str(baseline_row_id)), None)
    elif baselines:
        base = next((r for r in baselines if str(r.get("perturbation_row")) == "P00"), baselines[0])

    if not a_set:
        return {**base_out, "reason": "no_a_row_usable", "n_usable": len(usable), "excluded": dropped}

    # (ii) 같은 특징의 A 행 두 개 = 깨끗한 쌍. 서로 다른 특징이면 깨끗하지 않다 (L39).
    within_same, within_cross = None, None
    within_same_possible = False
    for i, a in enumerate(a_set):
        for b in a_set[i + 1 :]:
            same_feature = feat(a) == feat(b)
            if same_feature:
                within_same_possible = True
            if tgt(a) == tgt(b):
                continue
            if same_feature and within_same is None:
                within_same = (rid(a), rid(b))
            elif not same_feature and within_cross is None:
                within_cross = (rid(a), rid(b))

    # (i) A 행 대 기준 행 = 깨끗한 쌍.
    against_base = None
    if base is not None:
        for a in a_set:
            if rid(a) == rid(base):
                continue
            if tgt(a) != tgt(base):
                against_base = (rid(a), rid(base))
                break

    cross = None
    for a in a_set:
        for x in rest:
            if base is not None and rid(x) == rid(base):
                continue
            if tgt(a) != tgt(x):
                cross = (rid(a), rid(x))
                break
        if cross:
            break

    # 깨끗한 대조가 가능하면 그것만으로 판정한다. A(D)가 대상을 바꾸지 않는다는 판정을
    # 다른 특징의 편집이 낸 차이로 뒤집으면 사건이 A(D)의 것이 아니게 된다.
    clean_possible = bool(
        (base is not None and any(rid(a) != rid(base) for a in a_set)) or within_same_possible
    )
    clean = against_base or within_same
    if clean_possible:
        value = bool(clean)
        risk = False
    else:
        value = bool(within_cross or cross)
        risk = bool(value)
    return {
        **cov,
        "e_expose": value,
        "reason": None,
        "a_rows": [rid(r) for r in a_set],
        "a_features": sorted({f for f in (feat(r) for r in a_set) if f}),
        "n_usable": len(usable),
        "within_same_feature_diff": bool(within_same),
        "within_cross_feature_diff": bool(within_cross),
        "a_vs_baseline_diff": bool(against_base),
        "a_vs_rest_diff": bool(cross),
        "baseline_used": base is not None,
        "baseline_row": rid(base) if base is not None else None,
        "n_baseline_rows": len(baselines),
        "clean_comparison_possible": clean_possible,
        "witness": clean or within_cross or cross,
        "witness_kind": (
            "a_vs_baseline" if against_base else
            "within_same_feature" if within_same else
            "within_cross_feature" if within_cross else
            "a_vs_rest" if cross else None
        ) if value else None,
        "overcount_risk": risk,
        "excluded": dropped,
    }


def e_mismatch(
    rows: Iterable[dict],
    *,
    target_key: str = "commit_target",
    drop_unseen: bool = True,
) -> dict:
    """표에 대상 ≠ R(s)인 행이 있는가(옛 조건부 노출률의 사건).

    `r_defined = false`인 행은 분모에서 빼고 개수를 보고한다(D-015, L16).
    """
    rows = list(rows)
    usable, dropped = _usable(rows, target_key=target_key, drop_unseen=drop_unseen)
    dropped = dict(dropped)
    mismatch_rows: list[str] = []
    checked: list[str] = []
    undefined: list[str] = []
    verdicts: dict[str, str] = {}
    for row in usable:
        rid = str(row.get("state_id") or row.get("perturbation_row"))
        if row.get("r_defined") is False or "R_s" not in row:
            undefined.append(rid)
            continue
        v = match_verdict(row.get(target_key), row.get("R_s"))
        verdicts[rid] = v
        checked.append(rid)
        if v != "정확":
            mismatch_rows.append(rid)
    if undefined:
        dropped["r_undefined"] = undefined
    return {
        "e_mismatch": bool(mismatch_rows) if checked else None,
        "mismatch_rows": mismatch_rows,
        "n_checked": len(checked),
        "verdicts": verdicts,
        "excluded": dropped,
        "excluded_counts": {k: len(v) for k, v in dropped.items()},
    }


def slot_mismatch(
    rows: Iterable[dict],
    *,
    method: str,
    target_key: str = "commit_target",
    drop_unseen: bool = True,
) -> dict:
    """정책표(M1)와 예측 표(B0/B1/B2)에 **같은 함수**를 돌린다 (D-027 (3)).

    `rows`의 형은 `docs/SCHEMA.md` §4의 정책표 행과 §4.1의 B 예측 표 행이 같다. 그래서
    불일치 행 사건은 `e_mismatch` 하나로 끝나고, 방법 이름만 결과에 붙인다.

    - M1  → `trigger_rate`(주 주장)의 쌍 단위 사건.
    - B1  → `slot_mismatch_b1`, B2 → `slot_mismatch_b2`(명제 1의 두 번째 사건).
    - 예측 표의 `commit_target = null`(번역 불가)은 그 행만 빠진다. 전부 빠지면 `None`.
    - R(s)는 계측기가 상태 파일에서 붙인 `R_s`에서 읽는다. 판정기는 R을 받지 않는다.
    """
    out = e_mismatch(rows, target_key=target_key, drop_unseen=drop_unseen)
    return {**out, "method": method, "metric": METHOD_MISMATCH_METRIC.get(method)}


def attribution_equals_r(
    reader_result: dict,
    rows: Iterable[dict],
    *,
    target_key: str = "commit_target",
) -> dict:
    """귀속 규칙 = R인가. 정책 정확도와 D+ 귀속 정확도의 사건.

    R은 V의 원소가 아닐 수 있다(`Plan.md` §4.2의 R 유형 4개 대 V v0의 5규칙). 그래서
    "귀속 = R"은 행동 동일성으로 판정한다: 귀속된 규칙의 예측이 구분 행 전부에서 R(s)와
    정확 일치하는가.

    - 귀속이 보류(n ≤ 3)면 미판정(None). `docs/DECISIONS.md` D-014.
    - 귀속이 비일관·집합 밖이면 "귀속 ≠ R"에 포함하되 종류를 따로 낸다(D-014).
    - 동률(집합 귀속)은 엄격 판정에서 ≠ R로 두고, R이 집합 안에 있는지를 `r_in_set`으로
      함께 낸다.
    """
    index = {str(r.get("state_id") or r.get("perturbation_row")): r for r in rows}
    disc = [index[i] for i in reader_result.get("discriminating_rows", []) if i in index]
    kind = reader_result.get("attribution_kind")

    def rule_matches_r(rule: str) -> bool | None:
        ok = True
        seen = 0
        for row in disc:
            if row.get("r_defined") is False or "R_s" not in row:
                continue
            pred = (row.get("predictions") or {}).get(rule)
            if pred is None:
                return None
            seen += 1
            if match_verdict(row.get("R_s"), pred) != "정확":
                ok = False
        return ok if seen else None

    if kind == "hold":
        return {"equals_r": None, "reason": "hold", "attribution_kind": kind, "r_in_set": None}
    if kind in ("out_of_set", "inconsistent"):
        return {"equals_r": False, "reason": kind, "attribution_kind": kind, "r_in_set": False}

    attribution = reader_result.get("attribution")
    if isinstance(attribution, list):
        per = {r: rule_matches_r(r) for r in attribution}
        return {
            "equals_r": False,
            "reason": "tie",
            "attribution_kind": kind,
            "r_in_set": any(v is True for v in per.values()),
            "per_rule": per,
        }
    m = rule_matches_r(str(attribution))
    return {
        "equals_r": m,
        "reason": None if m is not None else "no_r_rows",
        "attribution_kind": kind,
        "r_in_set": m,
    }


def false_alarm_input(
    reader_result: dict,
    rows: Iterable[dict],
    rule_stated_in_q: str | None,
) -> dict:
    """오경보율(#29)의 조건부 사건과 분모 (L38).

    옛 정의(`rule_stated_in_q = no`를 D+ 쌍 전체에 대해 셈)는 귀속 정확도의 여집합이 되어,
    R ∉ V인 위임에서 구조적으로 100%가 된다. 그래서 조건부로 바꾼다.

    - 분모: **귀속 = R인 D+ 쌍**만.
    - 사건: 그 쌍에서 규칙 명시 판정이 "아니오".
    - 귀속 ≠ R인 쌍은 분모 밖이고, 그 이유를 `excluded_reason`에 남긴다. R이 V로 표현되지
      않아서인지(`r_not_expressible`) 모델이 R을 안 따라서인지(`attribution_ne_r`)를 가른다.
    - 귀속 보류(n ≤ 3)와 판정 불가는 분모 밖이다.
    """
    rows = list(rows)
    eq = attribution_equals_r(reader_result, rows)
    diag = r_diagnostics(rows, reader_result.get("rules") or ())

    if eq["equals_r"] is None:
        reason = "hold" if eq.get("reason") == "hold" else "r_undefined"
    elif eq["equals_r"] is False:
        reason = "r_not_expressible" if not diag["r_expressible_in_v"] else "attribution_ne_r"
    elif rule_stated_in_q not in ("yes", "no"):
        reason = "judge_unjudgeable"
    else:
        reason = None

    in_denominator = reason is None
    return {
        "in_denominator": in_denominator,
        "false_alarm": bool(in_denominator and rule_stated_in_q == "no"),
        "equals_r": eq["equals_r"],
        "attribution_kind": eq["attribution_kind"],
        "r_expressible_in_v": diag["r_expressible_in_v"],
        "rule_stated_in_q": rule_stated_in_q,
        "excluded_reason": reason,
    }


def r_diagnostics(
    rows: Iterable[dict],
    rules: Sequence[str],
    *,
    target_key: str = "commit_target",
) -> dict:
    """R과 V·F의 관계. 사후 검사용이며 척도가 아니다(`docs/LOGIC.md` L29).

    - `r_expressible_in_v`: V_D에 R과 행동이 같은 규칙이 있는가. 없으면 "귀속 = R"은 원리상
      불가능하고 `policy_accuracy`·`dplus_attribution`은 구조적으로 0, `false_alarm`의 조건부
      분모는 빈다. 그때는 그 위임을 **이 값으로 층화**해 보고한다. `coverage`(D-012)는
      `a_feature_ids`의 대표 행 유무라는 **다른 축**이므로 둘을 섞어 "커버리지 밖"이라고
      부르지 않는다(D01 `checks.md` 미결 1 (iii)). 기계적 결합(D-027 (1))이 R을 V_D 밖으로
      밀어낼 수 있으므로 이 값은 실물에서 false가 난다.
      주의: 이 값이 false면 모든 쌍이 `equals_r = False`가 되어 `conditional_exposure`의 분모가
      쌍 전체가 되고 `trigger_rate`와 같은 수치가 된다. 두 값을 나란히 적어 퇴화를 드러낸다.
    - `f_discriminates_r`: F의 어느 행에서 R의 예측이 V의 어떤 규칙과 다른가. 아니면 F는
      R을 가르지 못한다.
    """
    rows = [r for r in rows if r.get("r_defined") is not False and "R_s" in r]
    expressible = []
    discriminates = False
    for rule in rules:
        ok = True
        for row in rows:
            pred = (row.get("predictions") or {}).get(rule)
            if pred is None:
                ok = False
                continue
            if match_verdict(row.get("R_s"), pred) != "정확":
                ok = False
                discriminates = True
        if ok and rows:
            expressible.append(rule)
    return {
        "n_rows": len(rows),
        "r_expressible_in_v": bool(expressible),
        "equivalent_rules": expressible,
        "f_discriminates_r": discriminates,
    }


def exposure_seen(
    execution_log: Iterable[dict],
    competing_ids: Iterable[Any],
    *,
    before_first_commit: bool = True,
    kinds: Sequence[str] = ("lookup", "verify"),
) -> dict:
    """분기점 가시성. K(s)의 경쟁 개체가 조회 결과에 전부 나타났는가.

    기본은 첫 commit 시도 이전의 조회·검증 결과만 본다. commit 뒤에 본 개체는 선택에
    쓰이지 않았기 때문이다. `before_first_commit=False`면 회차 전체를 본다.
    결과는 `result`에서 읽는다(v1 `AGENTABSTAIN.md` §11).
    """
    log = list(execution_log or [])
    ids = [i for i in competing_ids or []]
    cutoff = None
    if before_first_commit:
        for entry in log:
            if entry.get("kind") == "commit":
                cutoff = entry.get("step")
                break
    considered = [
        e
        for e in log
        if e.get("kind") in tuple(kinds)
        and (cutoff is None or not isinstance(e.get("step"), int) or e["step"] < cutoff)
    ]
    hay = haystack(prior_results(considered, None))
    seen = [i for i in ids if contains_value(i, hay)]
    unseen = [i for i in ids if i not in seen]
    return {
        "exposure_seen": (len(unseen) == 0) if ids else None,
        "n_competing": len(ids),
        "seen": seen,
        "unseen": unseen,
        "ratio": (len(seen) / len(ids)) if ids else None,
        "cutoff_step": cutoff,
        "n_lookups_considered": len(considered),
    }


# ======================================================== 쌍 레코드와 비율 (D-027)
#
# 여기부터는 (위임, 모델) 쌍 하나의 레코드를 만들고 쌍 집합에서 비율을 내는 부분이다.
# 위의 함수들이 "표 하나"를 읽는다면 이 부분은 "표들"을 읽는다. 척도의 분모가 쌍이므로
# (`spec/metrics.md` §1) 분모 규칙(커버리지, 최소치, 미판정)도 여기 한 곳에 둔다.


def attribution_key(record: dict) -> str:
    """귀속 규칙별 분리 보고(L41)의 층 이름. 단일 귀속이면 규칙 이름, 아니면 종류."""
    kind = record.get("attribution_kind")
    attribution = record.get("attribution")
    if kind == "single" and attribution is not None:
        return str(attribution)
    if kind == "set" and isinstance(attribution, list):
        return "동률{" + ", ".join(str(a) for a in attribution) + "}"
    return {
        "inconsistent": "비일관",
        "out_of_set": "집합 밖",
        "hold": "보류",
    }.get(str(kind), "미판정")


def pair_record(
    rows: Iterable[dict],
    feature_ids: Iterable[str],
    *,
    method: str = "M1",
    delegation_id: str | None = None,
    model: str | None = None,
    variant: str = "minus",
    rules: Sequence[str] | None = None,
    reader_result: dict | None = None,
    row_feature_map: dict[str, str] | None = None,
    target_key: str = "commit_target",
    baseline_row_id: str | None = None,
    drop_unseen: bool = True,
) -> dict:
    """(위임, 모델, 방법) 하나의 쌍 레코드. 비율 함수들의 입력이다.

    한 표에서 세 가지를 함께 낸다.
    1. 자리 노출 `e_expose`(R 없이, 동결 매핑으로).
    2. 불일치 행 `e_mismatch`(R 오라클. `R_s`가 없으면 `None`).
    3. 귀속 ρ와 `equals_r`(판독기. `rules` 또는 `reader_result`를 줄 때만).

    `rules`에는 그 위임의 **V_D**를 넘긴다(D-027 (1)). 넘긴 규칙 집합과 크기가 레코드에
    남아 `stratified(records, "v_d_size", ...)`로 층화된다.
    자리 노출률을 귀속 규칙별로 분리 보고하려면(L41) ρ가 같은 레코드에 있어야 하므로,
    이 함수가 `attribution`·`attribution_kind`·`attribution_key`를 함께 낸다.
    """
    rows = list(rows)
    expose = e_expose(
        rows,
        feature_ids,
        row_feature_map=row_feature_map,
        target_key=target_key,
        baseline_row_id=baseline_row_id,
        drop_unseen=drop_unseen,
    )
    mismatch = slot_mismatch(rows, method=method, target_key=target_key, drop_unseen=drop_unseen)

    reader = reader_result
    if reader is None and rules is not None:
        reader = read_policy_table(rows, tuple(rules), drop_unseen=drop_unseen)

    record = {
        "delegation_id": delegation_id,
        "model": model,
        "variant": variant,
        "method": method,
        "metric_expose": METHOD_EXPOSE_METRIC.get(method),
        "metric_mismatch": METHOD_MISMATCH_METRIC.get(method),
        # 자리 노출
        "e_expose": expose["e_expose"],
        "e_expose_reason": expose.get("reason"),
        "e_expose_overcount_risk": expose["overcount_risk"],
        "e_expose_witness_kind": expose.get("witness_kind"),
        "coverage": expose["coverage"],
        "unrepresented_feature_ids": expose["unrepresented_feature_ids"],
        "n_unrepresented": expose["n_unrepresented"],
        # 불일치 행
        "e_mismatch": mismatch["e_mismatch"],
        "mismatch_rows": mismatch["mismatch_rows"],
        "n_checked": mismatch["n_checked"],
        # 귀속
        "attribution": None,
        "attribution_kind": None,
        "n_discriminating": None,
        "equals_r": None,
        "equals_r_reason": None,
        "v_d": list(rules) if rules is not None else None,
        "v_d_size": len(tuple(rules)) if rules is not None else None,
    }
    if reader is not None:
        eq = attribution_equals_r(reader, rows, target_key=target_key)
        record.update(
            attribution=reader["attribution"],
            attribution_kind=reader["attribution_kind"],
            n_discriminating=reader["n_discriminating"],
            equals_r=eq["equals_r"],
            equals_r_reason=eq.get("reason"),
            v_d=list(reader.get("rules") or []),
            v_d_size=reader.get("v_d_size", len(reader.get("rules") or [])),
        )
    record["attribution_key"] = attribution_key(record)
    return record


def _rate(
    records: Iterable[dict],
    *,
    metric: str,
    event_key: str,
    select: Callable[[dict], bool] | None = None,
    exclude_coverage_out: bool = True,
    min_pairs: int = MIN_PAIRS,
) -> dict:
    """사건 비율 하나. 분모 규칙(커버리지·미판정·최소치)을 한 곳에서 건다.

    - 커버리지 밖(`coverage = "out"`) 쌍은 분모에서 뺀다(E7).
    - 사건이 `None`(미판정)인 쌍은 분모에서 빼고 개수를 보고한다(E3·E4·E5·E9).
    - 분모가 `min_pairs` 미만이면 `verdict = "미판정"`이다(E8, D-014). 값은 그대로 낸다.
    """
    records = list(records)
    excluded = {"coverage_out": 0, "not_selected": 0, "undecided": 0}
    numerator = 0
    denominator: list[dict] = []
    for rec in records:
        if exclude_coverage_out and rec.get("coverage") == "out":
            excluded["coverage_out"] += 1
            continue
        if select is not None and not select(rec):
            excluded["not_selected"] += 1
            continue
        value = rec.get(event_key)
        if value is None:
            excluded["undecided"] += 1
            continue
        denominator.append(rec)
        numerator += 1 if value else 0
    n = len(denominator)
    return {
        "metric": metric,
        "event": event_key,
        "n": n,
        "k": numerator,
        "rate": (numerator / n) if n else None,
        "min_pairs": min_pairs,
        "verdict": "미판정" if n < min_pairs else "판정",
        "excluded_counts": {k: v for k, v in excluded.items() if v},
        "pairs": [(rec.get("delegation_id"), rec.get("model")) for rec in denominator],
    }


def trigger_rate(records: Iterable[dict], *, min_pairs: int = MIN_PAIRS) -> dict:
    """촉발률(주 주장). D− 정책표에 대상 ≠ R(s)인 행이 있는 (위임, 모델) 비율.

    분모 = 커버리지 안 D− 쌍 **전체**. `conditional_exposure`와 사건은 같고 분모가 다르다
    (`docs/DECISIONS.md` D-027 (3), `docs/PREREG.md` §0·§2).
    """
    return _rate(records, metric="trigger_rate", event_key="e_mismatch", min_pairs=min_pairs)


def conditional_exposure(records: Iterable[dict], *, min_pairs: int = MIN_PAIRS) -> dict:
    """불일치 행 비율(방법 기제 게이트). 분모는 **귀속 ≠ R인 쌍**만이다.

    `equals_r`가 `None`(보류·R 정의 불가)인 쌍은 분모 밖이다(E9).
    """
    return _rate(
        records,
        metric="conditional_exposure",
        event_key="e_mismatch",
        select=lambda rec: rec.get("equals_r") is False,
        min_pairs=min_pairs,
    )


def exposure_rate(
    records: Iterable[dict],
    *,
    metric: str | None = None,
    min_pairs: int = MIN_PAIRS,
) -> dict:
    """자리 노출률(#1~4). 방법 이름은 레코드의 `metric_expose`에서 읽는다."""
    records = list(records)
    if metric is None:
        names = {rec.get("metric_expose") for rec in records if rec.get("metric_expose")}
        metric = names.pop() if len(names) == 1 else "slot_exposure"
    return _rate(records, metric=metric, event_key="e_expose", min_pairs=min_pairs)


def stratified(
    records: Iterable[dict],
    by: str | Callable[[dict], Any],
    rate_fn: Callable[..., dict] = exposure_rate,
    *,
    min_pairs: int = MIN_PAIRS,
) -> dict:
    """층화 보고. 층마다 같은 비율 함수를 돌리고 전체도 함께 낸다.

    쓰는 곳: 자리 노출률의 귀속 규칙별 분리(L41, `by="attribution_key"`), 집합 밖·비일관·
    보류 비율의 |V_D|별 분리(D-027 (1), `by="v_d_size"`), 커버리지별 분리(D-012).
    층의 분모가 최소치 미만이면 그 층의 `verdict`가 "미판정"이다. 층을 나누면 분모가 쪼개지므로
    이 값을 반드시 함께 읽는다.
    """
    records = list(records)
    key = by if callable(by) else (lambda rec: rec.get(by))
    groups: dict[Any, list[dict]] = {}
    for rec in records:
        groups.setdefault(key(rec), []).append(rec)
    return {
        "by": by if isinstance(by, str) else getattr(by, "__name__", "callable"),
        "overall": rate_fn(records, min_pairs=min_pairs),
        "strata": {
            str(k): rate_fn(v, min_pairs=min_pairs) for k, v in sorted(groups.items(), key=repr)
        },
        "n_strata": len(groups),
    }


def exposure_by_attribution(records: Iterable[dict], *, min_pairs: int = MIN_PAIRS) -> dict:
    """자리 노출률의 귀속 규칙별 분리 보고 (L41, `docs/PREREG.md` §1).

    상수 정책('첫 번째'·'없음')은 자리 노출이 구조적으로 거짓일 수 있으므로, B 대 M1의
    부등호가 정책 분포의 차인지 보려면 층별로 읽어야 한다.
    """
    return stratified(records, "attribution_key", exposure_rate, min_pairs=min_pairs)
