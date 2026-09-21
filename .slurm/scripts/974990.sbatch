#!/bin/bash
# vLLM 서빙 잡 (standing-delegation-v2). `Plan.md` §2 어댑터(OpenAI 호환) · §3 모델.
# 원형은 ../underspec/scripts/vllm_serve.sbatch (실측 검증값)이고, 여기서 바뀐 것은
# (1) 모델 키 두 개(D-007 파일럿 로컬 2), (2) 툴 호출 파서 플래그(러너 M1에 필수), (3) 파티션 기본값.
#
# 사용:
#   sbatch --job-name=vllm-qwen38 scripts/vllm_serve.sbatch qwen3.8-27B-FP8
#   sbatch --job-name=vllm-glm47  scripts/vllm_serve.sbatch glm-4.7-flash
# 인자: $1 모델 키, $2 max-model-len(기본 131072), $3 TP(기본 1)
# 엔드포인트는 헬스체크 통과 뒤 runs/serve/<model_key>.endpoint 에 http://HOST:PORT/v1 로 쓴다.
#
#SBATCH --partition=A100-80GB
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --time=1-00:00:00
#SBATCH --output=slurm_logs/%x-%j.out
#SBATCH --error=slurm_logs/%x-%j.err

MODEL_KEY="${1:?모델 키 (qwen3.8-27B-FP8 | glm-4.7-flash | qwen3.6-27B | gemma-4-26B-A4B-it)}"

# errexit 은 소싱 **뒤에** (앞에 두면 ExitCode 11 즉사, slurm-assistant 스킬).
source ~/slurm_common.sh
set -eo pipefail

# vLLM 0.26.0 은 이 프로젝트 venv 가 아니라 검증된 서빙 venv 에 있다 (docs/FEASIBILITY.md §2).
source /home3/b.ms/projects/multiturn-reliability-env/.venv/bin/activate

# 계산 노드는 외부 DNS 가 없다. 가중치는 로그인 노드에서 미리 받았다.
export HF_HUB_OFFLINE=1

DTYPE=bfloat16
REASONING_PARSER=""
TOOL_PARSER=""
MAX_SEQS_DEFAULT=256
case "$MODEL_KEY" in
    # docs/FEASIBILITY.md §1.2·§1.4·§7.1. FP8 체크포인트라 dtype auto. Hopper 에서 DeepGEMM NVCC JIT
    # 사망 회피(잡 719119) → CUTLASS 폴백. hybrid(linear attention) 라 48GB 카드에서는 MAX_SEQS 96 이하.
    qwen3.8-27B-FP8)  REPO_ID="Qwen/Qwen3.8-27B-FP8"; DTYPE=auto
                      REASONING_PARSER=qwen3; TOOL_PARSER=qwen3_xml
                      export VLLM_USE_DEEP_GEMM=0 ;;
    # 모델 카드의 vllm serve 명령 그대로 (docs/FEASIBILITY.md §1.2): glm47 / glm45.
    glm-4.7-flash)    REPO_ID="zai-org/GLM-4.7-Flash"
                      REASONING_PARSER=glm45; TOOL_PARSER=glm47 ;;
    # 생성기 v1 의 LLM (평가 대상 밖, D-036). 평가 대상 Qwen3.8 의 이전 판. 이전 프로젝트에서 reasoning parser qwen3 로 서빙 실적.
    qwen3.6-27B)        REPO_ID="Qwen/Qwen3.6-27B"; REASONING_PARSER=qwen3; TOOL_PARSER=qwen3_xml ;;
    gemma-4-26B-A4B-it) REPO_ID="google/gemma-4-26B-A4B-it" ;;
    *) echo "[FATAL] unknown model key: $MODEL_KEY" >&2; exit 1 ;;
esac
TP="${3:-1}"
MAX_LEN="${2:-131072}"
GPU_UTIL=0.90
SEED=20260729

PORT=$(( 8000 + SLURM_JOB_ID % 1000 ))
HOST=$(hostname -s)
ENDPOINT_DIR="runs/serve"
mkdir -p "$ENDPOINT_DIR"
ENDPOINT_FILE="${ENDPOINT_DIR}/${MODEL_KEY}.endpoint"

echo "model=${REPO_ID} key=${MODEL_KEY} tp=${TP} host=${HOST} port=${PORT} max_len=${MAX_LEN} max_seqs=${MAX_SEQS:-$MAX_SEQS_DEFAULT}"
python -c "import vllm; print('vllm', vllm.__version__)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

cleanup() {
    if [ -f "$ENDPOINT_FILE" ] && [ "$(cat "$ENDPOINT_FILE")" = "http://${HOST}:${PORT}/v1" ]; then
        rm -f "$ENDPOINT_FILE"
    fi
}
trap cleanup EXIT

python -m vllm.entrypoints.openai.api_server \
    --model "$REPO_ID" \
    --served-model-name "$MODEL_KEY" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --tensor-parallel-size "$TP" \
    --dtype "$DTYPE" \
    --max-model-len "$MAX_LEN" \
    --max-num-seqs "${MAX_SEQS:-$MAX_SEQS_DEFAULT}" \
    --gpu-memory-utilization "$GPU_UTIL" \
    --seed "$SEED" \
    ${REASONING_PARSER:+--reasoning-parser "$REASONING_PARSER"} \
    ${TOOL_PARSER:+--enable-auto-tool-choice --tool-call-parser "$TOOL_PARSER"} \
    --no-enable-log-requests &
SERVER_PID=$!

# 헬스 체크 통과 뒤에만 엔드포인트 공개. 적재 대기 기본 60분(360×10s). 공유 홈이 붐비면 더 걸린다.
for _ in $(seq 1 "${SERVE_WAIT_TICKS:-360}"); do
    if curl -sf "http://${HOST}:${PORT}/v1/models" > /dev/null; then
        echo "http://${HOST}:${PORT}/v1" > "$ENDPOINT_FILE"
        echo "endpoint published: $(cat "$ENDPOINT_FILE")"
        break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[FATAL] vLLM 서버가 적재 중 죽었다. stderr 로그를 볼 것." >&2
        exit 1
    fi
    sleep 10
done

if [ ! -f "$ENDPOINT_FILE" ]; then
    echo "[FATAL] $(( ${SERVE_WAIT_TICKS:-360} / 6 ))분 안에 서버가 준비되지 않았다." >&2
    kill "$SERVER_PID" 2>/dev/null || true
    exit 1
fi

wait "$SERVER_PID"
