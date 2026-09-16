"""pytest 공통 설정: AgentAbstain 코드·데이터 경로를 기본값으로 잡는다 (docs/FEASIBILITY.md §5 방식).

환경변수가 이미 있으면 그대로 두고, 없으면 v1 저장소의 사본을 가리킨다.
"""
from __future__ import annotations

import os
import sys

_CODE = "/home3/b.ms/projects/standing-delegation/data/agentabstain-code"
_DATA = "/home3/b.ms/projects/standing-delegation/data/agentabstain-data"

if _CODE not in sys.path and os.path.isdir(_CODE):
    sys.path.insert(0, _CODE)
os.environ.setdefault("AGENTABSTAIN_DATA", _DATA)
