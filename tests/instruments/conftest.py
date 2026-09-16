"""합성 검사 공통 설정. 러너 없이 돈다.

`.venv/bin/python -m pytest tests/instruments -q` 로 도는 것이 요구사항이므로
`src`를 여기서 임포트 경로에 얹는다(`docs/FEASIBILITY.md` §5의 PYTHONPATH 방식과 같은 뜻).
pyproject.toml은 고치지 않는다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
FIXTURE_DIR = ROOT / "tests" / "fixtures"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def policy_tables() -> dict:
    return load_fixture("policy_tables.json")


@pytest.fixture(scope="session")
def forksets() -> dict:
    return load_fixture("forksets.json")


@pytest.fixture(scope="session")
def rollout_provenance() -> dict:
    return load_fixture("rollout_provenance.json")


@pytest.fixture(scope="session")
def rollout_identity() -> tuple[dict, dict]:
    return load_fixture("rollout_identity_plus.json"), load_fixture("rollout_identity_minus.json")


@pytest.fixture(scope="session")
def rollout_attempts() -> dict:
    return load_fixture("rollout_attempts.json")


@pytest.fixture(scope="session")
def rollout_attempt_failed_only() -> dict:
    return load_fixture("rollout_attempt_failed_only.json")


@pytest.fixture(scope="session")
def rollout_exposure_seen() -> dict:
    return load_fixture("rollout_exposure_seen.json")
