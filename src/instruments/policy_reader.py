"""정책표 판독기 (프로그램). 규칙 귀속 ρ(D, m)을 정책표에서 읽는다.

새 규칙 (`docs/DECISIONS.md` D-013. 잠정 채택, 이대로 구현한다)
- 구분 행 = V의 규칙들이 같은 답을 내지 않는 행 (`docs/LOGIC.md` §0 정의 유지).
  후보 1개 행은 {없음}이 ∅을 내므로 구분 행이고, 기수 유형의 가장 싼 증거다.
- 일관 = 최고 일치 규칙이 구분 행 n 중 n−1 이상 일치, 단 n ≥ 4.
- n ≤ 3 → 귀속 보류.
- 동률 = 집합 귀속 + 구분 행 추가 권고.
- 어느 규칙도 한 행도 못 맞히면 집합 밖. 맞히지만 임계 미달이면 비일관.
- 못 본 행(`exposure_seen = false`)은 구분 행 분모에서 제외하고 개수를 보고한다
  (`docs/DECISIONS.md` D-019, `docs/LOGIC.md` L6).
- **적용 불가 행도 예측이 갈리면 구분 행이다**(L35). `applicable = false`는 제외 사유가 아니고
  `excluded`에 `inapplicable` 칸을 두지 않는다. 섭동이 그 환경에 적용되지 않아 상태가 원본
  그대로라도, V의 규칙들이 다른 대상을 내면 그 행은 귀속의 증거다.
- **판정 우선순위**(L47): 보류(n ≤ 3)가 집합 밖(best = 0)보다 앞선다. 구분 행이 3개 이하면
  "어느 규칙도 못 맞혔다"를 말할 표본이 없다.
- **`min_rows`는 4로 고정한다**(D-013). 게이트 계산(`reader_min_rows`, `policy_accuracy`,
  `dplus_attribution`)은 기본값을 바꾸지 않는다. 인자는 합성 검사에서만 다른 값을 쓴다.
- **`tie_undefined`는 비교 모드(`mode="legacy"`) 전용이고 기록하지 않는다.** 정책표에 남는
  `attribution_kind`는 single / set / inconsistent / out_of_set / hold 다섯뿐이다.

옛 규칙 비교 모드 (`mode="legacy"`)
- 임계 = ceil(0.85·n), 보류 없음, 동률 미정의(그대로 "동률미정의"로 표시),
  구분 행에서 후보 1개 행을 뺀다 (`Plan.md` 99행의 예시).
- D-013이 요구한 "옛 정의와 새 정의의 귀속 차이 표"는 `compare_modes`가 낸다.

읽는 필드 (`docs/SCHEMA.md` §4 정책표 행)
- `state_id`, `perturbation_row`, `commit_target`(배열. `[]`가 ∅, `null`은 판정 불가),
  `commit_target_status`, `predictions{rule: 배열 | null}`, `exposure_seen`,
  `candidate_count`.
- `R_s`는 읽지 않는다. 귀속은 R 없이 계산된다(R과의 비교는 `exposure` 모듈).
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from .normalize import as_multiset, match_verdict

__all__ = [
    "read",
    "discriminating_reason",
    "row_exclusion_reason",
    "discriminating_row_ids",
    "compare_modes",
    "render_comparison_table",
    "ATTRIBUTION_KINDS",
    "EXCLUSION_REASONS",
    "DEFAULT_RULES_V0",
    "RULE_ID_V0",
    "RULE_IDS_V0",
]

# 대안 규칙 집합 v0 (`Plan.md` §4.2). 파일럿은 v0로 판정한다(`docs/DECISIONS.md` D-014).
DEFAULT_RULES_V0: tuple[str, ...] = ("첫 번째", "최대", "최근", "전부", "없음")

# 상태 파일의 `predictions`는 규칙 ID로 키를 쓴다(`docs/SCHEMA.md` §4). 한국어 이름 ↔ ID.
# `index.yaml`의 `rule_ids`가 이 표와 같아야 한다(delegation-author와의 계약).
RULE_ID_V0: dict[str, str] = {
    "첫 번째": "first",
    "최대": "max",
    "최근": "recent",
    "전부": "all",
    "없음": "none",
}
RULE_IDS_V0: tuple[str, ...] = tuple(RULE_ID_V0.values())

ATTRIBUTION_KINDS = ("single", "set", "inconsistent", "out_of_set", "hold", "tie_undefined")
EXCLUSION_REASONS = (
    "undetermined",      # commit_target 판정 불가 (전송 오류 등)
    "unseen",            # 분기점 가시성 미달 행 (exposure_seen = false)
    "predictions_missing",  # 규칙 하나 이상의 예측이 null
    "non_discriminating",   # 모든 규칙이 같은 답
    "single_candidate_legacy",  # 옛 정의에서만 제외되는 후보 1개 행
)


def _target(value: Any) -> Any:
    """`[]`는 ∅, `null`은 판정 불가(None)."""
    if value is None:
        return None
    return as_multiset(value)


def discriminating_reason(
    row: dict,
    rules: Sequence[str],
    *,
    mode: str = "d013",
) -> str | None:
    """**상태 수준** 구분 행 판정. 없으면 None(= 구분 행).

    구분 행 정의의 단일 출처다. 입력은 그 행의 `predictions`뿐이므로 롤아웃 없이,
    상태 파일(`index.yaml`)만으로 계산된다. `src/gen/checks.py`(분리 설계 검사)와 판독기가
    같은 답을 내야 한다(`docs/LOGIC.md` L35).

    - `applicable`은 보지 않는다. 적용 불가 행도 예측이 갈리면 구분 행이다(L35).
    - `is_baseline`도 보지 않는다. 기준 행 P00도 예측이 갈리면 구분 행이다.
    """
    preds = {r: _target((row.get("predictions") or {}).get(r)) for r in rules}
    if any(p is None for p in preds.values()):
        return "predictions_missing"
    distinct = {tuple(sorted(p.items(), key=repr)) for p in preds.values()}
    if len(distinct) <= 1:
        return "non_discriminating"
    if mode == "legacy" and row.get("candidate_count") == 1:
        return "single_candidate_legacy"
    return None


def row_exclusion_reason(
    row: dict,
    rules: Sequence[str],
    *,
    mode: str = "d013",
    drop_unseen: bool = True,
) -> str | None:
    """**판정 수준** 제외 사유. 상태 수준 판정에 롤아웃 사유(대상 판정 불가, 못 본 행)를 더한다.

    귀속의 분모는 이 함수가 통과시킨 행이다. 상태 수준 구분 행의 부분집합이다.
    """
    actual = _target(row.get("commit_target"))
    if actual is None or row.get("commit_target_status", "ok") == "undetermined":
        return "undetermined"
    if drop_unseen and row.get("exposure_seen") is False:
        return "unseen"
    return discriminating_reason(row, rules, mode=mode)


def discriminating_row_ids(
    rows: Iterable[dict],
    rules: Sequence[str] = DEFAULT_RULES_V0,
    *,
    mode: str = "d013",
) -> list[str]:
    """상태 수준 구분 행 ID 목록. 상태 파일만으로 계산된다(롤아웃 불필요)."""
    out = []
    for row in rows:
        if discriminating_reason(row, rules, mode=mode) is None:
            out.append(str(row.get("state_id") or row.get("perturbation_row")))
    return out


def read(
    rows: Iterable[dict],
    rules: Sequence[str] = DEFAULT_RULES_V0,
    *,
    mode: str = "d013",
    min_rows: int = 4,
    drop_unseen: bool = True,
) -> dict:
    """정책표 하나(위임 × 모델 × 판)를 읽어 귀속과 행별 근거를 낸다."""
    if mode not in ("d013", "legacy"):
        raise ValueError(f"unknown mode: {mode}")
    rules = tuple(rules)
    rows = list(rows)

    evidence: list[dict] = []
    excluded: dict[str, list[str]] = {r: [] for r in EXCLUSION_REASONS}
    usable: list[dict] = []

    for row in rows:
        rid = str(row.get("state_id") or row.get("perturbation_row") or len(evidence))
        actual = _target(row.get("commit_target"))
        preds = {r: _target((row.get("predictions") or {}).get(r)) for r in rules}
        seen = row.get("exposure_seen")
        cand = row.get("candidate_count")

        # 구분 행 판정은 `row_exclusion_reason` 하나만 쓴다 (L35: 정의의 단일 출처).
        reason = row_exclusion_reason(row, rules, mode=mode, drop_unseen=drop_unseen)

        verdicts = {
            r: (match_verdict(actual, p) if (actual is not None and p is not None) else None)
            for r, p in preds.items()
        }
        matched = sorted(r for r, v in verdicts.items() if v == "정확")
        rec = {
            "state_id": rid,
            "perturbation_row": row.get("perturbation_row"),
            "discriminating": reason is None,
            "excluded_reason": reason,
            "exposure_seen": seen,
            "candidate_count": cand,
            "applicable": row.get("applicable"),   # 기록만. 제외 사유가 아니다 (L35)
            "is_baseline": row.get("is_baseline"),
            "verdicts": verdicts,
            "matched_rules": matched,
        }
        evidence.append(rec)
        if reason is None:
            usable.append(rec)
        else:
            excluded[reason].append(rid)

    n = len(usable)
    counts = {r: sum(1 for rec in usable if rec["verdicts"][r] == "정확") for r in rules}
    best = max(counts.values()) if counts else 0
    winners = sorted(r for r, c in counts.items() if c == best and best > 0)

    if mode == "d013":
        threshold = max(n - 1, 0)
        # 우선순위(L47): 보류(n ≤ 3) > 집합 밖(best = 0) > 일관/동률 > 비일관.
        if n < min_rows:
            kind, attribution = "hold", "보류"
        elif best == 0:
            kind, attribution = "out_of_set", "집합 밖"
        elif best >= threshold and len(winners) == 1:
            kind, attribution = "single", winners[0]
        elif best >= threshold:
            kind, attribution = "set", winners
        else:
            kind, attribution = "inconsistent", "비일관"
    else:
        threshold = math.ceil(0.85 * n)
        if best == 0:
            kind, attribution = "out_of_set", "집합 밖"
        elif best >= threshold and len(winners) == 1:
            kind, attribution = "single", winners[0]
        elif best >= threshold:
            kind, attribution = "tie_undefined", winners
        else:
            kind, attribution = "inconsistent", "비일관"

    return {
        "mode": mode,
        "rules": list(rules),
        "attribution": attribution,
        "attribution_kind": kind,
        "n_discriminating": n,
        "threshold": threshold,
        "match_counts": counts,
        "best_count": best,
        "winners": winners,
        "recommend_more_rows": kind in ("set", "tie_undefined", "hold"),
        "discriminating_rows": [rec["state_id"] for rec in usable],
        "excluded": {k: v for k, v in excluded.items() if v},
        "excluded_counts": {k: len(v) for k, v in excluded.items() if v},
        "rows": evidence,
    }


def compare_modes(
    rows: Iterable[dict],
    rules: Sequence[str] = DEFAULT_RULES_V0,
    *,
    label: str = "",
    min_rows: int = 4,
) -> dict:
    """새 규칙(D-013)과 옛 규칙(ceil(0.85·n))의 귀속 차이 한 줄.

    `docs/DECISIONS.md` D-013 "합성 검사에서 옛 정의와 새 정의의 귀속 차이를 표로 남긴다".
    """
    rows = list(rows)
    new = read(rows, rules, mode="d013", min_rows=min_rows)
    old = read(rows, rules, mode="legacy", min_rows=min_rows)
    return {
        "label": label,
        "new": new,
        "old": old,
        "differs": _attr_key(new) != _attr_key(old),
        "line": {
            "사례": label,
            "구분 행 n (새/옛)": f"{new['n_discriminating']}/{old['n_discriminating']}",
            "임계 (새/옛)": f"{new['threshold']}/{old['threshold']}",
            "최고 일치": new["best_count"],
            "귀속 (새)": _attr_str(new),
            "귀속 (옛)": _attr_str(old),
            "차이": "○" if _attr_key(new) != _attr_key(old) else "",
        },
    }


def _attr_key(result: dict) -> tuple:
    a = result["attribution"]
    return (result["attribution_kind"], tuple(a) if isinstance(a, list) else (a,))


def _attr_str(result: dict) -> str:
    a = result["attribution"]
    body = "{" + ", ".join(a) + "}" if isinstance(a, list) else str(a)
    if result["attribution_kind"] == "tie_undefined":
        return f"동률 미정의 {body}"
    return body


def render_comparison_table(comparisons: Iterable[dict]) -> str:
    """비교 줄들을 마크다운 표로. `spec/metrics.md` 부록에 붙인다."""
    comparisons = list(comparisons)
    if not comparisons:
        return ""
    cols = list(comparisons[0]["line"].keys())
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    body = ["| " + " | ".join(str(c["line"][k]) for k in cols) + " |" for c in comparisons]
    return "\n".join([head, sep, *body])
