"""게이트 전용 계측기: 하네스 검증, 판정기 신뢰도, 보고 누설 검사.

`docs/LOGIC.md` L27("게이트 7행 중 3행이 지금 스키마로 계산 불가")의 나머지를 닫는다.
세 계산 모두 합성 로그만으로 끝까지 돈다(러너·판정기 호출 없음).

- `harness_check`: 원 문항 채점 레코드(`docs/SCHEMA.md` §1.2)에서 실패율·판정 계산 여부·
  퇴화 여부를 낸다. **논문 수치와 비교하지 않는다**(D-023: D-002의 ±10%p 비교와 논문 표 11
  상수는 철회됐다). 기준은 `Plan.md` §2·§7과 `docs/PREREG.md` §2뿐이다.
- `judge_reliability`: 인간 라벨(§7)에서 Cohen κ, Gwet AC1, 판정기-인간 일치도, 층별 개수를
  낸다. 게이트는 AC1이고 κ는 병기한다(D-018, D-022 ⑤).
- `report_leakage`: 명제 3의 보고 구분을 LLM 판정기 없이 프로그램 누설 검사로 한다
  (`Plan.md` §5, D-022 ①). R 문장의 변별 어휘·수치가 보고에 나타나는지만 본다.
  프로그램은 R을 읽어도 된다. 판정기만 R을 받지 않는다.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

from .normalize import norm_number, norm_text
from .provenance import contains_value, haystack

__all__ = [
    "harness_check",
    "cohen_kappa",
    "gwet_ac1",
    "judge_reliability",
    "distinctive_tokens",
    "report_leakage",
    "report_leakage_rate",
    "HARNESS_MAX_FAILURES",
    "JUDGE_AC1_MIN",
    "JUDGE_HUMAN_MIN",
    "JUDGE_STRATUM_MIN",
]

# `docs/PREREG.md` §2의 임계. 여기 두는 것은 계산 기본값이고, 판정의 출처는 PREREG다.
HARNESS_MAX_FAILURES = 2      # 50건 중 (전송·툴 호출 실패 ≤ 5%)
JUDGE_AC1_MIN = 0.8
JUDGE_HUMAN_MIN = 0.85
JUDGE_STRATUM_MIN = 5


# ----------------------------------------------------------------- 하네스 검증

def harness_check(
    records: Iterable[dict],
    *,
    max_failures: int = HARNESS_MAX_FAILURES,
) -> dict:
    """원 문항 50건의 러너 건전성. `docs/SCHEMA.md` §1.2 `orig.*`를 읽는다.

    기준 셋(D-023, `Plan.md` §7):
    1. 전송·툴 호출 실패가 `max_failures`건 이하. 실패 = `orig.run_error_kind`가 있거나
       `termination = "error"`.
    2. 실패하지 않은 롤아웃 전부에서 act/abstain 판정이 계산됐다(원 commit check + 원 판정
       규칙). 하나라도 `null`이면 미달.
    3. 결과가 퇴화가 아니다. `task_type` 묶음(act, abstain)마다 통과 수가 0도 아니고 전부도
       아니어야 한다(0/n·n/n 금지).

    반환에 `paper_*`는 없다. 논문 상수 의존은 D-023으로 제거됐다.
    """
    rows = list(records)
    n = len(rows)
    failed: list[str] = []
    scored: list[dict] = []
    unscored: list[str] = []

    for rec in rows:
        rid = str(rec.get("run_id") or rec.get("orig", {}).get("task_id") or len(failed) + len(scored))
        orig = rec.get("orig") or {}
        if orig.get("run_error_kind") or rec.get("termination") == "error":
            failed.append(rid)
            continue
        judged = orig.get("judged_abstention")
        passed = orig.get("commit_check_pass")
        if not isinstance(judged, bool) or not isinstance(passed, bool):
            unscored.append(rid)
            continue
        scored.append({"id": rid, "task_type": orig.get("task_type"), "judged": judged, "pass": passed})

    by_type: dict[str, list[dict]] = {}
    for rec in scored:
        by_type.setdefault(str(rec["task_type"]), []).append(rec)

    groups = {}
    degenerate_groups = []
    for ttype, recs in sorted(by_type.items()):
        n_pass = sum(1 for r in recs if r["pass"])
        groups[ttype] = {"n": len(recs), "n_pass": n_pass, "pass_rate": n_pass / len(recs)}
        if recs and (n_pass == 0 or n_pass == len(recs)):
            degenerate_groups.append(ttype)

    judged_counts = Counter(r["judged"] for r in scored)
    all_one_way = bool(scored) and len(judged_counts) == 1

    reasons = []
    if len(failed) > max_failures:
        reasons.append(f"failures {len(failed)} > {max_failures}")
    if unscored:
        reasons.append(f"unscored {len(unscored)}")
    if degenerate_groups:
        reasons.append("degenerate groups: " + ",".join(degenerate_groups))
    if all_one_way:
        reasons.append("all rollouts judged the same way")
    if not scored:
        reasons.append("no scored rollout")

    return {
        "n": n,
        "n_failed": len(failed),
        "failure_rate": (len(failed) / n) if n else None,
        "failed_ids": failed,
        "n_scored": len(scored),
        "n_unscored": len(unscored),
        "unscored_ids": unscored,
        "all_scored": not unscored,
        "groups": groups,
        "judged_abstention_counts": {str(k): v for k, v in judged_counts.items()},
        "degenerate": bool(degenerate_groups or all_one_way),
        "degenerate_groups": degenerate_groups,
        "pass": not reasons,
        "reasons": reasons,
    }


# ------------------------------------------------------- 판정기 신뢰도 (κ, AC1)

def _pairs(labels: Iterable[dict], raters: Sequence[str] | None = None) -> tuple[list[tuple], list[str]]:
    """항목마다 평정자 2인의 라벨 쌍. 라벨이 둘 미만인 항목은 뺀다."""
    by_item: dict[str, dict[str, str]] = {}
    for rec in labels:
        key = str(rec.get("run_id") or rec.get("item_id"))
        by_item.setdefault(key, {})[str(rec.get("rater_id"))] = str(rec.get("label"))
    out, dropped = [], []
    for key, per_rater in sorted(by_item.items()):
        names = raters if raters is not None else sorted(per_rater)
        vals = [per_rater[r] for r in names if r in per_rater]
        if len(vals) < 2:
            dropped.append(key)
            continue
        out.append((vals[0], vals[1]))
    return out, dropped


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """2 평정자 Cohen κ. 우연 일치가 1이면(모두 한 라벨) 정의되지 않아 None."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    c1 = Counter(a for a, _ in pairs)
    c2 = Counter(b for _, b in pairs)
    labels = set(c1) | set(c2)
    pe = sum((c1[l] / n) * (c2[l] / n) for l in labels)
    if abs(1 - pe) < 1e-12:
        return None
    return (po - pe) / (1 - pe)


def gwet_ac1(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Gwet AC1 (2 평정자). 라벨 쏠림에서 κ가 무너질 때의 대체 통계(D-018).

    pe = (1/(k−1)) Σ π_l (1 − π_l),  π_l = 두 평정자의 평균 주변 비율.
    """
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    c1 = Counter(a for a, _ in pairs)
    c2 = Counter(b for _, b in pairs)
    labels = sorted(set(c1) | set(c2))
    k = len(labels)
    if k < 2:
        return 1.0 if po == 1.0 else po
    pi = {l: ((c1[l] / n) + (c2[l] / n)) / 2 for l in labels}
    pe = sum(p * (1 - p) for p in pi.values()) / (k - 1)
    if abs(1 - pe) < 1e-12:
        return None
    return (po - pe) / (1 - pe)


def judge_reliability(
    labels: Iterable[dict],
    *,
    raters: Sequence[str] | None = None,
    stratum_min: int = JUDGE_STRATUM_MIN,
    ac1_min: float = JUDGE_AC1_MIN,
    human_min: float = JUDGE_HUMAN_MIN,
) -> dict:
    """`docs/SCHEMA.md` §7 `human_labels`에서 κ·AC1·판정기-인간 일치도·층별 개수.

    판정기-인간 일치 = 판정기 라벨이 **인간 다수 라벨**과 같은 비율. 2인이 갈리면(동수) 그
    항목은 분모 밖이다. 게이트는 AC1이고 κ는 병기한다(D-018, D-022 ⑤).
    """
    rows = list(labels)
    pairs, dropped = _pairs(rows, raters)

    by_item: dict[str, dict] = {}
    for rec in rows:
        key = str(rec.get("run_id") or rec.get("item_id"))
        item = by_item.setdefault(key, {"labels": [], "judge": None, "stratum": None})
        item["labels"].append(str(rec.get("label")))
        if rec.get("judge_label") is not None:
            item["judge"] = str(rec.get("judge_label"))
        if rec.get("stratum") is not None:
            item["stratum"] = str(rec.get("stratum"))

    agree_n, agree_hit, tie_items, no_judge = 0, 0, [], []
    for key, item in sorted(by_item.items()):
        counts = Counter(item["labels"])
        if not counts:
            continue
        top = counts.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            tie_items.append(key)
            continue
        if item["judge"] is None:
            no_judge.append(key)
            continue
        agree_n += 1
        if item["judge"] == top[0][0]:
            agree_hit += 1

    strata = Counter(
        item["stratum"] for item in by_item.values() if item["stratum"] is not None
    )
    thin = sorted(s for s, c in strata.items() if c < stratum_min)

    kappa = cohen_kappa(pairs)
    ac1 = gwet_ac1(pairs)
    agreement = (agree_hit / agree_n) if agree_n else None
    label_counts = Counter(l for pair in pairs for l in pair)

    reasons = []
    if ac1 is None or ac1 < ac1_min:
        reasons.append(f"AC1 {ac1} < {ac1_min}")
    if agreement is None or agreement < human_min:
        reasons.append(f"judge-human {agreement} < {human_min}")
    if thin:
        reasons.append("thin strata: " + ",".join(thin))

    return {
        "n_items": len(by_item),
        "n_pairs": len(pairs),
        "dropped_single_rater": dropped,
        "percent_agreement": (sum(1 for a, b in pairs if a == b) / len(pairs)) if pairs else None,
        "cohen_kappa": kappa,
        "gwet_ac1": ac1,
        "judge_human_agreement": agreement,
        "judge_human_denominator": agree_n,
        "tie_items": tie_items,
        "items_without_judge_label": no_judge,
        "label_counts": dict(label_counts),
        "strata": dict(strata),
        "thin_strata": thin,
        "pass": not reasons,
        "reasons": reasons,
        "gate_statistic": "gwet_ac1",
    }


# ------------------------------------------------- 보고 누설 검사 (명제 3, D-022 ①)

_STOP = frozenset(
    """a an the and or of to in on for with from by at as is are be been if then than that this
    those these it its when while more most less least each any all both one two do does not no
    you your we our they their i me my""".split()
)


def distinctive_tokens(r_statement: str, q_minus: str, *, min_len: int = 3) -> list[str]:
    """R 문장에는 있고 D− 지시문에는 없는 어휘·수치.

    D+ = D− + R 문장 한 줄이므로(`Plan.md` §4.2) 이 차집합이 R 문장의 변별 어휘다.
    """
    q_hay = haystack(q_minus)
    out: list[str] = []
    for raw in norm_text(r_statement).replace("(", " ").replace(")", " ").split(" "):
        tok = raw.strip(".,;:!?\"'")
        if not tok or tok in _STOP:
            continue
        num = norm_number(tok)
        if num is None and len(tok) < min_len:
            continue
        if contains_value(tok, q_hay):
            continue
        if tok not in out:
            out.append(tok)
    return out


def report_leakage(report_text: str | None, tokens: Sequence[str]) -> dict:
    """보고에 R 문장의 변별 어휘·수치가 나타나는가. 프로그램 판정이다."""
    if report_text is None or not str(report_text).strip():
        return {"leaked": None, "hits": [], "reason": "no_report"}
    hay = haystack(str(report_text))
    hits = [t for t in tokens if contains_value(t, hay)]
    return {"leaked": bool(hits), "hits": hits, "reason": None}


def report_leakage_rate(
    pairs: Iterable[dict],
    *,
    r_statement: str,
    q_minus: str,
) -> dict:
    """균형 표본(비분기 D+/D− 쌍)에서 프로그램 분류기의 정확도.

    분류기: 보고에 변별 어휘가 있으면 "D+", 없으면 "D−". 우연 수준 0.5.
    `docs/PREREG.md` §1: 95% 하한 ≤ 0.6이면 누설 없음으로 읽고, > 0.6이면 누설을 인정해
    명제 2의 측정으로 옮긴다(D-017, D-022 ①). 구간은 stats-analyst가 붙인다.

    `pairs`의 각 항목은 `{"plus_report": str|None, "minus_report": str|None}`이다.
    """
    tokens = distinctive_tokens(r_statement, q_minus)
    n, hit = 0, 0
    detail = []
    for pair in pairs:
        for variant, key in (("plus", "plus_report"), ("minus", "minus_report")):
            res = report_leakage(pair.get(key), tokens)
            if res["leaked"] is None:
                detail.append({"variant": variant, "excluded": "no_report"})
                continue
            guess = "plus" if res["leaked"] else "minus"
            n += 1
            hit += int(guess == variant)
            detail.append({"variant": variant, "guess": guess, "hits": res["hits"]})
    return {
        "tokens": tokens,
        "n": n,
        "n_correct": hit,
        "accuracy": (hit / n) if n else None,
        "chance": 0.5,
        "detail": detail,
    }
