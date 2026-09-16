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
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .normalize import as_multiset, match_verdict
from .provenance import contains_value, haystack, prior_results

__all__ = [
    "ROW_FEATURE_V1",
    "coverage_of",
    "a_rows",
    "e_expose",
    "e_mismatch",
    "attribution_equals_r",
    "false_alarm_input",
    "r_diagnostics",
    "exposure_seen",
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

    - `r_expressible_in_v`: V에 R과 행동이 같은 규칙이 있는가. 없으면 "귀속 = R"은 원리상
      불가능하고 정책 정확도는 0이 되므로, 그 위임은 커버리지 밖으로 읽어야 한다.
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
