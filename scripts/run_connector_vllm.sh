#!/usr/bin/env bash
# Launch the connector against the shared vLLM server (nemotron-3-super NVFP4 on :8001).
#
# vLLM owns the GPU on the GB10, so Ollama's nemotron is no longer loadable — all
# generation (vote Reasoner + opposition HyDE/letters) MUST go to vLLM. Embeddings
# still use Ollama's nomic-embed (OLLAMA_URL, default :11434).
#
# Usage (on the box):   bash scripts/run_connector_vllm.sh
# Over Tailscale:        VLLM_URL=http://<box-host>:8001/v1 bash scripts/run_connector_vllm.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VLLM_URL="${VLLM_URL:-http://localhost:8001/v1}"
export VOTE_PREDICTOR_LLM_URL="$VLLM_URL"
export VOTE_PREDICTOR_LLM_MODEL="${VLLM_MODEL:-nemotron-3-super}"
export OPP_LLM_BASE_URL="$VLLM_URL"
export OPP_LLM_MODEL="${VLLM_MODEL:-nemotron-3-super}"
export MASSING_USE_MOCK="${MASSING_USE_MOCK:-1}"

echo "connector -> vLLM at $VLLM_URL (model ${VLLM_MODEL:-nemotron-3-super})"
exec uvicorn connector.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
