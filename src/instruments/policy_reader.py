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
        status = row.get("commit_target_status", "ok")
        preds = {r: _target((row.get("predictions") or {}).get(r)) for r in rules}
        seen = row.get("exposure_seen")
        cand = row.get("candidate_count")

        reason: str | None = None
        if actual is None or status == "undetermined":
            reason = "undetermined"
        elif drop_unseen and seen is False:
            reason = "unseen"
        elif any(p is None for p in preds.values()):
            reason = "predictions_missing"
        else:
            distinct = {tuple(sorted(p.items(), key=repr)) for p in preds.values()}
            if len(distinct) <= 1:
                reason = "non_discriminating"
            elif mode == "legacy" and cand == 1:
                reason = "single_candidate_legacy"

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
