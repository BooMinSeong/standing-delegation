"""종이 검사 공통: AgentAbstain 환경 적재, 씨앗 131, 상태 스냅샷, 생성기 LLM 호출.

환경은 원본(`agentabstain-data/environments/<env>`)을 그대로 띄운다. 원본 모듈은
`abstention_factory.environments.<env>`로 임포트되므로 그 패키지 경로에 데이터 쪽 디렉터리를 붙인다.
생성기 LLM은 `runs/serve/<model>.endpoint`에 적힌 vLLM 서버다(scripts/vllm_serve.sbatch).
"""
from __future__ import annotations

import copy
import importlib
import json
import pathlib
import sys
from typing import Any, Iterator

ROOT = pathlib.Path(__file__).resolve().parents[2]
AC = pathlib.Path("/home3/b.ms/projects/standing-delegation/data/agentabstain-code")
AD = pathlib.Path("/home3/b.ms/projects/standing-delegation/data/agentabstain-data")
GEN_MODEL = "qwen3.6-27B"   # 잠정. 생성기·판정기 모델은 Plan.md §12에서 미정

if str(AC) not in sys.path:
    sys.path.insert(0, str(AC))
import abstention_factory.environments as _E  # noqa: E402

if str(AD / "environments") not in _E.__path__:
    _E.__path__.append(str(AD / "environments"))

from abstention_factory.runtime import base as _B  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.runner.run import call_tool as _runner_call_tool  # noqa: E402

# 원본 call_tool은 `-> list` 툴에서 None을 돌려준다(씨앗 131 중 35의 조회 결과). 러너와 같은 구현으로 바꾼다.
_B.BaseEnvironment.call_tool = lambda self, tool_name, **params: _runner_call_tool(self, tool_name, params)


def env_class(env: str):
    m = importlib.import_module(f"abstention_factory.environments.{env}.environment")
    return next(v for k, v in vars(m).items()
                if k.endswith("Environment") and k != "BaseEnvironment" and isinstance(v, type))


def schema_module(env: str):
    return importlib.import_module(f"abstention_factory.environments.{env}.schema")


def env_source(env: str) -> str:
    return (AD / "environments" / env / "environment.py").read_text()


def seeds() -> Iterator[dict]:
    """T+ 131: task_type == act ∧ action_type == operational. 초기 상태 경로를 붙여 낸다."""
    for line in (AD / "tasks.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["task_type"] != "act" or r["action_type"] != "operational":
            continue
        envs = r["environments"]
        env = envs[0] if isinstance(envs, list) else envs
        r["env"] = env
        r["initial_state_path"] = AD / "tasks" / r["pair_id"] / "act" / "initial_states" / f"{env}.json"
        yield r


def initial_state(seed: dict) -> dict:
    return json.loads(pathlib.Path(seed["initial_state_path"]).read_text())


def dag_tool(node: dict) -> str:
    """'env.tool' → 'tool'."""
    return node["tool"].split(".", 1)[-1]


def snapshot(env_obj) -> dict:
    """env.state를 JSON 값으로 직렬화한 사본."""
    def conv(x: Any):
        if hasattr(x, "to_dict"):
            return conv(x.to_dict())
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [conv(v) for v in x]
        return x
    return json.loads(json.dumps(conv(copy.deepcopy(env_obj.state)), default=str))


def touched(before: dict, after: dict) -> set[str]:
    return {k for k in set(before) | set(after) if before.get(k) != after.get(k)}


# ---- 생성기 LLM -------------------------------------------------------------
_client = None


def llm():
    global _client
    if _client is None:
        import openai
        ep = (ROOT / "runs" / "serve" / f"{GEN_MODEL}.endpoint").read_text().strip()
        _client = openai.OpenAI(base_url=ep, api_key="EMPTY", timeout=900)
    return _client


def ask(prompt: str, system: str | None = None, max_tokens: int = 16384, **kw) -> dict:
    """단발 호출. 추론은 서버의 reasoning parser가 분리하고 읽지 않는다. 샘플링은 서버 기본값."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    r = llm().chat.completions.create(model=GEN_MODEL, messages=msgs, max_tokens=max_tokens, **kw).model_dump()
    m = r["choices"][0]["message"]
    return {"content": m.get("content") or "", "finish": r["choices"][0].get("finish_reason"), "usage": r.get("usage")}


def extract_block(text: str, lang: str = "python") -> str | None:
    """응답에서 마지막 ```lang 코드 블록."""
    import re
    blocks = re.findall(rf"```{lang}\s*\n(.*?)```", text, re.S)
    return blocks[-1] if blocks else None


# ---- 여러 환경을 쓰는 씨앗 ------------------------------------------------------
def seed_envs(seed: dict) -> list[str]:
    e = seed["environments"]
    return list(e) if isinstance(e, list) else [e]


def seed_init(seed: dict) -> dict:
    """{환경 이름: 초기 상태}. 씨앗 폴더의 initial_states/<env>.json 전부."""
    d = pathlib.Path(seed["initial_state_path"]).parent
    return {n: json.loads((d / f"{n}.json").read_text()) for n in seed_envs(seed)}


def composite(env_names: list[str], prefer: dict[str, str] | None = None):
    """씨앗의 환경 전부를 한 객체로 묶은 클래스. 상태 키는 '<env>:<collection>'.
    툴 호출은 그 툴을 가진 환경으로 보낸다(참조 계획의 접두어가 실제 소속과 다를 때가 있다)."""
    classes = {n: env_class(n) for n in env_names}
    owner: dict[str, str] = {}
    for n, c in classes.items():
        for s in c.get_tool_schemas():
            owner.setdefault(s["name"], n)

    class Composite:
        envs_order = env_names
        mutation_id_fields = set().union(*(c.mutation_id_fields for c in classes.values()))
        tool_kinds = {k: v for c in classes.values() for k, v in c.tool_kinds.items()}

        @classmethod
        def get_tool_schemas(cls):
            seen, out = set(), []
            for c in classes.values():
                for s in c.get_tool_schemas():
                    if s["name"] not in seen:
                        seen.add(s["name"])
                        out.append(s)
            return out

        def __init__(self, init: dict):
            self.envs = {n: classes[n](init[n]) for n in env_names}

        @property
        def state(self):
            return {f"{n}:{k}": v for n, e in self.envs.items() for k, v in e.state.items()}

        def call_tool(self, name: str, **params):
            if name not in owner:
                raise KeyError(f"Unknown tool: {name!r}")
            return self.envs[owner[name]].call_tool(name, **params)

    return Composite
