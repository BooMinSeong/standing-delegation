"""정규화와 다중집합 일치 판정의 단위 검사.

`docs/DECISIONS.md` D-015(다중집합, 정확/부분/초과), `Plan.md` §6 D1(정규화 후 비교).
"""

from __future__ import annotations

from instruments.normalize import (
    as_multiset,
    calls_identical,
    looks_like_ident,
    match_verdict,
    norm_number,
    norm_params,
    norm_text,
    norm_value,
)


def test_norm_text_collapses_whitespace_and_case():
    assert norm_text("  Please   Ship\tFast ") == "please ship fast"


def test_looks_like_ident_requires_digit_and_length():
    assert looks_like_ident("sup_002")
    assert looks_like_ident("PROD-002")
    assert not looks_like_ident("supplier")      # 숫자 없음
    assert not looks_like_ident("a1")            # 3자 미만
    assert not looks_like_ident("sup 002")       # 단일 토큰 아님


def test_identifier_spelling_is_normalized():
    assert norm_value("sup_002") == norm_value("SUP-002") == norm_value("Sup 002".replace(" ", "-"))
    assert norm_value("prod_001") != norm_value("prod_002")


def test_number_forms_are_normalized():
    assert norm_number("$1,200.00") == "1200"
    assert norm_number(" 0.750 ") == "0.75"
    assert norm_number("09:00") is None
    assert norm_value(100) == norm_value("100") == norm_value("100.0")


def test_param_order_is_ignored_and_id_lists_are_order_free():
    a = {"supplier_id": "sup_002", "product_ids": ["prod_001", "prod_002"]}
    b = {"product_ids": ["PROD-002", "prod_001"], "supplier_id": "SUP_002"}
    assert norm_params(a) == norm_params(b)


def test_body_lists_keep_order():
    a = {"operations": ["rename a", "rename b"]}
    b = {"operations": ["rename b", "rename a"]}
    assert norm_params(a) != norm_params(b)


def test_calls_identical_multiset():
    x = [{"tool": "env.commit", "params": {"a": 1, "b": "sup_002"}}]
    y = [{"tool": "env.commit", "params": {"b": "SUP-002", "a": "1"}}]
    assert calls_identical(x, y)
    assert not calls_identical(x, x + y)  # 호출 횟수가 다르면 다르다


def test_empty_target_is_emptyset_not_unknown():
    assert as_multiset([]) == as_multiset(None)
    assert match_verdict([], []) == "정확"


def test_match_verdict_labels():
    assert match_verdict(["sup_001"], ["sup_001"]) == "정확"
    assert match_verdict(["sup_001"], ["sup_001", "sup_002"]) == "부분"
    assert match_verdict(["sup_001", "sup_002"], ["sup_001"]) == "초과"
    assert match_verdict(["sup_001", "sup_009"], ["sup_001", "sup_002"]) == "혼합"
    assert match_verdict(["sup_009"], ["sup_001"]) == "불일치"
    assert match_verdict([], ["sup_001"]) == "미실행"
    assert match_verdict(["sup_001"], []) == "초과"       # R이 ∅인데 실행 = 초과
    assert match_verdict(["sup_001", "sup_001"], ["sup_001"]) == "초과"  # 중복도 센다
