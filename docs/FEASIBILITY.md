# FEASIBILITY: 실현 가능성 스파이크 (S0-7)

지위: Stage 0 작업 S0-7의 조회 결과. 모델 판 문자열, 서빙 자원, 키 유무, 파이썬 호환을 **실제 조회로** 확인한 기록이다. 추측은 `[미확인]`으로 남긴다. 여기 수치가 주장으로 쓰이면 stats-analyst가 `docs/EVIDENCE.md`로 옮긴다.

- 실행일: **2026-09-16** (`date -Iseconds` → `2026-09-16T09:59:29+09:00`)
- 실행자: harness-engineer (Stage 0)
- 제약 준수: 대형 잡 제출 없음, `sbatch` 제출 없음, 모델 가중치 다운로드 없음. HF/vLLM/Google 문서 조회(curl)와 로컬 파일 읽기, 그리고 이 저장소 `.venv` 생성만 수행.
- 쓴 파일: 이 파일, `/home3/b.ms/projects/standing-delegation-v2/.venv/` (§5).

---

## 1. 로컬 중형 후보 표

### 1.1 조회 명령

```bash
# 계열 목록 검색
curl -s "https://huggingface.co/api/models?author=Qwen&search=Qwen3.8&limit=50"
curl -s "https://huggingface.co/api/models?author=zai-org&limit=60&sort=lastModified&direction=-1"
curl -s "https://huggingface.co/api/models?author=MiniMaxAI&limit=40&sort=lastModified&direction=-1"
curl -s "https://huggingface.co/api/models?author=nvidia&search=Nemotron&limit=60&sort=lastModified&direction=-1"

# 후보별 실재·크기 (siblings 의 size 를 .safetensors 만 합산)
curl -s "https://huggingface.co/api/models/<repo_id>?blobs=true"

# 아키텍처·양자화·컨텍스트
curl -s https://huggingface.co/<repo_id>/raw/main/config.json
curl -s https://huggingface.co/<repo_id>/raw/main/generation_config.json
curl -s https://huggingface.co/<repo_id>/raw/main/tokenizer_config.json

# vLLM 공식 레시피 (파서 플래그·검증 하드웨어)
curl -sL https://recipes.vllm.ai/Qwen/Qwen3.8-27B
curl -sL https://recipes.vllm.ai/openai/gpt-oss-120b
```

### 1.2 후보 표

가중치 크기는 HF API `siblings[].size` 중 `*.safetensors`만 합산한 값(GiB, `original/` 제외). GPU 수는 가중치 + KV 여유로 본 추정이며, 실측 아님(← 서빙 잡은 Stage 1).

| repo id | 실재 | 파라미터 총/활성 | 가중치 | 아키텍처 / ctx | 1노드 GPU 추정 | vLLM tool-call 파서 | vLLM reasoning 파서 | 리더보드 | 라이선스 | 공개일 |
|---|---|---|---|---|---|---|---|---|---|---|
| `Qwen/Qwen3.8-27B-FP8` | [확인] HTTP 200 | 27.78B 총 / 27.78B (dense) | **28.7 GiB** (FP8 E4M3 24.7B + BF16 3.08B, 66파일) | `Qwen3_5ForConditionalGeneration`, `qwen3_5`, hybrid(64층 중 48 linear attention), VLM(vision tower), 262,144 ctx | **1×48GB** (RTX6000ADA/L40S, sm89 FP8 네이티브) 또는 1×80GB | **[확인]** `qwen3_xml` (vLLM 공식 레시피 명령) | **[확인]** `qwen3` | **없음** | apache-2.0 | 2026-08-13 |
| `Qwen/Qwen3.8-27B` | [확인] HTTP 200 | 27.78B / dense | 51.7 GiB (BF16, 18파일) | 동일 | 1×80GB | [확인] `qwen3_xml` | [확인] `qwen3` | 없음 | apache-2.0 | 2026-08-05 |
| `openai/gpt-oss-120b` | [확인] HTTP 200 | 116.83B 총 / **5.1B 활성** (MoE, 128전문가·top-4) | **60.8 GiB** (MXFP4 U8 114.7B + BF16 2.17B, 15파일) | `GptOssForCausalLM`, `gpt_oss`, 131,072 ctx | **1×80GB** (vLLM 레시피: "A100 80GB for single-GPU", `vllm serve openai/gpt-oss-120b`) | **[확인]** `openai` (레시피: `--tool-call-parser openai --enable-auto-tool-choice`) | **[확인]** `openai_gptoss` | **9위** (OpenClaw, Act 78.3 / Abstain 59.5 / Paired 46.2 / CAR 58.2) | apache-2.0 | 2025-08-04 |
| `openai/gpt-oss-20b` | [확인] HTTP 200 | 20.91B 총 / **3.6B 활성** (32전문가·top-4) | **12.8 GiB** (MXFP4) | `gpt_oss`, 131,072 ctx | 1×24GB (RTX3090)~1×48GB | [확인] `openai` | [확인] `openai_gptoss` | 없음 | apache-2.0 | 2025-08-04 |
| `zai-org/GLM-4.7-Flash` | [확인] HTTP 200 | 31.22B 총 / **A3B 활성** (64 routed + 1 shared, top-4; 카드: "30B-A3B MoE") | **58.2 GiB** (BF16, 2파일) | `Glm4MoeLiteForCausalLM`, `glm4_moe_lite`, 202,752 ctx | 1×80GB (카드 예시는 TP=4) | **[확인]** `glm47` (모델 카드 vllm serve) | **[확인]** `glm45` (모델 카드) | 없음 | mit | 2026-01-19 |
| `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` | [확인] HTTP 200 | 31.58B / A3B | 61.3 GiB (BF16) | `NemotronHForCausalLM`, `nemotron_h`, 262,144 ctx | 1×80GB | **[미확인]** (vLLM 0.26.0 tool 파서 목록에 `nemotron` 없음; `hermes`/`pythonic` 유효성 미확인) | [확인] `nemotron_v3` | 없음 | other | 2026-08-01 |
| `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` | [확인] HTTP 200 | 17.82B(양자화 후 카운트) | 20.1 GiB (NVFP4) | `nemotron_h` | 1×48GB 이하(NVFP4는 Blackwell 전용 커널 — **A100/H200/Ada에서 미검증** `[미확인]`) | [미확인] | [확인] `nemotron_v3` | 없음 | other | 2026-08-04 |
| `google/gemma-4-26B-A4B-it` | [확인] HTTP 200 | 25.81B / A4B (128전문가) | 48.1 GiB (BF16) | `Gemma4ForConditionalGeneration` | 1×80GB (**이전 프로젝트 실측**: 가중치 48.5 GiB, KV 20.75 GiB, 232,328토큰, A100-80GB TP=1) | [확인] `gemma4` | [확인] `gemma4` | 없음 | apache-2.0 | 2026-03-11 |
| `Qwen/Qwen3.8-Flash-Next-FP8` | [확인] HTTP 200 | 180.0B / [미확인] | 172.8 GiB | `qwen4_exp` — **vLLM 0.26.0 registry에 `Qwen4ExpForConditionalGeneration` 없음** | 3×80GB 이상 | [미확인] | [미확인] | 없음 | other | 2026-08-24 |
| `zai-org/GLM-5.3-Flash` | [확인] HTTP 200 | 321.3B / [미확인] | 305.8 GiB | `glm5_next` — **vLLM 0.26.0 registry에 없음** | 4×80GB 이상 | [미확인] | [미확인] | 없음 | mit | 2026-08-25 |
| `MiniMaxAI/MiniMax-M2.5` | [확인] HTTP 200 | 228.7B / [미확인] | 214.3 GiB (FP8) | — | 3×80GB 이상 | [확인] `minimax_m2` | [확인] `minimax_m2` | **11위** (OpenClaw, 83.8/50.1/41.9/49.6) | other | 2026-02-12 |
| `zai-org/GLM-5` | [확인] HTTP 200 | 753.9B | 1404.2 GiB (BF16) | — | ≥16×80GB (**중형 아님**) | [확인] `glm47` | [확인] `glm47` | **8위** | mit | 2026-02-11 |
| `zai-org/GLM-5-Air`, `GLM-5-Flash`, `GLM-4.7-Air`, `GLM-4.7-Flash-FP8` | **[미확인] — 존재하지 않음** (HTTP **401**; 같은 조회 방식으로 `GLM-5`/`GLM-5.3-Flash`/`GLM-4.7-Flash`는 200. zai-org 전체 목록 60건에도 없음) | — | — | — | — | — | — | — | — | — |

리더보드 원문: `/home3/b.ms/projects/standing-delegation/data/agentabstain-code/README.md` 33~62행. 17개 모델 전부 상업 API 또는 OpenClaw 게이트웨이(OpenRouter/Bedrock)로 돌렸고, **로컬 서빙 가능한 항목은 GPT-OSS 120B(9위), MiniMax M2.5(11위), GLM-5(8위), DeepSeek V3.2(12위), DeepSeek V4 Pro(15위), Kimi K2.5(16위)** 뿐이다. 이 중 1노드 이하로 서빙되는 것은 **GPT-OSS 120B 하나**다. [확인]

### 1.3 파서 목록 확인 근거 (로컬 vLLM 0.26.0 레지스트리)

```bash
SP=/home3/b.ms/projects/multiturn-reliability-env/.venv/lib/python3.12/site-packages
python3 -c "import re;print(sorted(re.findall(r'^    \"([^\"]+)\": \(', open('$SP/vllm/reasoning/__init__.py').read(), re.M)))"
python3 -c "import re;print(sorted(re.findall(r'^    \"([^\"]+)\": \(', open('$SP/vllm/tool_parsers/__init__.py').read(), re.M)))"
```

- reasoning 파서 28종: `cohere_command3/4, deepseek_r1, deepseek_v3, deepseek_v4, ernie45, gemma4, glm45, glm47, granite, holo2, hunyuan_a13b, hy_v3, kimi_k2, mimo, minimax_m2, minimax_m2_append_think, minimax_m3, mistral, nemotron_v3, olmo3, openai_gptoss, poolside_v1, qwen3, seed_oss, step3, step3p5` [확인]
- tool-call 파서 44종: `..., gemma4, glm45, glm47, hermes, kimi_k2, minimax_m2, minimax_m3, openai, pythonic, qwen3_coder, qwen3_xml, ...` — **`qwen3`라는 tool 파서는 없다**. Qwen 계열은 `qwen3_xml` 또는 `qwen3_coder`(둘 다 `Qwen3EngineToolParser`로 매핑). [확인]
- 주의: `ReasoningParserManager.reasoning_parsers`는 lazy 등록이라 임포트 직후 빈 dict다. 이름은 `_REASONING_PARSERS_TO_REGISTER` / `_TOOL_PARSERS_TO_REGISTER` 딕셔너리에서 읽어야 한다. [확인]

### 1.4 Qwen3.8-27B-FP8 세부 (권고 1순위 근거)

- chat template 실측 (`tokenizer_config.json`, 8,952자): `<tool_call>` 5회, `</tool_call>` 3회, `<think>` 3회, `</think>` 2회, `tool_response` 4회, **`reasoning_content` 7회**. → 툴 호출과 추론 트레이스 분리가 템플릿 수준에서 지원된다. [확인]
- 모델 카드: "Thinking mode is **on by default** and can be disabled per request; reasoning depth can be tuned with `reasoning_effort`(`xhigh`/`medium`/`low`, 기본 `xhigh`), and reasoning context from historical messages is retained via `preserve_thinking`." OpenAI 호환 델타에서 `delta.reasoning_content` / `delta.reasoning`를 읽는 예제를 카드가 직접 싣는다. [확인]
- 비-thinking 모드: `chat_template_kwargs: {"enable_thinking": false}`. [확인]
- 권장 샘플링(카드): thinking `T=1.0, top_p=0.95, top_k=20`; `generation_config.json` = `temperature 1.0, top_k 20, top_p 0.95`. 우리 러너 기본은 T=0이므로 **판 차이를 로그에 남긴다**(`Plan.md` §2). [확인]
- vLLM 공식 레시피 (`recipes.vllm.ai/Qwen/Qwen3.8-27B`, 2026-09-14 갱신): `softwareRequirements: vLLM 0.17.0+`. 검증 하드웨어 키워드 = **GB300 NVL4, RTX 5090, RTX Pro 6000, DGX Spark(GB10), Ascend 950PR** — 전부 Blackwell/Ascend. **A100/H200(Hopper·Ampere)은 레시피에 없다** `[미확인]`. FP8 체크포인트는 "vLLM auto-disables DeepGemm for `model_type=qwen3_5_text` on Blackwell and falls back to CUTLASS"라고만 적혀 있다.
  - 확인된 명령 형태: `vllm serve Qwen/Qwen3.8-27B-FP8 --tensor-parallel-size 4 --max-model-len 262144 --kv-cache-dtype fp8 --reasoning-parser qwen3` / TP1 NVFP4 예에는 `--enable-auto-tool-choice --tool-call-parser qwen3_xml`이 붙는다. [확인]
  - TP2(RTX 5090 2장) FP8 실측치가 레시피에 있다: KV 377,456 토큰, **가중치 14.28 GiB/GPU** (→ 총 28.6 GiB, HF 합산 28.7 GiB와 일치). [확인]
- **위험**: hybrid(linear attention) 모델은 시퀀스마다 상태 캐시 블록을 쓴다. 이전 프로젝트 실측(잡 789097, 48GB 카드): `max_num_seqs (256) exceeds available Mamba cache blocks (133)`로 기동 실패. 48GB에 얹으면 `--max-num-seqs`를 96 이하로 내려야 한다. (`/home3/b.ms/projects/underspec/scripts/vllm_serve.sbatch` 주석) [확인]

---

## 2. 이전 프로젝트의 서빙 환경

### 2.1 venv 위치 정정

```bash
/home3/b.ms/projects/underspec/.venv/bin/python -c "import vllm; print(vllm.__version__)"
# → ModuleNotFoundError: No module named 'vllm'   (Python 3.11.12)
/home3/b.ms/projects/multiturn-reliability-env/.venv/bin/python -c "import vllm; print(vllm.__version__)"
# → 0.26.0   (Python 3.12.10)
```

**`underspec/.venv`에는 vLLM이 없다** (감사 코드용 py3.11 환경). 실제 서빙 환경은 **`/home3/b.ms/projects/multiturn-reliability-env/.venv` = Python 3.12.10 + vLLM 0.26.0** 이며, `vllm_serve.sbatch`가 그 경로를 activate한다. A100/H200 동일 wheel. [확인]

### 2.2 `underspec/scripts/vllm_serve.sbatch` 옵션 (실측 검증된 값)

| 항목 | 값 |
|---|---|
| 파티션 | `#SBATCH --partition=H200` (기본값; 제출 시 오버라이드 전제) |
| GPU / CPU / 시간 | `--gres=gpu:1`, `--cpus-per-task=8`, `--time=1-00:00:00` |
| 로그 | `slurm_logs/%x-%j.{out,err}` |
| TP | `TP="${3:-1}"` (기본 1) |
| `--max-model-len` | `${2:-131072}` — A100-80GB KV 풀 실측 상한에서 물러선 값 |
| `--max-num-seqs` | `${MAX_SEQS:-256}` (하이브리드/소형 카드에서 96 등으로 낮춤) |
| `--gpu-memory-utilization` | `0.90` |
| `--seed` | `20260729` (서버 측 재현성) |
| **reasoning parser** | 모델 키별: `qwen3.6-27B` → `qwen3`, `qwen3.6-35B-A3B-FP8` → `qwen3`, `gemma4-26B-A4B-it` → (없음), `qwen3-4B-instruct` → (없음). 플래그는 `${REASONING_PARSER:+--reasoning-parser "$REASONING_PARSER"}` |
| **tool-call parser** | **없음** — 이 스크립트는 `--tool-call-parser`/`--enable-auto-tool-choice`를 전혀 쓰지 않는다. 우리 러너는 툴 호출이 필수이므로 **새 플래그를 추가해야 한다**. [확인·차이점] |
| 기타 | `HF_HUB_OFFLINE=1` 강제(계산 노드 외부 DNS 차단), `VLLM_USE_DEEP_GEMM=0`(Hopper FP8 DeepGEMM NVCC JIT 사망 회피, 잡 719119/n90), `--no-enable-log-requests` |
| 순서 함정 | `source ~/slurm_common.sh` **뒤에** `set -eo pipefail`. 앞에 두면 ExitCode 11 즉사 |
| 엔드포인트 공개 | `/v1/models` 헬스체크 통과 후 `runs/serve/<model_key>.endpoint`에 `http://HOST:PORT/v1` 기록. 포트는 `8000 + SLURM_JOB_ID % 1000`. 적재 대기 `SERVE_WAIT_TICKS:-180`(30분) |

### 2.3 `underspec/configs/*.yaml` 엔드포인트 설정 형태

```yaml
models:
  mut: gemma4-26B-A4B-it
  extractor: qwen3.6-27B
  judge: qwen3.6-27B
endpoints:
  gemma4-26B-A4B-it:
    base_url: http://localhost:8000/v1
    base_url_env: GEMMA4_VLLM_URL      # env 가 있으면 base_url 을 이긴다
    api_key_env: VLLM_API_KEY          # set 일 때만 전송
    timeout: 900
  qwen3.6-27B:
    base_url: http://localhost:8001/v1
    base_url_env: QWEN36_VLLM_URL
    api_key_env: VLLM_API_KEY
    timeout: 900
max_tokens: 8192      # reasoning 모델: thinking 이 답을 밀어내지 않게
temperature: 1.0
parallel_instances: 10
parallel_pins: 30
```

- 여기 없는 모델 키는 Anthropic API로 라우팅된다(`phase1.yaml` 주석). `served_model` 오버라이드 필드가 있으나 서버가 `--served-model-name`으로 같은 키를 등록하므로 미사용. [확인]
- `multiturn-reliability-env/configs/models.yaml`의 A100-80GB 실측 (2026-07-30, util 0.90 = 71.35 GiB 예산): Qwen3.6-27B 가중치 51.1 GiB → KV 17.18 GiB(245,077토큰); gemma-4-26B-A4B-it 가중치 48.5 GiB → KV 20.75 GiB(232,328토큰). 파티션 `A100-80GB`, `qos: hpgpu`, TP=1. [확인]

---

## 3. API 키 (값은 조회·기록하지 않음)

```bash
for v in ANTHROPIC_API_KEY OPENAI_API_KEY GOOGLE_API_KEY GEMINI_API_KEY; do
  if [ -n "${!v}" ]; then echo "$v: set"; else echo "$v: unset"; fi; done
grep -cE 'export (ANTHROPIC_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|GEMINI_API_KEY)' ~/.bashrc ~/.zshrc ~/.bash_profile
find /home3/b.ms/projects -maxdepth 3 -name ".env*" -type f
```

| 항목 | 결과 |
|---|---|
| `ANTHROPIC_API_KEY` | **unset** |
| `OPENAI_API_KEY` | **unset** |
| `GOOGLE_API_KEY` | **unset** |
| `GEMINI_API_KEY` | **unset** |
| (참고) `ANTHROPIC_AUTH_TOKEN`, `HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN` | 모두 unset |
| `~/.bashrc` | 존재, 해당 export 줄 수 **0** |
| `~/.zshrc` | 존재, **0** |
| `~/.bash_profile` | 존재, **0** |
| `~/.profile` | 없음 |
| 프로젝트 `.env` | `standing-delegation-v2`, `standing-delegation`, `underspec` 모두 **없음**. `projects` 하위 3단계까지 `.env*` 파일 **0건** |
| AgentAbstain `.env.template` | 존재(`data/agentabstain-code/.env.template`) — 채워지지 않은 템플릿. 필요한 키를 하네스별로 명시: `OPENAI_API_KEY`(OpenAI SDK + 판정기), `GOOGLE_API_KEY`(Google ADK), `OPENROUTER_API_KEY`(OpenClaw), `ANTHROPIC_API_KEY` 또는 Bedrock(`CLAUDE_CODE_USE_BEDROCK=1`, `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`) |

**결론**: 상업 모델(Claude Opus 4.7 / GPT-5.5)과 판정기(Gemini 3.1 Pro)를 부를 키가 **현재 하나도 없다**. `Plan.md` §3의 상업 2개 + 판정기 1개는 키 확보가 선행 조건이다. Stage 1 시작 전 저자가 키를 넣어야 한다. 값은 절대 문서·로그에 남기지 않는다. [확인]

> 참고: Claude 쪽은 API 키 외에 `ant auth login` OAuth 프로필 경로도 있다(`claude-api` 스킬 §Authentication). `ant auth status`로 확인 가능하나 이번 스파이크에서는 실행하지 않았다 `[미확인]`.

---

## 4. 클러스터 (제출 없음)

`slurm-assistant` 스킬을 먼저 읽었다(Skill 도구). 아래는 그 규칙 + 실제 조회.

### 4.1 1×80GB 또는 2×80GB 서빙 잡의 파티션·QOS

| 후보 | 파티션 | VRAM | CPU/GPU | QOS | 비고 |
|---|---|---|---|---|---|
| 1순위(80GB급) | `A100-80GB` | 80GB | 8 | **`hpgpu`** | 14노드 112 GPU. 사용자당 hpgpu 동시 16 GPU 한도(현재 사용 0/16) |
| 2순위(141GB) | `H200-ZT` / `H200-PCIe-ZT` | 141GB | 8 | **`zt`** | Priority 1000으로 최우선 스케줄, **hpgpu 16 GPU 한도와 무관**. 이 두 파티션에 hpgpu를 쓰면 순손해 |
| 3순위(141GB) | `H200` | 141GB | 8 | `hpgpu` | 2노드뿐 |
| 48GB 대안 | `RTX6000ADA` / `L40S` | 48GB | 4 / 8 | **QOS 줄 생략** | sm89 = FP8 네이티브. Qwen3.8-27B-FP8(28.7 GiB)이 1장에 들어간다 |

- `--partition`은 **항상 명시**해야 한다(기본값이 RTX2080Ti).
- CPU는 `--cpus-per-task = GPU수 × 파티션 비율`. A100-80GB/H200 = 8, RTX6000ADA = 4, L40S = 8.
- 메모리는 생략(전 파티션 `MaxMemPerNode=UNLIMITED`).
- 계산 노드는 외부 네트워크가 없다 → 가중치를 **로그인 노드에서 미리 받아** `HF_HUB_OFFLINE=1`로 읽게 한다. 현재 HF 캐시(`/home3/b.ms/.cache/huggingface/hub`, 428 GB 사용)에 **후보 모델 중 어느 것도 없다** — Stage 1 전에 로그인 노드에서 받아야 한다(FP8 28.7 GiB / gpt-oss-120b 60.8 GiB). `/home3` 여유 20 TB. [확인]

### 4.2 지금 idle 자원 (2026-09-16 09:59 KST)

```bash
sinfo -o "%20P %5a %10l %6D %6t %N"
bash ~/.claude/skills/slurm-assistant/scripts/cluster_status.sh A100-80GB
bash ~/.claude/skills/slurm-assistant/scripts/cluster_status.sh H200-ZT
sinfo -p A100-80GB,H200,H200-ZT,H200-PCIe-ZT,L40S,RTX6000ADA -N \
  -O "NodeList:12,Partition:14,StateCompact:8,Gres:20,GresUsed:24" --noheader
```

| 파티션 | 총 GPU | 여유(노드별 GresUsed 기준) | 대기잡 | 상태 |
|---|---|---|---|---|
| `A100-80GB` | 112 | **3** (n51 2장, n57 1장; 나머지 12노드 8/8 사용) — `cluster_status.sh` AVAIL 표기 8 | **396** | 사실상 만석 |
| `H200` | 16 | **0** (n87 drain, n88 8/8 alloc) | — | 불가 |
| `H200-ZT` | 16 | **0** (n89 8/8 사용, n90 drain*) | **87** | 대기, 단 `zt` 우선순위 1000 |
| `H200-PCIe-ZT` | 15 | **0** (n91 8/8, n92 drain*) | — | 대기 |
| `RTX6000ADA` (48GB) | 80 | **17** (n61:2, n63:4, n64:4, n65:4, n70:3) | — | **여유 있음** |
| `L40S` (48GB) | 48 | **6** (n84/85/86 각 2) | — | 여유 있음 |
| 내 hpgpu 사용량 | — | **0/16 (여유 16)** | — | |

**함의**: 80GB급은 지금 거의 없고 A100-80GB 대기가 396잡이다. 반면 48GB(RTX6000ADA/L40S)는 23장이 비어 있다. **Qwen3.8-27B-FP8(28.7 GiB)은 48GB 1장에 들어가므로 파일럿 서빙이 즉시 가능**하고, gpt-oss-120b(60.8 GiB)는 A100-80GB 1장을 기다려야 한다. 2×48GB TP2로 gpt-oss-120b를 얹는 것은 vLLM 레시피에 없다 `[미확인]`(레시피의 검증 하드웨어는 H100/H200/B200 + "A100 80GB for single-GPU").

**제출은 하지 않았다.** `squeue`/`sacct`/`sbatch` 제출 0건.

---

## 5. 파이썬 호환 (3.12) — 실행 성공

### 5.1 AgentAbstain 코드 구조 판단

- `requirements.txt`(`/home3/b.ms/projects/standing-delegation/data/agentabstain-code/requirements.txt`)는 **버전 핀이 하나도 없다**. 내용: `PyYAML, python-dotenv, pydantic, fastmcp, mcp, openai, anthropic, tqdm` + 하네스 SDK `openai-agents, claude-code-sdk, google-adk, google-genai` + `huggingface_hub` + `numpy, pandas, scipy, matplotlib, pillow`.
- 패키징 파일 없음(`setup.py`/`pyproject.toml`/`setup.cfg` 전부 부재) → `PYTHONPATH`로 리포 루트를 얹어 쓴다.
- v1 `AGENTABSTAIN.md` §1.5는 python 3.11을 적지만, **우리는 하네스 SDK 4개를 쓰지 않는다**(`Plan.md` §2: 어댑터는 OpenAI 호환 chat completions 하나, 환경은 같은 프로세스 `MultiEnvironment.call_tool`). 필요한 것은 `abstention_factory.runtime.{base,multi,registry}` + `fastmcp/mcp/pydantic/PyYAML`뿐이고, 여기에 3.12를 막는 요소가 없다.
- `abstention_factory/runtime/__init__.py`는 **의도적으로 비어 있다**(순환 임포트 회피). 소비자는 `abstention_factory.runtime.base` / `.multi` / `.registry`를 직접 임포트해야 한다. `src/runtime/__init__.py`는 `src.runtime.openaisdk`(= `openai-agents` 의존)를 재수출하므로 **건드리지 않는다**.
- 환경 패키지는 `AGENTABSTAIN_DATA`가 가리키는 디렉터리 하위의 `environments/`에서 동적으로 임포트된다(`abstention_factory/environments/__init__.py` 11행: `Path(os.environ.get("AGENTABSTAIN_DATA","data")).resolve()/"environments"`).

### 5.2 실행한 명령과 결과

```bash
cd /home3/b.ms/projects/standing-delegation-v2
uv venv --python 3.12 .venv                        # uv 0.6.17 → CPython 3.12.10
uv pip install --python ./.venv/bin/python fastmcp mcp pydantic PyYAML openai

export AGENTABSTAIN_DATA=/home3/b.ms/projects/standing-delegation/data/agentabstain-data
export PYTHONPATH=/home3/b.ms/projects/standing-delegation/data/agentabstain-code
./.venv/bin/python -c "
import json; from pathlib import Path
from abstention_factory.runtime.multi import build_multi_environment
p=Path('$AGENTABSTAIN_DATA')/'tasks/ambiguous_action_specification/preview_001/abstain/initial_states'
st={f.stem: json.loads(f.read_text()) for f in p.glob('*.json')}
me=build_multi_environment(sorted(st), st)
print(len(me.get_tool_schemas()))
"
```

| 검사 | 결과 |
|---|---|
| `uv venv --python 3.12` | **성공** — Python 3.12.10 |
| `fastmcp mcp pydantic PyYAML openai` 설치 | **성공** — `fastmcp 4.0.4`, `mcp 2.2.0`, `pydantic 2.13.5`, `PyYAML 6.0.3`, `openai 3.14.1` |
| `import abstention_factory` | **성공** |
| `abstention_factory.runtime.registry` | **성공** — `ENVIRONMENT_REGISTRY` 42개 환경 (README의 "42 executable MCP sandbox environments"와 일치) |
| `build_multi_environment(...)` 인스턴스화 | **성공** — `MultiEnvironment` 반환 (`preview_001/abstain`, env=`device_privacy_and_focus`) |
| `get_tool_schemas()` | **성공** — 14개. 이름은 `device_privacy_and_focus.<tool>` 형태의 namespaced |
| `__runtime_export_snapshot` 노출 | **스키마에 없음** — `get_tool_schemas()` 결과에 `snapshot` 포함 이름 0건. 그래도 러너에 차단 테스트를 둔다(`harness-engineer` 요구사항) |
| `get_execution_log()` | `list` 반환 |
| 사용 가능 메서드 | `call_tool, get_tool_schemas, get_tool_callable, get_execution_log, get_state_schema, execution_log, state, sub_env, sub_env_names, mutation_tools, mutation_id_fields, tool_kinds, break_tool, abreak_tool, hide_tool, always_skip_fields, env_name, short_name, mcp` |

**결론: 3.12에서 돈다.** `[확인]` 하네스 SDK 4종(`openai-agents`, `claude-code-sdk`, `google-adk`, `google-genai`)의 3.12 호환은 **확인하지 않았다** `[미확인]` — 우리 러너가 쓰지 않으므로 검사 대상이 아니다.

### 5.3 하네스 검증용 문항 수 대조 (D-002)

```bash
python3 -c "
import json,collections
rows=[json.loads(l) for l in open('/home3/b.ms/projects/standing-delegation/data/agentabstain-data/tasks.jsonl')]
print(len(rows)); print(collections.Counter(r['category'] for r in rows))"
```

- `tasks.jsonl` 총 **526행 = 263쌍** (README의 "263 paired tasks"와 일치).
- 시나리오별 행 수: `ambiguous_action_specification 60`, `conflicting_constraints 64`, `conflicting_evidence 60`, `critical_tool_failure 68`, `emergent_risk_discovery 66`, `high_stakes_action 62`, `insufficient_tool_capability 68`, **`missing_critical_parameter 78`**.
- **`Plan.md`/D-002의 "S1 39쌍 78문항"과 행 수가 일치하는 시나리오는 `missing_critical_parameter`(78행 = 39쌍) 하나다.** 다만 논문에서 S1이 이 시나리오를 가리키는지는 리포지터리 문서에 명시가 없다 `[미확인]` — **S1의 시나리오 이름을 저자가 확정해야 한다**. 리더보드 수치는 8개 시나리오 macro-average이고, 논문 표 11(시나리오별 값)은 이 리포에 없다 `[미확인]`.
- 각 행의 필드: `pair_id, category, task_id, task_type(act|abstain), phase(pre_execution|...), transformation_dimension, action_type, instruction, system_prompt, critical_actions, execution_dag, environments, abstention_trigger`. 원 계약 재현에 필요한 `system_prompt`/`instruction`이 그대로 있다. [확인]
- 채점기 참조: `eval/configs/default.yaml` 판정기는 `provider: openai, model: gpt-5.4-2026-03-05, temperature 0.0, max_tokens 1024` 단일 모델. [확인]

---

## 6. 상업 모델·판정기 API 모델 ID

| 모델 | AgentAbstain 논문 캠페인이 쓴 문자열 (리포 `src/configs/`) | 현행 공개 문서 확인 | 판정 |
|---|---|---|---|
| **Claude Opus 4.7** | `us.anthropic.claude-opus-4-7` (Bedrock 라우트, `claudesdk_claude-opus-4-7.yaml`, `temperature 0.0`, `max_turns 30`) | **네이티브 API ID = `claude-opus-4-7`** — `claude-api` 스킬의 Current Models 표(cached 2026-06-24), 1M ctx, $5/$25 per 1M. 날짜 접미사를 붙이지 않는다 | **[확인]** |
| **GPT-5.5** | `gpt-5.5-2026-04-23` (`openaisdk_gpt-5.5.yaml`, `temperature: Null`, `max_turns 30`) | `https://developers.openai.com/api/docs/models` (HTTP 200, 379 KB) 안에 **`gpt-5.5` 문자열 0건**. 현행으로 보이는 것은 `gpt-5.6`, `gpt-5.6-cyber` 등 | ID 문자열은 **[확인]**(리포 설정), **현재 API에서 서빙되는지는 [미확인]**. Stage 1에서 `GET /v1/models`로 확인해야 함 |
| **Gemini 3.1 Pro** | `gemini-3.1-pro-preview` (`googleadk_gemini-3.1-pro.yaml`, `temperature 0.0`) | `https://ai.google.dev/gemini-api/docs/models` (HTTP 200, 149 KB)에 **`gemini-3.1-pro`와 `gemini-3.1-pro-preview` 둘 다 존재**. 같은 문서에 `gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`도 보임 | **[확인]** — 판정기는 `gemini-3.1-pro`(GA)를 쓰고, 논문 재현 목적이면 `gemini-3.1-pro-preview`를 쓴다 |
| (참고) 판정기 원본 | `gpt-5.4-2026-03-05` (`eval/configs/default.yaml`) | 미조회 | **[미확인]** |
| (참고) 리더보드 기타 | `amazon-bedrock/openai.gpt-oss-120b-1:0`, `amazon-bedrock/zai.glm-5`, `amazon-bedrock/minimax.minimax-m2.5`, `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `gemini-3-flash-preview`, `gpt-5-2025-08-07`, `gpt-5.1-2025-11-13`, `gpt-5.2-2025-12-11`, `gpt-5.4-2026-03-05`, `gpt-4o-2024-08-06`, `openrouter/deepseek/deepseek-v4-pro` | | **[확인]** (리포 설정 문자열) |

`claude-api` 스킬을 Skill 도구로 읽어 Claude 쪽을 확인했다. 스킬은 기본 모델로 `claude-opus-5`를 쓰라고 하지만, **우리는 리더보드 재현을 위해 `claude-opus-4-7`을 고정한다**(`Plan.md` §3). 주의: Opus 4.7은 `budget_tokens`가 제거되어 400을 내고, `thinking`을 생략하면 사고 없이 돈다 → `thinking: {type:"adaptive"}`를 명시해야 추론 트레이스(요약)가 나온다. `temperature`/`top_p`도 제거되어 400이다 → **Opus 4.7에는 T=0을 보낼 수 없다**. 이 판 차이를 로그와 `Plan.md` §2 "샘플링 기본 T=0, 무시하는 모델은 기록"에 반영해야 한다. [확인]

---

## 7. 권고 (저자 확정 대기)

### 7.1 로컬 모델

| 자리 | 모델 | 근거 |
|---|---|---|
| **파일럿 A (1순위)** | **`Qwen/Qwen3.8-27B-FP8`** | 저자가 든 판이 실재(HF 200). 28.7 GiB → **48GB 1장**에 들어가고 그 파티션은 지금 23장 여유. `--reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_xml`이 vLLM 공식 레시피에 있다. chat template에 `reasoning_content` 7회. apache-2.0. vLLM 0.17.0+ 요구 → 우리 0.26.0 충족 |
| **파일럿 B (2순위)** | **`zai-org/GLM-4.7-Flash`** | 30B-A3B, 58.2 GiB → 1×80GB. `--tool-call-parser glm47 --reasoning-parser glm45`가 **모델 카드 명령에 직접** 있다. mit. 아키텍처 `Glm4MoeLiteForCausalLM`가 vLLM 0.26.0 registry에 있음. 계열이 Qwen과 달라 "모델 간 차이 = 엔드포인트와 reasoning 필드 이름뿐"을 검사하기에 좋다 |
| **본 실험 추가 C** | **`openai/gpt-oss-120b`** | 하네스 검증 모델과 동일 판을 본 실험에도 쓰면 검증→본실험 판 동일성이 공짜로 따라온다. 60.8 GiB, A100-80GB 1장(레시피 명시). apache-2.0 |
| 대안(C 실패 시) | `google/gemma-4-26B-A4B-it` | **이전 프로젝트에서 A100-80GB TP=1로 실제 서빙된 유일한 후보**(가중치 48.5 GiB, KV 232k토큰 실측). 단 `vllm_serve.sbatch`에서 reasoning parser 없이 돌렸으므로 `--reasoning-parser gemma4` 동작은 미검증 `[미확인]` |
| 개발용 소형 | `Qwen/Qwen3-4B-Instruct-2507` 또는 `openai/gpt-oss-20b` | 전자는 `vllm_serve.sbatch`에 이미 등록되어 RTX3090 24GB에 얹힌다(A100/H200 큐 회피). 후자는 12.8 GiB로 gpt-oss와 **같은 파서 경로**(`openai`/`openai_gptoss`)를 디버깅할 수 있다 |

### 7.2 하네스 검증 모델

**`openai/gpt-oss-120b`** — AgentAbstain 리더보드 9위이면서 1노드 이하로 서빙되는 **유일한** 후보다. 리더보드 macro 값: Act **78.3** / Abstain **59.5** / Paired 46.2 / CAR 58.2. [확인]

- 서빙: `A100-80GB`, `--gres=gpu:1 --cpus-per-task=8 --qos=hpgpu`, `--tool-call-parser openai --enable-auto-tool-choice --reasoning-parser openai_gptoss`. 지금 대기 396잡이므로 **가중치를 로그인 노드에서 먼저 받아 두고**(60.8 GiB) 큐에 넣는다.
- 남는 위험 2개:
  1. **하네스 불일치.** 리더보드 수치는 OpenClaw 하네스 + `amazon-bedrock/openai.gpt-oss-120b-1:0` 라우트다. 우리는 vLLM 로컬 서빙 + 자체 루프다. ±10%p 검사는 이 차이를 통과시키지 못할 수 있다 → EVIDENCE에 하네스 차이를 반드시 병기한다(D-002 철회 조건과 같은 취지).
  2. **`tool_choice` 제약.** vLLM 레시피 Known Limitations: "Function calling currently supports only `tool_choice="auto"`". 우리 러너가 forced tool choice를 쓰면 못 쓴다 → 러너는 `auto`만 쓰도록 고정한다.
- 비교 대상 수치의 시나리오 분해(논문 표 11)가 이 리포에 없다 `[미확인]`. S1이 어느 시나리오인지도 미확정(§5.3).

---

## 8. 미확인 항목 정리

1. **S1의 시나리오 이름.** 행 수(78 = 39쌍)로는 `missing_critical_parameter`가 유일하게 일치하나 리포에 S1↔시나리오 매핑이 없다. 논문 표 11의 시나리오별 act/abstain 값도 리포에 없다. → 저자 확정 필요.
2. **GPT-5.5의 현재 서빙 여부.** 리포 설정의 `gpt-5.5-2026-04-23`은 확인했지만 OpenAI 현행 문서에 `gpt-5.5`가 없다(`gpt-5.6`이 보인다). Stage 1에서 `GET /v1/models`로 확인.
3. **Qwen3.8-27B-FP8의 Hopper/Ampere 검증.** vLLM 공식 레시피는 Blackwell/Ascend만 검증했다. A100-80GB(FP8 → W8A16 marlin 경로)와 H200(DeepGEMM NVCC JIT 사망 이력 → `VLLM_USE_DEEP_GEMM=0`), 그리고 48GB Ada에서의 하이브리드 상태 캐시 블록 한계(`--max-num-seqs` 하향 필요)는 모두 실기동으로만 확인된다.
4. **2×48GB TP2로 gpt-oss-120b** — 레시피에 없음.
5. **Nemotron 3.5 Lightning의 vLLM tool-call 파서** — 전용 파서 없음. `hermes`/`pythonic` 대체 가능성 미확인. NVFP4 판은 Blackwell 전용 커널 의심.
6. **`--reasoning-parser gemma4` 실동작** — 이전 프로젝트는 gemma4를 파서 없이 서빙했다.
7. **API 키 4종 전부 부재.** 상업 2개 + 판정기 1개는 키 확보가 선행 조건. Claude는 `ant auth login` OAuth 프로필 경로도 가능하나 `ant auth status`를 실행하지 않았다.
8. **HF 캐시에 후보 모델 0건.** 계산 노드는 외부 DNS가 막혀 있으므로 로그인 노드 선다운로드가 Stage 1의 선행 작업이다.
9. **하네스 SDK(`openai-agents`/`claude-code-sdk`/`google-adk`/`google-genai`)의 3.12 호환** — 우리 러너가 쓰지 않아 검사하지 않았다.
10. **`gpt-5.4-2026-03-05`(원 판정기)의 현재 서빙 여부** — 미조회.
