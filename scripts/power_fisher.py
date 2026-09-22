"""의존 검정의 검정력 (docs/GEN-ALGO.md §18, D-042).

결과를 이진(기준 최빈 행동 / 그 밖)으로 굵히고 Fisher 양측 정확 검정을 한다고 둔다.
기준 n_b 런의 최빈 확률 p0, 편집 n_e 런에서 그 확률이 d만큼 내려갈 때 p ≤ alpha일 확률을
이항 분포 전수 열거로 계산한다(몬테카를로 아님). alpha 기본값은 한 가족에 편집 17개일 때의
BH 첫 문턱 0.10/17.
사용: uv run --with scipy python scripts/power_fisher.py
"""
from __future__ import annotations

import functools
from math import comb

from scipy.stats import binom, fisher_exact

ALPHA = 0.10 / 17


@functools.lru_cache(None)
def _p(a: int, b: int, c: int, d: int) -> float:
    return fisher_exact([[a, b], [c, d]], alternative="two-sided")[1]


def power(n_b: int, n_e: int, p0: float, d: float, alpha: float = ALPHA) -> float:
    pe = max(p0 - d, 0.0)
    return sum(binom.pmf(xb, n_b, p0) * binom.pmf(xe, n_e, pe)
               for xb in range(n_b + 1) for xe in range(n_e + 1)
               if _p(xb, n_b - xb, xe, n_e - xe) <= alpha)


if __name__ == "__main__":
    rows = [("15 / 5", 15, 5), ("기준 뒤 반쪽 7 / 5", 7, 5), ("B_many 뒤 반쪽 4 / 5", 4, 5),
            ("B_one 32 / 10", 32, 10), ("B_many 17 / 10", 17, 10)]
    print(f"alpha = {ALPHA:.5f}, d = 0.5")
    print("| 기준 / 편집 | p0 0.95 | p0 0.68 | 완전 분리의 최소 p |")
    print("|---|---|---|---|")
    for name, nb, ne in rows:
        print(f"| {name} | {power(nb, ne, 0.95, 0.5):.2f} | {power(nb, ne, 0.68, 0.5):.2f} | {1 / comb(nb + ne, ne):.5f} |")
