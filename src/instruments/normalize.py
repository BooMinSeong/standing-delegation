"""정규화와 다중집합 일치 판정.

쓰는 곳
- 산출물 동일성(`Plan.md` §6 D1 "정규화 후"): 비분기 상태에서 D+/D− commit 호출 비교.
- commit 대상 일치 판정(`docs/DECISIONS.md` D-015, `docs/LOGIC.md` L21): commit_target은
  다중집합이고 일치 판정은 정확 / 부분 / 초과다.
- 출처 계산의 값 대조(`provenance`).

정규화 규칙 (`docs/SCHEMA.md` §6에 같은 문장으로 적혀 있다)
1. 인자 순서: dict의 키 순서는 무시한다(키로 정렬).
2. 공백: NFKC 정규화 후 연속 공백을 하나로 줄이고 앞뒤를 자른다. 대소문자는 무시한다.
3. 식별자 표기: "숫자를 포함하고 3자 이상"인 토큰은 식별자로 보고 `-`, `_`, 공백을 지운다
   (식별자 판정 기준은 `docs/derivation/perturbation-v1.md` §2.2 `cand_uniqueness`의
   식별자 토큰 규칙을 그대로 쓴다). `ORD-001`, `ord_001`, `ord 001`은 같은 값이다.
4. 수치: 통화 기호와 천 단위 콤마를 떼고 Decimal로 정규화한다. `$1,200.00` = `1200`.
5. 다중집합: 식별자·수치만으로 된 리스트는 순서를 무시한다(집합성 인자). 본문성 리스트
   (문자열이 섞인 리스트)는 순서를 유지한다 — 섭동표 v1의 `list_order` 특징이 순서 자체를
   대상으로 삼기 때문이다(`docs/derivation/perturbation-v1.md` §3 마지막 단락).

이 모듈은 R도 정답도 읽지 않는다.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any, Hashable, Iterable

__all__ = [
    "norm_text",
    "looks_like_ident",
    "norm_ident",
    "norm_number",
    "norm_value",
    "norm_params",
    "norm_call",
    "calls_multiset",
    "calls_identical",
    "as_multiset",
    "match_verdict",
    "MATCH_LABELS",
    "BODY_KEYS",
]

# 본문성 인자 키. `docs/derivation/perturbation-v1.md` §2.2 `content_transfer`의 목록 그대로.
BODY_KEYS = frozenset(
    {
        "body",
        "content",
        "message",
        "text",
        "summary",
        "justification",
        "note",
        "notes",
        "reason",
        "resolution_note",
        "description",
        "shipment_description",
        "resource_summary",
        "plan_terms",
        "checklist_updates",
        "file_content",
        "config_text",
        "operations",
        "rename_map",
        "seat_requests",
    }
)

_WS = re.compile(r"\s+")
_IDENT_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./\-]*$")
_DIGIT = re.compile(r"\d")
_IDENT_SEP = re.compile(r"[-_\s]+")
_CURRENCY = re.compile(r"^[\s$€£¥₩]+|[\s$€£¥₩]+$")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d\d\d(\D|$))")

MATCH_LABELS = ("정확", "부분", "초과", "혼합", "불일치", "미실행")


def norm_text(value: Any) -> str:
    """공백·대소문자·유니코드 표기를 정규화한 문자열."""
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKC", s)
    s = _WS.sub(" ", s).strip()
    return s.casefold()


def looks_like_ident(value: Any) -> bool:
    """식별자 토큰 판정: 숫자를 포함하고 3자 이상이며 구분자만 섞인 단일 토큰."""
    if isinstance(value, bool) or value is None:
        return False
    s = unicodedata.normalize("NFKC", str(value)).strip()
    if len(s) < 3 or " " in s:
        return False
    if not _DIGIT.search(s):
        return False
    return bool(_IDENT_OK.match(s))


def norm_ident(value: Any) -> str:
    """식별자 표기 정규화: 소문자화 후 `-`, `_`, 공백 제거."""
    return _IDENT_SEP.sub("", norm_text(value))


def norm_number(value: Any) -> str | None:
    """수치로 읽히면 정규 10진 문자열, 아니면 None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            return None
        return _fmt(d)
    if not isinstance(value, str):
        return None
    s = unicodedata.normalize("NFKC", value).strip()
    s = _CURRENCY.sub("", s)
    s = _THOUSANDS.sub("", s)
    if s in ("", "+", "-", "."):
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if not d.is_finite():
        return None
    return _fmt(d)


def _fmt(d: Decimal) -> str:
    d = d.normalize()
    if d == 0:
        return "0"
    return format(d, "f")


def norm_value(value: Any, *, key: str | None = None) -> Hashable:
    """값 하나를 비교 가능한 정규형(해시 가능)으로.

    반환은 `(종류, 내용)` 꼴이다. 종류는 null / bool / num / ident / text / seq / bag / map.
    `key`를 주면 본문성 키(BODY_KEYS)의 리스트는 순서를 유지한다.
    """
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    num = norm_number(value)
    if num is not None:
        return ("num", num)
    if isinstance(value, str):
        if looks_like_ident(value):
            return ("ident", norm_ident(value))
        return ("text", norm_text(value))
    if isinstance(value, dict):
        return ("map", tuple(sorted((norm_text(k), norm_value(v, key=str(k))) for k, v in value.items())))
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [norm_value(v) for v in value]
        if isinstance(value, (set, frozenset)):
            return ("bag", tuple(sorted(Counter(items).items(), key=repr)))
        order_free = _order_free(items) and (key is None or key.lower() not in BODY_KEYS)
        if order_free:
            return ("bag", tuple(sorted(Counter(items).items(), key=repr)))
        return ("seq", tuple(items))
    return ("text", norm_text(value))


def _order_free(items: list[Hashable]) -> bool:
    """식별자·수치·bool만으로 된 리스트는 집합성으로 본다."""
    if not items:
        return True
    return all(isinstance(i, tuple) and i and i[0] in ("ident", "num", "bool", "null") for i in items)


def norm_params(params: Any) -> tuple:
    """인자 dict를 키 정렬된 정규형 튜플로. 인자 순서는 무시된다."""
    if not isinstance(params, dict):
        return (("__value__", norm_value(params)),)
    return tuple(sorted((norm_text(k), norm_value(v, key=str(k))) for k, v in params.items()))


def norm_call(tool: Any, params: Any) -> tuple:
    """commit 호출 하나의 정규형."""
    return (norm_text(tool), norm_params(params))


def calls_multiset(calls: Iterable[dict]) -> Counter:
    """`[{tool, params}, ...]`의 정규형 다중집합."""
    return Counter(norm_call(c.get("tool"), c.get("params")) for c in calls)


def calls_identical(calls_a: Iterable[dict], calls_b: Iterable[dict]) -> bool:
    """두 실행의 commit 호출이 정규화 후 같은 다중집합인가."""
    return calls_multiset(calls_a) == calls_multiset(calls_b)


def as_multiset(value: Any) -> Counter:
    """commit 대상을 다중집합으로. None과 빈 리스트는 ∅(빈 다중집합)이다.

    `docs/DECISIONS.md` D-015. ∅(실행하지 않음)은 정당한 대상이므로 "판정 불가"와
    구분해야 한다. 판정 불가는 호출자가 `commit_target_status`로 따로 표시한다
    (`docs/SCHEMA.md` §3).
    """
    if value is None:
        return Counter()
    if isinstance(value, Counter):
        return Counter({k: v for k, v in value.items() if v})
    if isinstance(value, dict):
        return Counter({norm_value(k): int(v) for k, v in value.items() if int(v)})
    if isinstance(value, (list, tuple, set, frozenset)):
        return Counter(norm_value(v) for v in value)
    return Counter([norm_value(value)])


def match_verdict(actual: Any, predicted: Any) -> str:
    """다중집합 일치 판정. `docs/DECISIONS.md` D-015, `docs/LOGIC.md` L21.

    - 정확: 같다 (∅ = ∅ 도 정확)
    - 부분: 실제 ⊊ 예측 (일부만 실행)
    - 초과: 실제 ⊋ 예측 (더 실행). 예측이 ∅인데 실행이 있으면 초과다.
    - 혼합: 겹치지만 어느 쪽도 포함하지 않는다 (부분 + 초과)
    - 불일치: 겹치는 원소가 없고 둘 다 비어 있지 않다
    - 미실행: 실제 ∅, 예측 ≠ ∅
    """
    a = as_multiset(actual)
    p = as_multiset(predicted)
    if a == p:
        return "정확"
    if not a:
        return "미실행"
    if not p:
        return "초과"
    inter = a & p
    if not inter:
        return "불일치"
    if a <= p:
        return "부분"
    if p <= a:
        return "초과"
    return "혼합"
