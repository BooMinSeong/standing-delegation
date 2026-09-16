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

단일 편집 대조의 한계 (합성 검사와 `spec/metrics.md` 예외 처리에 적혀 있다)
F는 같은 기준 상태에 편집 하나씩을 가한 8행이고 기준 행(무편집)이 없다. A(D) 행과 비 A(D)
행의 대상이 다를 때 그 차이가 A(D) 때문인지 그 행 자신의 편집 때문인지 표 안에서 가릴 수
없다. 그래서 `baseline_row_id`(무편집 행)가 표에 있으면 A 행 대 기준 행으로만 판정하고,
없으면 쌍 비교로 판정하되 `overcount_risk = True`를 함께 낸다. 기준 행 1행 추가를 권고한다.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .normalize import as_multiset, match_verdict
from .provenance import contains_value, haystack, prior_results

__all__ = [
    "ROW_FEATURE_V1",
    "a_rows",
    "e_expose",
    "e_mismatch",
    "attribution_equals_r",
    "r_diagnostics",
    "exposure_seen",
]

# fork set 8행 → 주 특징 ID. `docs/derivation/perturbation-v1.md` §7.2와 `derive.py` ROWS_V1.
# `docs/DECISIONS.md` D-010의 선택 결과 그대로. 이 표를 바꾸려면 DECISIONS를 먼저 고친다.
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
    `feature_ids`가 비면 커버리지 밖 위임이므로 분모에서 뺀다(`e_expose = None`).
    """
    rows = list(rows)
    fmap = row_feature_map if row_feature_map is not None else ROW_FEATURE_V1
    want = set(feature_ids or ())
    if not want:
        return {
            "e_expose": None,
            "reason": "coverage_out",
            "a_rows": [],
            "n_usable": 0,
            "excluded": {},
            "overcount_risk": False,
        }

    usable, dropped = _usable(rows, target_key=target_key, drop_unseen=drop_unseen)

    def rid(row: dict) -> str:
        return str(row.get("state_id") or row.get("perturbation_row"))

    def tgt(row: dict):
        return as_multiset(row.get(target_key))

    a_set = [r for r in usable if fmap.get(str(r.get("perturbation_row"))) in want]
    a_ids = {id(r) for r in a_set}
    rest = [r for r in usable if id(r) not in a_ids]
    base = None
    if baseline_row_id is not None:
        base = next((r for r in usable if rid(r) == str(baseline_row_id)), None)

    if not a_set:
        return {
            "e_expose": None,
            "reason": "no_a_row_usable",
            "a_rows": [],
            "n_usable": len(usable),
            "excluded": dropped,
            "overcount_risk": False,
        }

    witness = None
    within = False
    for i, a in enumerate(a_set):
        for b in a_set[i + 1 :]:
            if tgt(a) != tgt(b):
                within, witness = True, (rid(a), rid(b))
                break
        if within:
            break

    if base is not None:
        against_base = None
        for a in a_set:
            if rid(a) == rid(base):
                continue
            if tgt(a) != tgt(base):
                against_base = (rid(a), rid(base))
                break
        value = bool(within or against_base)
        return {
            "e_expose": value,
            "reason": None,
            "a_rows": [rid(r) for r in a_set],
            "n_usable": len(usable),
            "within_a_diff": within,
            "a_vs_baseline_diff": bool(against_base),
            "baseline_used": True,
            "witness": witness or against_base,
            "overcount_risk": False,
            "excluded": dropped,
        }

    cross = None
    for a in a_set:
        for x in rest:
            if tgt(a) != tgt(x):
                cross = (rid(a), rid(x))
                break
        if cross:
            break

    value = bool(within or cross)
    return {
        "e_expose": value,
        "reason": None,
        "a_rows": [rid(r) for r in a_set],
        "n_usable": len(usable),
        "within_a_diff": within,
        "a_vs_rest_diff": bool(cross),
        "baseline_used": False,
        "witness": witness or cross,
        "overcount_risk": bool(cross and not within),
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
