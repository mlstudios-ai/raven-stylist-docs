# Inference — agent notes

This component serves the fine-tuned MoE stylist model behind an
OpenAI-compatible HTTP API. Wraps `llama.cpp`'s `llama-server` on Mac with
full Metal offload. See [`README.md`](./README.md) for full usage.

## Where things live

| What | Path |
|---|---|
| OpenAI client factory (env-var local/remote) | `src/raven/inference_client.py` |
| Build script (LoRA → GGUF) | `scripts/merge_model.py` (repo root) |
| Serve script (lifecycle) | `scripts/serve_model.py` (repo root) |
| Model artefact | `models/sigmoi/stylist_gguf/model-q4_k_m.gguf` |
| LoRA adapter source | `models/sigmoi/adapters/` |
| llama.cpp checkout | `~/Developer/llama.cpp` (env: `LLAMA_CPP_DIR`) |
| llama.cpp setup doc | [`../../docs/llama-cpp-setup.md`](../../docs/llama-cpp-setup.md) |
| PID file (running server) | `/tmp/raven-llama-server-<port>.pid` |

The empty `model/` subdir here is reserved — current artefacts live under
`models/sigmoi/` at the repo root. Don't move them without updating the
serve/merge invocations.

## Non-obvious things

- **Editable install required.** Run `uv pip install -e .` from the repo root
  before running anything; `pyproject.toml` is now correctly mapped
  (`packages = ["src/raven"]`), but the install must happen explicitly.
- **Client factory.** `raven.inference_client.make_client()` returns a
  configured OpenAI-compatible client; the env vars decide local vs remote.
  How callers shape their `messages=[...]` is entirely their concern — this
  component takes no position on prompts.
- **Merge base must be BF16, not bnb-4bit.** The LoRA was trained on
  `unsloth/gpt-oss-20b-unsloth-bnb-4bit` but bnb-4bit weights don't round-trip
  cleanly through `convert_hf_to_gguf.py`. Use `unsloth/gpt-oss-20b-BF16`. The
  LoRA deltas are precision-agnostic — they apply to either base.
- **Merge path forces CPU.** `_merge_gguf` in `merge_model.py` passes
  `device_map={"": "cpu"}` because `device_map="auto"` triggers disk-offload
  on Mac for 20B+ models, which breaks PEFT adapter attach with
  meta-tensor / offload `KeyError`. Don't revert.
- **bf16 not fp16 on the merge path.** The original script used `torch.float16`
  for gguf; we use `torch.bfloat16` to match the source weights exactly and
  avoid silent ~3-bit exponent loss before quantisation.
- **`device_map` is plumbed as a parameter** through `_load_base(...)` so the
  16bit / 4bit paths still default to `"auto"`. Only the gguf path overrides.
- **Stop semantics** — `serve_model.py --stop` is idempotent; the function
  `stop_server(port, timeout)` returns `True` only if a live process was
  signalled. Stale PID files are auto-cleaned.

## Common tasks

- **Rebuild the GGUF after retraining the LoRA**: re-run `merge_model.py`
  with the new adapters dir; output overwrites in place.
- **Try a different quantisation**: `--quantization q5_k_m` (better quality,
  ~18 GB), `q8_0` (~22 GB, near-lossless), `f16` (~40 GB, no llama-quantize
  step).
- **Multiple instances**: each `--port` gets its own PID file, so two
  concurrent servers on different ports work and `--stop --port N` only
  touches the matching one.
- **Switch Mac → CUDA host**: `--method 4bit` path uses bnb + `device_map=auto`
  and is fine on CUDA. The gguf path also works on CUDA without changes.

## Out of scope for this component

- Prompt construction, templates, schemas, or any opinion on how callers
  shape their requests
- Agent orchestration / when to call which agent → `backend/stylist`
- Style recommendation logic → `backend/style`
- VTO image generation → `backend/vto`
- Hosting / deployment (AWS Lambda, etc.) → `terraform/`

This component owns only: model artefact lifecycle and the local HTTP
serving boundary (the `make_client()` factory). Anything above the wire —
prompts, agents, orchestration — lives elsewhere.
