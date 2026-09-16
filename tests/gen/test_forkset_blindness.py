"""fork set 생성기가 R을 모른다는 것을 소스와 동작 양쪽에서 막는다.

`Plan.md` §4.3 마지막 문장("측정용 상태는 R을 알고 만들고, 방법의 fork set은 R을 몰라야
한다. ... 이 분리가 없으면 M1은 동어반복이다")과 `.claude/agents/delegation-author.md`의
눈가림 규칙이 근거다.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FORKSET = REPO / "src" / "gen" / "forkset.py"
FORK_DIR = REPO / "data" / "delegations" / "D01" / "states" / "fork"
# 섭동표 v1 §7.2의 8행 + 무편집 기준 행 P00 (D-022 ③ 채택, Plan.md v2.1 §4.3)
SELECTED_ROWS = ["P00", "P01", "P04", "P07", "P09", "P11", "P13", "P16", "P18"]

# R이 조건을 거는 필드와 그 근처 필드 이름. 생성기 소스에 하나도 없어야 한다
# (필드는 전부 상태 데이터에서 열거하게 짜여 있다).
DECISION_TOKENS = [
    "available_quantity",
    "lead_time_days",
    "price",
    "ordering_permitted",
    "quantity_on_hand",
    "supplier",
    "SUP-",
    "PROD-",
    "INV-",
]


def test_source_names_no_decision_field() -> None:
    source = FORKSET.read_text()
    hits = [t for t in DECISION_TOKENS if t in source]
    assert hits == [], f"생성기 소스가 결정 축 이름을 적고 있다: {hits}"


def test_source_does_not_import_r_side() -> None:
    tree = ast.parse(FORKSET.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"rule", "d01_rule", "checks", "measure_states"}, imported


def test_import_does_not_pull_r_in() -> None:
    code = (
        "import importlib.util, sys;"
        f"spec = importlib.util.spec_from_file_location('forkset', r'{FORKSET}');"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
        "assert not {'rule', 'd01_rule', 'checks', 'measure_states'} & set(sys.modules), sys.modules.keys();"
        "print('ok')"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_guard_blocks_r_side_reads(tmp_path) -> None:
    """install_guard() 뒤에는 rule.py·q_plus.txt·측정용 상태·meta.yaml을 열 수 없다."""
    targets = [
        "data/delegations/D01/rule.py",
        "data/delegations/D01/q_plus.txt",
        "data/delegations/D01/states/measure/s01.json",
        "data/delegations/D01/states/fork/index.yaml",
        "data/delegations/D01/meta.yaml",
        "data/delegations/D01/policy_preview.md",
    ]
    script = tmp_path / "probe.py"
    script.write_text(
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('forkset', r'{FORKSET}')\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "m.install_guard()\n"
        f"targets = {targets!r}\n"
        f"repo = r'{REPO}'\n"
        "blocked = []\n"
        "for t in targets:\n"
        "    try:\n"
        "        open(repo + '/' + t).read()\n"
        "    except PermissionError:\n"
        "        blocked.append(t)\n"
        "print(len(blocked), len(targets))\n"
    )
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    blocked, total = out.stdout.split()
    assert blocked == total, f"막히지 않은 경로가 있다: {out.stdout}"


def test_fork_states_are_regenerable(tmp_path) -> None:
    """손으로 고치지 않았는지: 다시 생성해 파일 단위로 같은지 본다."""
    out = subprocess.run(
        [sys.executable, str(FORKSET), "--out", str(tmp_path)],
        capture_output=True, text=True, cwd=REPO,
    )
    assert out.returncode == 0, out.stderr
    # 생성기가 쓰는 파일만 비교한다(index.yaml은 R을 아는 src/gen/checks.py가 쓴다).
    owned = sorted(p.name for p in FORK_DIR.iterdir()
                   if p.name.startswith("f") and p.suffix == ".json" or p.name == "forkset_log.yaml")
    regenerated = sorted(p.name for p in tmp_path.iterdir())
    assert owned == regenerated, (owned, regenerated)
    for name in owned:
        assert (FORK_DIR / name).read_text() == (tmp_path / name).read_text(), f"{name}이 재생성과 다르다"


def test_fork_rows_are_the_selected_nine() -> None:
    rows = [
        json.loads(line.split(":", 1)[1].strip())
        for line in (FORK_DIR / "forkset_log.yaml").read_text().splitlines()
        if line.strip().startswith("perturbation_row:")
    ]
    assert rows == SELECTED_ROWS, rows
    assert len(rows) == 9


def test_fork_states_load_in_environment() -> None:
    """생성된 상태가 AgentAbstain 로더를 통과한다."""
    sys.path.insert(0, str(REPO / "data"))
    from envs.store_procurement_and_inventory.environment import (  # noqa: E402
        StoreProcurementAndInventoryEnvironment as E,
    )

    for path in sorted(FORK_DIR.glob("f*.json")):
        env = E(json.loads(path.read_text()))
        assert isinstance(env.call_tool("search_suppliers", query=""), list)
