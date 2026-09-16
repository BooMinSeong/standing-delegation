"""V(대안 규칙 집합)의 속성 결합을 환경 스키마에서 기계로 뽑는다. **R을 모르는 코드다.**

근거: `docs/DECISIONS.md` D-027 (1) (저자 확정 2026-09-16, D-021 #1·L43).
  "결합을 저자가 고르면 R을 아는 사람이 구분 행 수와 분리 설계 통과를 정하게 되므로,
   결합은 환경 스키마에서 프로그램이 뽑는다."

D-027 (1)의 규칙을 그대로 옮긴 것 (문장 → 코드):
  - 후보     = 그 위임의 적격 후보 집합 K(s). 호출자가 빈손 조회 순서대로 건네준다.
  - 첫 번째  = 빈손 조회가 돌려주는 목록 순서의 첫 후보  → 후보 목록의 0번.
  - 최대     = 후보 레코드의 숫자 필드를 환경 `schema.py`의 **선언 순서**로 나열해
               첫 필드가 가장 큰 후보.
  - 최근     = 시각·날짜 타입 필드가 있으면 선언 순서 첫 필드가 가장 늦은 후보,
               없으면 삽입 순서의 마지막 후보.
  - 전부     = 적격 후보 전체(다중집합).   없음 = 항상 ∅.
  - 동률     = 모든 규칙에서 식별자 오름차순.
  - 결합이 정의되지 않는 규칙(해당 필드 없음)은 그 위임의 V_D에서 뺀다.

허용된 입력 두 가지뿐이다.
  (1) 환경 `schema.py`의 경로. **임포트하지 않고 `ast`로 읽는다**(실행 부작용 없음).
  (2) 후보 컬렉션 이름(예: 위임의 K(s)가 사는 컬렉션).
금지된 입력: R, `rule.py`, `q_plus.txt`, 측정용·fork 상태, `meta.yaml`, `checks.py`.
`install_guard()`가 실행 중 읽기를 막고 `tests/gen/test_bindings_blindness.py`가 소스와
동작 양쪽을 막는다. 이 파일에는 결정 축이 될 수 있는 필드 이름을 한 번도 적지 않는다
(필드는 전부 스키마에서 열거한다. 테스트가 소스를 검사한다).

사용:
  .venv/bin/python src/gen/bindings.py                 # 결합 표를 YAML로 찍는다
  .venv/bin/python src/gen/bindings.py --write-meta    # meta.yaml의 표시 구간을 갈아끼운다
  .venv/bin/python src/gen/bindings.py --check         # meta.yaml이 프로그램 산출과 같은가
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Callable, Sequence

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from _paths import bootstrap  # noqa: E402  (경로를 스스로 잡는다 — tests/conftest.py와 같은 방식)

bootstrap()

REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- 눈가림 장치
FORBIDDEN_READ = (
    "rule.py",
    "q_plus",
    "states/measure",
    "states/fork",
    "states/heldout",
    "meta.yaml",
    "policy_preview",
    "checks.py",
    "checks.md",
)
FORBIDDEN_IMPORT = ("rule", "d01_rule", "checks", "src.gen.checks", "measure_states", "src.gen.measure_states")


def install_guard() -> None:
    """R 쪽 파일을 읽거나 임포트하면 그 자리에서 죽는다 (forkset.py와 같은 장치)."""

    def _hook(event: str, args):
        if event == "open":
            path = str(args[0]).replace("\\", "/")
            if any(tok in path for tok in FORBIDDEN_READ):
                raise PermissionError(f"결합 추출기는 이 파일을 읽을 수 없다: {path}")
        elif event == "import":
            if args[0] in FORBIDDEN_IMPORT:
                raise PermissionError(f"결합 추출기는 이 모듈을 임포트할 수 없다: {args[0]}")

    sys.addaudithook(_hook)


# ---------------------------------------------------------------- 규칙 이름·ID
RULE_NAMES: tuple[str, ...] = ("첫 번째", "최대", "최근", "전부", "없음")
RULE_IDS: dict[str, str] = {
    "첫 번째": "first",
    "최대": "max",
    "최근": "recent",
    "전부": "all",
    "없음": "none",
}

# ---------------------------------------------------------------- 타입 분류 (D-027 (1))
NUMERIC_ANNOTATIONS = {"int", "float", "decimal", "Decimal"}
TEMPORAL_ANNOTATIONS = {"date", "time", "datetime", "datetime.date", "datetime.datetime", "datetime.time"}
STRING_ANNOTATIONS = {"str"}
# 문자열로 적힌 시각·날짜 필드를 이름으로 알아본다. 숫자 타입은 여기 걸려도 시각이 아니다
# (숫자 필드는 '최대'의 재료이고, 타입 판정이 이름 판정보다 앞선다).
TEMPORAL_NAME_RE = re.compile(r"(?:^|_)(?:date|time|datetime|timestamp)(?:_|$)|_at$")
IDENTIFIER_SUFFIX = "_id"


def _annotation_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    text = ast.unparse(node)
    # Optional[X] / X | None 은 X로 읽는다.
    text = text.replace("Optional[", "").rstrip("]")
    parts = [p.strip() for p in text.split("|") if p.strip() and p.strip() != "None"]
    return parts[0] if parts else text.strip()


def dataclass_fields(schema_path: Path) -> dict[str, list[tuple[str, str]]]:
    """`schema.py`를 `ast`로 읽어 클래스마다 (필드, 주석)을 **선언 순서**로 돌려준다."""
    tree = ast.parse(Path(schema_path).read_text())
    out: dict[str, list[tuple[str, str]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields = [
            (st.target.id, _annotation_name(st.annotation))
            for st in node.body
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)
        ]
        if fields:
            out[node.name] = fields
    return out


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _singular(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def record_class_for(collection: str, classes: dict[str, list]) -> str:
    """컬렉션 이름 → 레코드 클래스 이름. 기계적 대응(복수형 제거 + CamelCase)."""
    want = _singular(collection)
    for name in classes:
        if _camel_to_snake(name) == want:
            return name
    raise KeyError(f"컬렉션 '{collection}'에 대응하는 레코드 클래스를 schema.py에서 찾지 못했다")


def classify(fields: Sequence[tuple[str, str]]) -> dict[str, list[str]]:
    numeric, temporal, identifiers = [], [], []
    for name, annotation in fields:
        if annotation in NUMERIC_ANNOTATIONS:
            numeric.append(name)
        elif annotation in TEMPORAL_ANNOTATIONS or (
            annotation in STRING_ANNOTATIONS and TEMPORAL_NAME_RE.search(name)
        ):
            temporal.append(name)
        if name.endswith(IDENTIFIER_SUFFIX):
            identifiers.append(name)
    return {"numeric": numeric, "temporal": temporal, "identifier": identifiers}


# ---------------------------------------------------------------- 결합 표
def derive(schema_path: Path, collection: str) -> dict:
    """D-027 (1)의 결합 표. 입력은 스키마 경로와 컬렉션 이름뿐이다."""
    classes = dataclass_fields(schema_path)
    record_class = record_class_for(collection, classes)
    fields = classes[record_class]
    kinds = classify(fields)
    numeric, temporal, identifiers = kinds["numeric"], kinds["temporal"], kinds["identifier"]
    if not identifiers:
        raise KeyError(f"'{collection}' 레코드에 식별자(*{IDENTIFIER_SUFFIX}) 필드가 없어 동률을 풀 수 없다")
    identifier = identifiers[0]

    rules: dict[str, dict] = {}
    rules["첫 번째"] = {
        "defined": True,
        "key_field": None,
        "binding": f"빈손 조회 순서(= 컬렉션 '{collection}'의 삽입 순서)의 첫 적격 후보",
        "basis": "D-027 (1) '첫 번째'. 순서는 컬렉션 삽입 순서이고, 빈손 조회가 그 순서로 돌려주는 것은 checks.md (f)가 상태마다 확인한다",
    }
    if numeric:
        rules["최대"] = {
            "defined": True,
            "key_field": numeric[0],
            "binding": f"적격 후보 중 '{numeric[0]}'이(가) 최대인 후보. 동률은 '{identifier}' 오름차순",
            "basis": f"D-027 (1) '최대'. 숫자 필드를 schema.py 선언 순서로 나열하면 {numeric}이고 첫 필드가 '{numeric[0]}'이다",
        }
    else:
        rules["최대"] = {
            "defined": False,
            "key_field": None,
            "binding": None,
            "basis": f"'{record_class}'에 숫자 필드가 없다 → V_D에서 뺀다",
        }
    if temporal:
        rules["최근"] = {
            "defined": True,
            "key_field": temporal[0],
            "binding": f"적격 후보 중 '{temporal[0]}'이(가) 가장 늦은 후보. 동률은 '{identifier}' 오름차순",
            "basis": f"D-027 (1) '최근'. 시각·날짜 타입 필드를 선언 순서로 나열하면 {temporal}이고 첫 필드가 '{temporal[0]}'이다",
        }
    else:
        rules["최근"] = {
            "defined": True,
            "key_field": None,
            "binding": f"빈손 조회 순서(= 컬렉션 '{collection}'의 삽입 순서)의 마지막 적격 후보",
            "basis": f"D-027 (1) '최근'의 대체 규칙. '{record_class}'에 시각·날짜 타입 필드가 없어 삽입 순서 마지막으로 결합한다",
        }
    rules["전부"] = {
        "defined": True,
        "key_field": None,
        "binding": f"적격 후보 전체(다중집합). 표기는 '{identifier}' 오름차순",
        "basis": "D-027 (1) '전부'. commit 대상이 다중집합이므로(D-015·L21) 추가 결합이 필요 없다",
    }
    rules["없음"] = {
        "defined": True,
        "key_field": None,
        "binding": "언제나 ∅ (commit 없음)",
        "basis": "D-027 (1) '없음'. 결합이 필요 없다",
    }

    v_d = [name for name in RULE_NAMES if rules[name]["defined"]]
    return {
        "generator": "src/gen/bindings.py",
        "decision": "D-027 (1)",
        "schema": str(Path(schema_path).relative_to(REPO)) if str(schema_path).startswith(str(REPO)) else str(schema_path),
        "collection": collection,
        "record_class": record_class,
        "field_order": [f for f, _ in fields],
        "numeric_fields": numeric,
        "temporal_fields": temporal,
        "identifier_field": identifier,
        "tie_break": f"'{identifier}' 오름차순 (모든 규칙 공통)",
        "rules": {name: rules[name] for name in RULE_NAMES},
        "v_d": v_d,
        "v_d_size": len(v_d),
        "excluded_from_v_d": {n: rules[n]["basis"] for n in RULE_NAMES if not rules[n]["defined"]},
    }


# ---------------------------------------------------------------- 선택 함수
def selectors(binding: dict) -> dict[str, Callable[[list[dict]], list[dict]]]:
    """결합 표 → 규칙별 선택 함수. 입력은 빈손 조회 순서의 적격 후보 목록이다."""
    ident = binding["identifier_field"]
    rules = binding["rules"]

    def first(cands):
        return cands[:1]

    def last(cands):
        return cands[-1:]

    def maximum(cands):
        field = rules["최대"]["key_field"]
        if not cands:
            return []
        return [sorted(cands, key=lambda r: (-r[field], str(r[ident])))[0]]

    def recent(cands):
        field = rules["최근"]["key_field"]
        if not cands:
            return []
        if field is None:
            return cands[-1:]
        # 가장 늦은 = 문자열 비교로도 순서가 보존되는 ISO 표기를 가정한다(D-027 (1)).
        return [sorted(cands, key=lambda r: (_desc_key(r[field]), str(r[ident])))[0]]

    def every(cands):
        return sorted(cands, key=lambda r: str(r[ident]))

    def nothing(cands):
        return []

    out: dict[str, Callable[[list[dict]], list[dict]]] = {
        "첫 번째": first,
        "최근": recent,
        "전부": every,
        "없음": nothing,
    }
    if rules["최대"]["defined"]:
        out["최대"] = maximum
    return {name: out[name] for name in RULE_NAMES if name in out}


class _Desc:
    """내림차순 정렬용 래퍼 (문자열·수치 공용)."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value


def _desc_key(value):
    return _Desc(value)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------- YAML 출력
def _yaml(obj, indent: int = 0) -> str:
    import json

    pad = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            key = k if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(k)) else json.dumps(str(k), ensure_ascii=False)
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{key}:\n{_yaml(v, indent + 1)}")
            elif isinstance(v, (dict, list)):
                lines.append(f"{pad}{key}: " + ("{}" if isinstance(v, dict) else "[]"))
            else:
                lines.append(f"{pad}{key}: {json.dumps(v, ensure_ascii=False)}")
        return "\n".join(lines)
    if isinstance(obj, list):
        return "\n".join(f"{pad}- {json.dumps(v, ensure_ascii=False)}" for v in obj)
    return f"{pad}{json.dumps(obj, ensure_ascii=False)}"


BEGIN = "# >>> v_binding (프로그램 생성: src/gen/bindings.py. 손으로 고치지 않는다 — D-027 (1))"
END = "# <<< v_binding"


def meta_block(binding: dict) -> str:
    return "\n".join([BEGIN, "v_binding:", _yaml(binding, 1), END])


def splice(meta_text: str, block: str) -> str:
    start = meta_text.index(BEGIN)
    end = meta_text.index(END) + len(END)
    return meta_text[:start] + block + meta_text[end:]


# ---------------------------------------------------------------- CLI
# 위임별 입력(스키마 경로, 후보 컬렉션 이름). 결합 표는 전부 여기서 나온다.
DELEGATIONS = {
    "D01": {
        "schema": REPO / "data" / "envs" / "store_procurement_and_inventory" / "schema.py",
        "collection": "supplier_listings",
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V 속성 결합 추출기 (D-027 (1))")
    parser.add_argument("--delegation", default="D01")
    parser.add_argument("--write-meta", action="store_true", help="meta.yaml의 표시 구간을 갈아끼운다")
    parser.add_argument("--check", action="store_true", help="meta.yaml이 프로그램 산출과 같은지만 본다")
    args = parser.parse_args(argv)

    conf = DELEGATIONS[args.delegation]
    binding = derive(conf["schema"], conf["collection"])
    block = meta_block(binding)

    if not (args.write_meta or args.check):
        print(block)
        return 0

    # meta.yaml 읽기·쓰기는 결합 추출이 끝난 뒤에만 한다(결합은 meta.yaml을 입력으로 쓰지 않는다).
    meta_path = REPO / "data" / "delegations" / args.delegation / "meta.yaml"
    text = meta_path.read_text()
    new = splice(text, block)
    if args.check:
        same = new == text
        print("meta.yaml v_binding: " + ("프로그램 산출과 같다" if same else "**다르다**"))
        return 0 if same else 1
    meta_path.write_text(new)
    print(f"wrote {meta_path.relative_to(REPO)} (v_binding {binding['v_d_size']}규칙)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
