"""`src/gen/`의 스크립트가 경로를 스스로 잡는다 (`tests/conftest.py`와 같은 방식).

왜: `.venv/bin/python src/gen/checks.py`가 환경변수 없이 돌지 않으면 저자가 검사를
직접 재현할 수 없고, 그러면 커밋을 신뢰할 근거가 없다(조율자 지적 2026-09-16).

규칙
- 환경변수가 이미 있으면 그대로 둔다(`setdefault`).
- 저장소 경로는 이 파일 위치에서 상대로 구한다. 상수로 박는 것은 v1 저장소 경로뿐이고
  값은 `docs/FEASIBILITY.md` §5와 같다.
- 하위 프로세스(`pytest`, fork set 재생성)도 같은 경로를 보도록 `PYTHONPATH`에도 넣는다.
- 저장소 루트는 sys.path **뒤쪽**에 둔다: AgentAbstain 코드에도 `src` 패키지가 있어
  앞에 두면 서로 가린다(`tests/gen/test_accounting_parity.py`의 주석과 같은 사정).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# v1 저장소의 AgentAbstain 사본 (docs/FEASIBILITY.md §5). 유일한 하드코딩 경로다.
V1_AGENTABSTAIN = Path("/home3/b.ms/projects/standing-delegation/data")
DEFAULT_CODE = V1_AGENTABSTAIN / "agentabstain-code"
DEFAULT_DATA = V1_AGENTABSTAIN / "agentabstain-data"

REPO = Path(__file__).resolve().parents[2]


def bootstrap() -> dict[str, str]:
    """AgentAbstain 코드·데이터 경로와 저장소 경로를 잡고, 쓴 값을 돌려준다."""
    code = Path(os.environ.get("AGENTABSTAIN_CODE", DEFAULT_CODE))
    os.environ.setdefault("AGENTABSTAIN_DATA", str(DEFAULT_DATA))

    ordered = [str(code), str(REPO / "data"), str(REPO)]
    for path in reversed(ordered):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)

    current = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    for path in reversed(ordered):
        if os.path.isdir(path) and path not in current:
            current.insert(0, path)
    os.environ["PYTHONPATH"] = os.pathsep.join(current)

    return {
        "AGENTABSTAIN_CODE": str(code),
        "AGENTABSTAIN_DATA": os.environ["AGENTABSTAIN_DATA"],
        "PYTHONPATH": os.environ["PYTHONPATH"],
    }
