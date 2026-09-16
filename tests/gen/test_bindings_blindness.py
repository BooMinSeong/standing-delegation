"""V 속성 결합 추출기가 R을 모른다는 것과, D-027 (1)의 규칙대로 뽑는다는 것을 막는다.

근거: `docs/DECISIONS.md` D-027 (1) ("결합을 저자가 고르면 R을 아는 사람이 구분 행 수와 분리
설계 통과를 정하게 되므로, 결합은 환경 스키마에서 프로그램이 뽑는다")와 `Plan.md` §4.3의
눈가림 규칙. `tests/gen/test_forkset_blindness.py`와 같은 장치를 쓴다.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BINDINGS = REPO / "src" / "gen" / "bindings.py"

# R이 조건을 거는 필드와 그 근처 필드 이름. 추출기 소스에 하나도 없어야 한다
# (필드는 전부 schema.py에서 열거하게 짜여 있다). 컬렉션 이름('supplier_listings')은
# D-027 (1)이 허용한 **입력**이므로 이 목록에 넣지 않는다.
DECISION_TOKENS = [
    "available_quantity",
    "lead_time_days",
    "price",
    "ordering_permitted",
    "quantity_on_hand",
    "SUP-",
    "PROD-",
    "INV-",
]


def _load():
    spec = importlib.util.spec_from_file_location("d01_bindings", BINDINGS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_names_no_decision_field() -> None:
    hits = [t for t in DECISION_TOKENS if t in BINDINGS.read_text()]
    assert hits == [], f"결합 추출기 소스가 결정 축 이름을 적고 있다: {hits}"


def test_source_does_not_import_r_side() -> None:
    tree = ast.parse(BINDINGS.read_text())
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
        f"spec = importlib.util.spec_from_file_location('bindings', r'{BINDINGS}');"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
        "assert not {'rule', 'd01_rule', 'checks', 'measure_states'} & set(sys.modules), sys.modules.keys();"
        "print('ok')"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_guard_blocks_r_side_reads(tmp_path) -> None:
    """install_guard() 뒤에는 rule.py·q_plus.txt·상태·meta.yaml을 열 수 없다."""
    targets = [
        "data/delegations/D01/rule.py",
        "data/delegations/D01/q_plus.txt",
        "data/delegations/D01/states/measure/s01.json",
        "data/delegations/D01/states/fork/f00.json",
        "data/delegations/D01/meta.yaml",
        "data/delegations/D01/policy_preview.md",
    ]
    script = tmp_path / "probe.py"
    script.write_text(
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('bindings', r'{BINDINGS}')\n"
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


def test_derive_runs_under_guard() -> None:
    """눈가림 장치를 켠 채로도 결합 표가 나온다 = R 쪽 입력이 필요 없다."""
    code = (
        "import importlib.util, json, sys\n"
        f"spec = importlib.util.spec_from_file_location('bindings', r'{BINDINGS}')\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "m.install_guard()\n"
        "conf = m.DELEGATIONS['D01']\n"
        "b = m.derive(conf['schema'], conf['collection'])\n"
        "print(json.dumps({'v_d_size': b['v_d_size'], 'max': b['rules']['최대']['key_field'],\n"
        "                  'numeric': b['numeric_fields'], 'temporal': b['temporal_fields']},\n"
        "                 ensure_ascii=False))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    import json

    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["max"] == got["numeric"][0], got
    assert got["v_d_size"] == 5, got


def test_meta_matches_program_output() -> None:
    """`meta.yaml`의 v_binding이 프로그램 산출과 같다 (저자가 손으로 고치지 않았다)."""
    out = subprocess.run(
        [sys.executable, str(BINDINGS), "--check"], cwd=REPO, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stdout + out.stderr


# --------------------------------------------------------------------------
# D-027 (1)의 규칙 자체 (합성 스키마로 확인)
# --------------------------------------------------------------------------

SYNTH_NUMERIC = '''
from dataclasses import dataclass


@dataclass
class WidgetOffer:
    offer_id: str
    label: str
    weight_grams: int
    unit_cost: float
'''

SYNTH_TEMPORAL = '''
from dataclasses import dataclass


@dataclass
class WidgetOffer:
    offer_id: str
    posted_at: str
    effective_date: str
    unit_cost: float
'''

SYNTH_NO_NUMERIC = '''
from dataclasses import dataclass


@dataclass
class WidgetOffer:
    offer_id: str
    label: str
    note: str
'''


def _derive(tmp_path, source, name="schema.py"):
    path = tmp_path / name
    path.write_text(source)
    return _load().derive(path, "widget_offers")


def test_max_uses_first_numeric_field_in_declaration_order(tmp_path) -> None:
    b = _derive(tmp_path, SYNTH_NUMERIC)
    assert b["numeric_fields"] == ["weight_grams", "unit_cost"]
    assert b["rules"]["최대"]["key_field"] == "weight_grams"
    assert b["identifier_field"] == "offer_id"


def test_recent_uses_first_temporal_field_else_insertion_order(tmp_path) -> None:
    b = _derive(tmp_path, SYNTH_TEMPORAL)
    assert b["temporal_fields"] == ["posted_at", "effective_date"]
    assert b["rules"]["최근"]["key_field"] == "posted_at"

    sub = tmp_path / "sub"
    sub.mkdir()
    b2 = _derive(sub, SYNTH_NUMERIC)
    assert b2["temporal_fields"] == []
    assert b2["rules"]["최근"]["key_field"] is None  # 삽입 순서 마지막


def test_undefined_binding_drops_rule_from_v_d(tmp_path) -> None:
    b = _derive(tmp_path, SYNTH_NO_NUMERIC)
    assert b["rules"]["최대"]["defined"] is False
    assert "최대" not in b["v_d"]
    assert b["v_d_size"] == 4
    assert "최대" in b["excluded_from_v_d"]


def test_selectors_follow_the_binding(tmp_path) -> None:
    module = _load()
    path = tmp_path / "schema.py"
    path.write_text(SYNTH_NUMERIC)
    b = module.derive(path, "widget_offers")
    pick = module.selectors(b)
    cands = [
        {"offer_id": "B", "weight_grams": 5, "unit_cost": 9.0},
        {"offer_id": "A", "weight_grams": 5, "unit_cost": 1.0},
        {"offer_id": "C", "weight_grams": 3, "unit_cost": 7.0},
    ]
    assert [r["offer_id"] for r in pick["첫 번째"](cands)] == ["B"]
    assert [r["offer_id"] for r in pick["최근"](cands)] == ["C"]
    # 동률(weight_grams 5)은 식별자 오름차순 → A
    assert [r["offer_id"] for r in pick["최대"](cands)] == ["A"]
    assert [r["offer_id"] for r in pick["전부"](cands)] == ["A", "B", "C"]
    assert pick["없음"](cands) == []
    for name in ("첫 번째", "최대", "최근", "전부", "없음"):
        assert pick[name]([]) == []
