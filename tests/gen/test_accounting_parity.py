"""구분 행 회계가 저작 쪽(`src/gen/checks.py`)과 판독기 쪽에서 같은지 본다.

`docs/DECISIONS.md` D-024 L35: "적용 불가 행도 예측이 갈리면 구분 행에 넣는다. `excluded`에
inapplicable 없음. checks.py와 policy_reader가 같은 n을 내는 검사 추가."

판독기에 넣는 `commit_target`은 V '첫 번째' 규칙의 예측이다(`policy_preview.md` §2 숨김판이
쓰는 것과 같은 가상 정책표). 구분 행 수는 `commit_target`이 무엇이든 같다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
FORK_INDEX = REPO / "data" / "delegations" / "D01" / "states" / "fork" / "index.yaml"


def _policy_reader():
    """AgentAbstain 리포의 `src` 패키지가 우리 `src`를 가린다. 그 경로를 빼고 임포트한다."""
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if "agentabstain-code" not in p]
    sys.path.insert(0, str(REPO))
    try:
        from src.instruments import policy_reader

        return policy_reader
    finally:
        sys.path[:] = saved


def test_checks_and_policy_reader_agree_on_n() -> None:
    reader = _policy_reader()
    index = yaml.safe_load(FORK_INDEX.read_text())
    rows = [
        {
            "state_id": s["state_id"],
            "perturbation_row": s["perturbation_row"],
            "commit_target": s["predictions"]["first"],
            "predictions": s["predictions"],
            "exposure_seen": s["exposure_seen"],
            "candidate_count": s["candidate_count"],
        }
        for s in index["states"]
    ]
    result = reader.read(rows, rules=reader.RULE_IDS_V0)
    assert result["n_discriminating"] == len(index["discriminating_rows"]), (
        result["n_discriminating"], index["discriminating_rows"]
    )
    assert result["discriminating_rows"] == index["discriminating_rows"]
    # inapplicable은 제외 사유가 아니다 (D-024 L35)
    assert "inapplicable" not in result["excluded"]
    inapplicable = set(index.get("inapplicable_rows") or [])
    assert inapplicable & set(index["discriminating_rows"]) == inapplicable, (
        "적용 불가 행이 예측이 갈리는데도 구분 행에서 빠졌다"
    )


def test_baseline_rows_are_hash_based() -> None:
    index = yaml.safe_load(FORK_INDEX.read_text())
    log = yaml.safe_load(
        (FORK_INDEX.parent / "forkset_log.yaml").read_text()
    )
    base_hash = log["base_state_canonical_sha256"]
    by_id = {s["state_id"]: s for s in index["states"]}
    for row in log["rows"]:
        expected = row["state_canonical_sha256"] == base_hash
        assert by_id[row["state_id"]]["is_baseline"] is expected, row["state_id"]
    assert index["baseline_reference"] == "f00"
    assert "f00" in index["baseline_rows"]
