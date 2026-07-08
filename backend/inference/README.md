# Inference

Local model-serving component for the Raven AI Stylist. Wraps a quantised GGUF
build of the fine-tuned `gpt-oss-20b` Mixture-of-Experts model behind an
OpenAI-compatible HTTP API, served on Mac via `llama.cpp`'s `llama-server`
with full Metal offload.

Callers reach the service through the `/v1/chat/completions` endpoint. A
thin client factory `raven.inference_client.make_client()` is provided as
a convenience for env-var-driven local/remote selection — what callers
send in the `messages` array is not this component's concern.

## Architecture

```
caller
   │  HTTP (OpenAI-compatible)
   ▼
llama-server  ──  Metal (GPU)
   │
   ▼
model-q4_k_m.gguf
```

The component itself is just a thin wrapper. Heavy lifting lives in:

- **`scripts/merge_model.py`** — merges the LoRA adapter into the BF16 base and
  exports a quantised GGUF (one-time build step).
- **`scripts/serve_model.py`** — starts/stops `llama-server`, tracks the PID for
  programmatic lifecycle control.

## Prerequisites

- Python 3.12 (`.python-version` pins this)
- `uv` (or `pip`) for dependency install
- `llama.cpp` checkout with `convert_hf_to_gguf.py`, `llama-quantize`, and
  `llama-server` built. Setup steps and the expected `LLAMA_CPP_DIR` env var
  are in [`docs/llama-cpp-setup.md`](../../docs/llama-cpp-setup.md).
- `cmake` (for building llama.cpp; `brew install cmake`).
- ~64 GB unified memory (for the merge step; serving the q4_k_m artefact only
  needs ~16 GB).
- ~60 GB free disk (40 GB BF16 download + 15 GB final GGUF).

## Setup

### 1. Build the model artefact (one-time)

Merges the LoRA adapter at `models/sigmoi/adapters/` into the BF16 base, then
quantises to `q4_k_m`:

```sh
python scripts/merge_model.py \
    --base unsloth/gpt-oss-20b-BF16 \
    --adapters models/sigmoi/adapters \
    --output  models/sigmoi/stylist_gguf \
    --method gguf \
    --quantization q4_k_m
```

First run downloads the BF16 base (~40 GB) into `~/.cache/huggingface/`.
Subsequent runs reuse the cache. Total wall-time on first run: ~30–90 min
depending on bandwidth. The merge step itself is ~10–20 min once weights are
local.

Output: `models/sigmoi/stylist_gguf/model-q4_k_m.gguf` (~15 GB, 6.04 BPW).

### 2. Start the server

```sh
python scripts/serve_model.py \
    --model models/sigmoi/stylist_gguf/model-q4_k_m.gguf \
    --ctx-size 8192 \
    -- --jinja
```

Defaults:

| Flag | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Loopback only |
| `--port` | `8080` | Also identifies the PID file |
| `--ctx-size` | `4096` | Context window |
| `--ngl` | `999` | Layers offloaded to Metal (all) |

Anything after `--` is passed straight to `llama-server`. Useful flags:

- `--jinja` — use the model's chat template (recommended)
- `-fa` — flash attention
- `--mlock` — pin model in RAM, prevent swap
- `--api-key <token>` — require bearer auth
- `-sm none` — disable speculative decoding

When the server prints `>>> Server ready at http://127.0.0.1:8080`, it's
accepting requests.

### 3. Stop the server

Three options:

```sh
# CLI flag (works from anywhere; idempotent)
python scripts/serve_model.py --stop --port 8080

# Programmatically (Python)
import sys
sys.path.insert(0, "scripts")
from serve_model import stop_server
stop_server(port=8080)

# Manual (if PID file is missing or you didn't start via this script)
pkill -f llama-server
```

`--stop` reads `/tmp/raven-llama-server-<port>.pid`, sends `SIGTERM`, waits up
to 5 s, then `SIGKILL` if needed. Idempotent: stopping when nothing is
running exits 0.

## Calling the server

The server speaks the OpenAI Chat Completions schema. Examples below show
the wire format only — they are illustrative and not a recommended prompt
shape. Callers decide what to put in `messages`.

### curl

```sh
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "ping"}],
    "max_tokens": 16
  }'
```

### Python (`raven.inference_client`)

`raven.inference_client.make_client()` is a convenience factory that reads
env vars so the same code works against the local server (default) or any
remote OpenAI-compatible endpoint. Direct `OpenAI(...)` construction works
too — the factory is just a shortcut for the env-var switch.

```python
from raven.inference_client import make_client

client, model = make_client()
resp = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "ping"}],
)
```

Streaming: pass `stream=True` to `chat.completions.create` and iterate over
the response.

### Selecting local vs remote (env vars)

| Variable | Default | Notes |
|---|---|---|
| `RAVEN_INFERENCE_URL` | `http://127.0.0.1:8080/v1` | Base URL incl. `/v1`. Point at any OpenAI-compatible endpoint. |
| `RAVEN_INFERENCE_API_KEY` | `not-needed` | Bearer token. Local llama-server ignores it. |
| `RAVEN_INFERENCE_MODEL` | `raven-stylist` | Label passed in `model` field. Ignored by llama-server (single-model). |

Local (default — no env vars needed):
```sh
python -c "from raven.inference_client import make_client; print(make_client()[0].base_url)"
# → http://127.0.0.1:8080/v1/
```

Remote (e.g. vast.ai):
```sh
export RAVEN_INFERENCE_URL=https://your-host.example.com/v1
export RAVEN_INFERENCE_API_KEY=sk-your-token
# agent code unchanged
```

## Endpoints

| Path | Purpose |
|---|---|
| `POST /v1/chat/completions` | OpenAI chat (uses chat template) |
| `POST /v1/completions` | OpenAI raw text completion |
| `POST /completion` | llama.cpp-native completion (more knobs) |
| `POST /tokenize` / `/detokenize` | Tokeniser access |
| `GET /props` | Model metadata, ctx size, chat template |
| `GET /health` | Liveness check |
| `GET /` | Built-in chat UI for interactive testing |

## Troubleshooting

**`ModuleNotFoundError: No module named 'raven'`**
Install the project editable: `uv pip install -e .` from the repo root. The
package is `raven` (mapped from `src/raven` in `pyproject.toml`).

**Server starts but `/health` never responds**
First-run model load can take 30–60 s on Mac as Metal compiles shaders.
Tail the log: `tail -f /private/tmp/.../tasks/<task-id>.output`.

**`llama-server not found`**
`LLAMA_CPP_DIR` isn't set or the `llama-server` target wasn't built.
See [`docs/llama-cpp-setup.md`](../../docs/llama-cpp-setup.md). The
serve script can also fall back to `brew install llama.cpp` (binary on PATH).

**Merge fails with `KeyError: 'base_model.model.model.model.layers.X.input_layernorm'`**
Caused by `device_map="auto"` disk-offloading layers on Mac for 20B+ models,
which breaks PEFT adapter attach. The gguf path in `merge_model.py` already
loads on CPU to avoid this; if you change it, keep `device_map={"": "cpu"}`.

**`145 of 459 tensor(s) required fallback quantization`**
Benign. k-quants have minimum row-size requirements; small tensors (norms,
biases, attention sinks) fall back to `q5_0` / `q8_0` / `f32`. Standard for
any q4_k_m export.

## File layout

```
backend/inference/
├── README.md           # This file
├── CLAUDE.md           # Notes for AI agents working on this component
└── model/              # (Reserved; current artefact lives at models/sigmoi/stylist_gguf/)
```

The actual on-disk model artefact lives at the repo root under
`models/sigmoi/stylist_gguf/model-q4_k_m.gguf`. The server scripts live at
`scripts/{merge_model,serve_model}.py`.
