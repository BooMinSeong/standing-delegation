"""종이 검사 2·3의 환경 프로필 (docs/GEN-ALGO.md §15). q를 보지 않는다.

- 컬렉션 → dataclass: environment.py `_load_state`의 AST에서 `Class(...) for x in initial_state.get("coll")`를 읽는다
- 타입·널: dataclass 선언
- 키: 컬렉션의 `*_id` 필드 중 코퍼스에서 값이 유일한 것. 여럿이면 클래스·컬렉션 이름과 어간이 맞는 것, 그다음 선언 순서
- FK: `*_id` 필드가 다른 컬렉션의 키와 이름이 같으면 참조
- 정체성: 검색(lookup) 툴에서 문자열 매개변수가 레코드 필드와 대조되는 곳을 AST로 읽는다.
  주판정 = 부분 문자열 대조(`q in x.f`), 변형판 = 등호 대조(`x.f == p`)까지
- 툴 반환 필드: 코퍼스 상태마다 lookup·verify 툴을 실제로 불러 반환에 나타나는 키를 모은다
"""
from __future__ import annotations

import ast
import contextlib
import dataclasses
import io
import json
import pathlib
import sys
import typing
from functools import lru_cache

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import aa  # noqa: E402


@lru_cache(None)
def corpus(env: str) -> list[dict]:
    """같은 환경을 쓰는 모든 문항(act·abstain)의 초기 상태."""
    out = []
    for p in sorted((aa.AD / "tasks").glob(f"*/*/*/initial_states/{env}.json")):
        out.append(json.loads(p.read_text()))
    return out


@lru_cache(None)
def _tree(env: str):
    return ast.parse(aa.env_source(env))


def _func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


@lru_cache(None)
def collection_classes(env: str) -> dict[str, str]:
    """컬렉션 이름 → dataclass 이름."""
    load = _func(_tree(env), "_load_state")
    out = {}
    for n in ast.walk(load):
        if isinstance(n, (ast.ListComp, ast.DictComp)):
            elt = n.elt if isinstance(n, ast.ListComp) else n.value
            cls = None
            for m in ast.walk(elt):
                if isinstance(m, ast.Call) and isinstance(m.func, ast.Name) and m.func.id[:1].isupper():
                    cls = m.func.id
                    break
            coll = None
            for g in n.generators:
                for m in ast.walk(g.iter):
                    if isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute) and m.func.attr == "get" \
                            and m.args and isinstance(m.args[0], ast.Constant):
                        coll = m.args[0].value
            if cls and coll:
                out[coll] = cls
    return out


@lru_cache(None)
def class_fields(env: str) -> dict[str, dict[str, dict]]:
    """dataclass 이름 → {필드: {type, nullable}}."""
    mod = aa.schema_module(env)
    out = {}
    for name, obj in vars(mod).items():
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            fs = {}
            for f in dataclasses.fields(obj):
                t = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", str(f.type))
                nullable = "None" in t or "Optional" in t or f.default is None
                fs[f.name] = {"type": t, "nullable": nullable}
            out[name] = fs
    return out


def _stem(s: str) -> str:
    return s.lower().rstrip("s").replace("_", "")


@lru_cache(None)
def keys(env: str) -> dict[str, str]:
    cc, cf = collection_classes(env), class_fields(env)
    out = {}
    for coll, cls in cc.items():
        ids = [f for f in cf.get(cls, {}) if f.endswith("_id") or f.endswith("_code")]
        uniq = []
        for f in ids:
            ok, seen_any = True, False
            for st in corpus(env):  # 상태 하나 안에서 유일해야 키다
                vals = [str(r.get(f)) for r in st.get(coll, []) if isinstance(r, dict) and f in r]
                seen_any |= bool(vals)
                ok &= len(vals) == len(set(vals))
            if seen_any and ok:
                uniq.append(f)
        if not uniq:
            continue
        stems = (_stem(cls), _stem(coll))
        best = [f for f in uniq if any(_stem(f[:-3]) in s or s in _stem(f[:-3]) for s in stems)]
        out[coll] = (best or uniq)[0]
    return out


@lru_cache(None)
def fks(env: str) -> list[tuple[str, str, str]]:
    """(참조 컬렉션, 필드, 피참조 컬렉션)."""
    cc, cf, ks = collection_classes(env), class_fields(env), keys(env)
    out = []
    for coll, cls in cc.items():
        for f in cf.get(cls, {}):
            if not f.endswith("_id"):
                continue
            for other, k in ks.items():
                if other != coll and k == f:
                    out.append((coll, f, other))
    return out


def _tools(env: str):
    reg = _func(_tree(env), "_register_tools")
    for n in reg.body:
        if isinstance(n, ast.FunctionDef):
            yield n


@lru_cache(None)
def identity_fields(env: str) -> dict[str, list[tuple[str, str, str, str]]]:
    """{'substring': [(tool, param, collection, field)], 'equality': [...]} — lookup 툴만."""
    kinds = aa.env_class(env).tool_kinds
    out = {"substring": [], "equality": []}
    for fn in _tools(env):
        if kinds.get(fn.name) != "lookup":
            continue
        params = {a.arg for a in fn.args.args if a.arg != "self"
                  and (a.annotation is None or (isinstance(a.annotation, ast.Name) and a.annotation.id == "str")
                       or (isinstance(a.annotation, ast.Constant) and a.annotation.value == "str"))}
        derived = set(params)
        for _ in range(3):
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign) and any(isinstance(m, ast.Name) and m.id in derived for m in ast.walk(n.value)):
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            derived.add(t.id)
        loopvar = {}
        for n in ast.walk(fn):
            if isinstance(n, (ast.For, ast.comprehension)):
                it, tgt = n.iter, n.target
                if isinstance(tgt, ast.Name):
                    for m in ast.walk(it):
                        if isinstance(m, ast.Subscript) and isinstance(m.slice, ast.Constant) and isinstance(m.slice.value, str):
                            loopvar[tgt.id] = m.slice.value
        for n in ast.walk(fn):
            if not isinstance(n, ast.Compare):
                continue
            sides = [n.left] + list(n.comparators)
            q_side = [s for s in sides if any(isinstance(m, ast.Name) and m.id in derived for m in ast.walk(s))]
            f_side = []
            for s in sides:
                for m in ast.walk(s):
                    if isinstance(m, ast.Attribute) and isinstance(m.value, ast.Name) and m.value.id in loopvar:
                        f_side.append((loopvar[m.value.id], m.attr))
            if not q_side or not f_side:
                continue
            op = "substring" if any(isinstance(o, (ast.In, ast.NotIn)) for o in n.ops) else \
                 "equality" if any(isinstance(o, (ast.Eq, ast.NotEq)) for o in n.ops) else None
            if not op:
                continue
            pname = next((m.id for s in q_side for m in ast.walk(s) if isinstance(m, ast.Name) and m.id in derived), "?")
            for coll, f in f_side:
                t = (fn.name, pname, coll, f)
                if t not in out[op]:
                    out[op].append(t)
    return out


def _walk_keys(x, acc: set):
    if isinstance(x, dict):
        for k, v in x.items():
            acc.add(k)
            _walk_keys(v, acc)
    elif isinstance(x, list):
        for v in x:
            _walk_keys(v, acc)


def call_tools(env: str, state: dict, record: dict | None = None) -> dict[str, object]:
    """lookup·verify 툴을 전부 불러 결과를 모은다. 매개변수는 record에 같은 이름의 필드가 있으면 그 값, 없으면 빈 문자열."""
    cls = aa.env_class(env)
    out = {}
    for sch in cls.get_tool_schemas():
        name = sch["name"]
        if cls.tool_kinds.get(name) not in ("lookup", "verify"):
            continue
        props = (sch.get("input_schema") or {}).get("properties", {})
        args = {}
        for p in props:
            v = (record or {}).get(p, "")
            args[p] = v if isinstance(v, str) else json.dumps(v) if isinstance(v, (list, dict)) else str(v)
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                e = cls(json.loads(json.dumps(state)))
                res = e.call_tool(name, **args)
                if res is None:  # 반환 타입이 맨 `list`면 structured_content가 없다. 텍스트 content를 읽는다
                    from abstention_factory.runtime.base import _run_sync
                    raw = _run_sync(e.mcp.call_tool(name, args))
                    texts = [getattr(c, "text", "") for c in (getattr(raw, "content", None) or [])]
                    parsed = []
                    for t in texts:
                        try:
                            parsed.append(json.loads(t))
                        except Exception:  # noqa: BLE001
                            parsed.append(t)
                    res = parsed[0] if len(parsed) == 1 else parsed
                    out.setdefault("__none_structured__", []).append(name)
                out[name] = res
        except Exception as ex:  # noqa: BLE001
            out[name] = {"__error__": f"{type(ex).__name__}: {ex}"[:200]}
    return out


@lru_cache(None)
def returned_fields(env: str) -> frozenset[str]:
    """코퍼스 상태에서 lookup·verify 툴 반환에 한 번이라도 키로 나타난 필드 이름."""
    acc: set = set()
    for st in corpus(env):
        colls = [c for c in collection_classes(env) if st.get(c)]
        recs = [None] + [st[c][0] for c in colls if isinstance(st[c], list) and st[c] and isinstance(st[c][0], dict)]
        for rec in recs:
            for res in call_tools(env, st, rec).values():
                _walk_keys(res, acc)
    return frozenset(acc)


if __name__ == "__main__":
    for env in ("store_procurement_and_inventory", "flight_and_travel_management"):
        print("==", env, "corpus", len(corpus(env)))
        print("classes", collection_classes(env))
        print("keys", keys(env))
        print("fks", fks(env))
        idf = identity_fields(env)
        print("identity substring", [(t, c, f) for t, _, c, f in idf["substring"]])
        print("identity equality", [(t, c, f) for t, _, c, f in idf["equality"]])
        print("returned", sorted(returned_fields(env))[:80])
