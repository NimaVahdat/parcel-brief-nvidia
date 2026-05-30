# Local LLM — DGX Spark

The open-model layer (parse free text → structured fields, phrase levers, draft opposition letters) is served by a **local LLM on a DGX Spark (NVIDIA GB10)**. Everything runs locally; no external API is called, per the project's unit economics.

`vote_predictor.predict()` uses it as the per-councillor **Reasoner** in the grounded multi-agent panel (degrading to a deterministic fallback when the endpoint is unreachable), and the eval harness exercises it in its LLM and no-grounding-ablation arms — see `vote-predictor/src/vote_predictor/{llm_wrapper,panel}.py`. The free-text I/O boundary (parsing application text, phrasing levers, drafting opposition letters) uses the same endpoint.

## What's serving

| | |
|---|---|
| **Model** | `nemotron-3-super:latest` — NVIDIA Nemotron-H hybrid Mamba-Transformer **MoE**, 123.6B params, Q4_K_M (~86GB), 256K context |
| **Server** | Ollama, OpenAI-compatible API |
| **Endpoint** | `http://<spark-host>:11434/v1` (tailnet-private; the real host is in `.env`) |
| **Throughput** | ~19 tok/s warm. Cold start loads 86GB into memory (~70s on first call). |

**Why Nemotron-H here, not a dense model.** The GB10's bottleneck is memory bandwidth (273 GB/s), not capacity (128GB unified) or compute. Two architectural traits attack that directly: **MoE** activates only a fraction of the 123B params per token (far fewer bytes/token than a dense model), and the **Mamba/SSM layers** replace most quadratic attention, shrinking the KV cache. The result is 123B-class quality that generates *faster* than a dense 32B would. A dense `Qwen3-32B-FP8` was benchmarked at ~8 tok/s on the same box.

## Pointing the project at it

Set these in `.env` (copy from `.env.example`, gitignored):

```bash
LLM_BASE_URL=http://<spark-host>:11434/v1
LLM_API_KEY=local                      # unused by Ollama; any value
LLM_MODEL=nemotron-3-super:latest
```

The wrapper uses the OpenAI client:

```python
from openai import OpenAI
client = OpenAI(base_url=LLM_BASE_URL, api_key="local")
resp = client.chat.completions.create(
    model="nemotron-3-super:latest",
    messages=[{"role": "user", "content": "..."}],
    temperature=0,
)
```

If you run the components **on the box**, use `http://localhost:11434/v1` and no network exposure is needed.

## Gotcha: it's a reasoning model

Chain-of-thought is returned in a separate **`reasoning`** field; the actual answer is in **`message.content`**. If `max_tokens` is too small, thinking consumes the whole budget and `content` comes back **empty** with `finish_reason: "length"`. Give it room (the wrapper sets no cap, which is correct), or strip thinking if the model/endpoint supports it. For JSON tasks the `content` holds clean, fence-free JSON once thinking completes — `json.loads()` parses it directly.

## Smoke test

```bash
curl -s http://<spark-host>:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nemotron-3-super:latest",
       "messages":[{"role":"user","content":"Extract as JSON keys height_m,total_units: A 45m tower, 200 units."}],
       "max_tokens":600,"temperature":0}'
# -> content: {"height_m": 45, "total_units": 200}
```

## Operational notes

- **Access over Tailscale.** Ollama defaults to `127.0.0.1`. To reach it from another tailnet device, it's bound to `0.0.0.0` via a systemd override on the box:
  `/etc/systemd/system/ollama.service.d/override.conf` → `Environment="OLLAMA_HOST=0.0.0.0:11434"`, then `systemctl daemon-reload && systemctl restart ollama`. The tailnet is private; the port is not exposed to the public internet.
- **`nvidia-smi` shows memory as `N/A` / `Not Supported`** on the unified-memory GB10. That's expected, not a fault — use `free -h` to see memory pressure.
- **Other models already on the box** (Ollama): `qwen3.6:35b`, `nemotron3:33b` (multimodal), `gemma4:26b`, and `nomic-embed-text` (a local embedding endpoint, alternative to the `all-mpnet-base-v2` sentence-transformer in `EMBEDDING_MODEL`).

## vLLM fallback (schema-guided JSON)

Ollama's JSON enforcement is `format=json` only. If a component needs strict **JSON-schema guided decoding** or a non-Ollama checkpoint, the box is prepped for vLLM: the `asus` user is in the `docker` group and the NVIDIA Docker runtime is registered, and the GB10-compatible CUDA-13 image `vllm/vllm-openai:cu130-nightly` is already pulled. Example (serves an FP8 model on `:8080`, the port `.env.example` originally assumed):

```bash
docker run -d --name vllm --restart unless-stopped --gpus all --ipc host --shm-size 32gb \
  -p 8080:8080 -v ~/.cache/huggingface:/root/.cache/huggingface \
  -e HF_HUB_ENABLE_HF_TRANSFER=1 \
  vllm/vllm-openai:cu130-nightly Qwen/Qwen3-32B-FP8 \
  --served-model-name qwen3-32b --port 8080 --host 0.0.0.0 \
  --gpu-memory-utilization 0.85 --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser hermes --enable-prefix-caching
```

Don't run vLLM and a large Ollama model at once — vLLM's `--gpu-memory-utilization 0.85` reserves most of the unified memory and will starve the other.

## Reproducing the box setup

One-time privileged steps already applied (require `sudo`; the box's `sudo` is not passwordless):

```bash
# Docker GPU access for the serving user
sudo usermod -aG docker asus
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Expose Ollama on the tailnet
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

## Current setup: nemotron-3-super on vLLM (NVFP4) — generation moved off Ollama

Generation (vote Reasoner + opposition HyDE/letters) now runs on **vLLM** serving the
NVFP4 build of nemotron-3-super, which **batches concurrent requests** (Ollama refuses to,
for this `nemotron_h_moe` arch). vLLM owns the GPU, so **Ollama's nemotron is no longer
loadable** — Ollama is kept only for `nomic-embed-text` embeddings.

**The server** (persistent Docker, port `:8001`):

```bash
docker run -d --name vllm-nemotron --restart unless-stopped --gpus all --ipc host --shm-size 16gb \
  -e VLLM_NVFP4_GEMM_BACKEND=marlin -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
  -e VLLM_USE_FLASHINFER_MOE_FP4=0 -e HF_HUB_OFFLINE=1 \
  -v /home/asus/hfcache:/root/.cache/huggingface \
  -v /home/asus/super_v3_reasoning_parser.py:/app/super_v3_reasoning_parser.py \
  -p 8001:8001 vllm/vllm-openai:cu130-nightly \
    --model unsloth/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 --served-model-name nemotron-3-super \
    --host 0.0.0.0 --port 8001 --quantization fp4 --kv-cache-dtype fp8 \
    --tensor-parallel-size 1 --trust-remote-code --gpu-memory-utilization 0.80 \
    --max-model-len 32768 --max-num-seqs 4 --moe-backend marlin --mamba_ssm_cache_dtype float32 \
    --enable-chunked-prefill \
    --reasoning-parser-plugin /app/super_v3_reasoning_parser.py --reasoning-parser super_v3
```

(Weights are the **ungated** `unsloth/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` mirror,
cached at `~/hfcache`; `gpu-memory-utilization 0.80` keeps it within the GB10's 128 GB.)

**Point the connector at it** — set these env vars (or just run the helper script), then launch:

```bash
export VOTE_PREDICTOR_LLM_URL=http://localhost:8001/v1   # over Tailscale: http://<box>:8001/v1
export VOTE_PREDICTOR_LLM_MODEL=nemotron-3-super
export OPP_LLM_BASE_URL=http://localhost:8001/v1
export OPP_LLM_MODEL=nemotron-3-super
export MASSING_USE_MOCK=1
uvicorn connector.api.main:app --host 0.0.0.0 --port 8000
# or: bash scripts/run_connector_vllm.sh
```

**Reasoning toggle.** nemotron's chain-of-thought is controlled by the `enable_thinking`
chat-template kwarg. Opposition sends `chat_template_kwargs={"enable_thinking": false}` for
HyDE (text is discarded after embedding) and letter generation (speed > marginal gain); the
vote Reasoner keeps it on. Pass `reasoning=False` to `opposition_generator.llm.chat[_json]`.
