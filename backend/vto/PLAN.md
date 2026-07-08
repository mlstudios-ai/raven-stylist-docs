# VTO Agent — Build Plan

> Three-doc convention: **CLAUDE.md** = what it is. **README.md** =
> developer guide. **PLAN.md** = the recipe a coding agent would use to
> rebuild this from scratch.

## Status

✅ Built and verified end-to-end against the local fine-tuned model **and**
real Gemini Flash Image. Smoke test passes; produces a coherent
photoreal try-on with the user's face from headshot.

## Materials needed

| Item | Where it lives | Purpose |
|---|---|---|
| Sigmoi system prompt + output schema | `template.py` :: `VTO_SYSTEM_PROMPT` | `<\|SIGMOI_VTO\|>` task tag + embedded JSON schema for `{scene, outfit, prompt}`. |
| User-prompt template | `template.py` :: `VTO_USER_PROMPT_TEMPLATE` | Slots for user prompt + style.context.occasion + style.intent.primary_intent + style.recommendations[0]. |
| `build_pieces` helper | `template.py` | Formats pieces list into the YAML-ish body. Uses **dict access**. |
| Reference filled prompt | `example_prompt.txt` | Training-distribution anchor for the input. |
| Reference output | `example_response` | Anchors response schema (model emits `{scene, outfit, prompt}`). |
| Style agent output | Comes in via `request.style` | Provides `intent.primary_intent`, `context.occasion`, `recommendations[0].{label, logic_summary, pieces}`. The `outfit` field on the *VTO* output is ignored at runtime; the authoritative outfit data is here. |
| User headshot | `backend/api/profiles/{user_id}/photos/headshot.png` | Face reference for Gemini. Headshot only — no body photos (would bleed existing outfit). |
| Sigmoi (local llama-server) | `scripts/serve_model.py` running on `127.0.0.1:8080` | Generates personalised Gemini prompt. |
| Gemini Flash Image | `gemini-3.1-flash-image-preview` via `google-genai` SDK | Renders the actual image. |
| API key | `GEMINI_API_KEY` in `.env` (loaded via `python-dotenv`) | |
| Photo-generation reference | `scripts/generate_profile_photos.py` | Demonstrates the `[prompt, headshot]` calling pattern; shows `image_size="1K"` config. |

## Build tasks

| # | Task | Status |
|---|---|---|
| 1 | Add `google-genai` + `pillow` to `requirements.txt`; `uv add -r requirements.txt` | ✅ |
| 2 | Fix `build_pieces` to dict access | ✅ |
| 3 | `agent.py` skeleton — `run(user_id, request) → dict` with DI seams (`headshot_loader`, `sigmoi_factory`, `gemini_caller`) | ✅ |
| 4 | Operational directives appended to `VTO_SYSTEM_PROMPT` at runtime: only-on-explicit-request + occasion-clarification rule (returns `{"clarifying_question": "..."}`) | ✅ |
| 5 | `_build_sigmoi_user_prompt` from `request.prompt` + `request.style.recommendations[0]` | ✅ |
| 6 | Sigmoi call (temp=0.2, `response_format={"type":"json_object"}`); parse with `raw_decode`; detect `clarifying_question` and raise `VtoClarificationRequired` | ✅ |
| 7 | `call_gemini` — concatenate `prompt.system` + `prompt.user`, pass `[prompt, PIL_headshot]` to `client.models.generate_content` with `response_modalities=["IMAGE"]`. Pull bytes via `part.as_image().image_bytes` (not PIL save). Return `(bytes, mime_type)`. | ✅ |
| 8 | `_compose_description` — mechanical `". ".join(occasion, setting, time_of_day, mood)` blurb. Orchestrator may rewrite for chat voice. | ✅ |
| 9 | `_save_debug` — write `{turn_id}.{ext}` (mime-aware) + `{turn_id}.meta.json` reproduction kit (input request, Sigmoi prompts in/out, Gemini prompts sent, headshot path) | ✅ |
| 10 | `smoke_test.py` — chains style → VTO end-to-end with `TestClient` for headshot, real Sigmoi + real Gemini. Validates JPEG/PNG magic, `image_mime`, debug bundle written. | ✅ |

## Key decisions

- **Two-stage flow.** Sigmoi (text-only fine-tune) generates the
  Gemini prompt. Gemini renders. The fine-tune does the personalisation
  work; the third party does the rendering work — same boundary the
  project root CLAUDE.md describes.
- **Headshot-only reference.** Matches the photo-generation script. Adding
  a body photo as a second reference risks bleeding the existing outfit.
- **`outfit` field ignored at runtime.** Authoritative data is on
  `request.style`. The schema field is reserved for a future
  product-search phase when descriptive pieces are matched to real
  inventory.
- **Image transport via base64**, not filesystem path. Future-proofs the
  contract for cross-process Lambda boundaries.
- **JPEG accepted** — Gemini's default. Smaller payload than PNG, fine
  for chat. Contract carries `image_mime` so consumers know the format.
- **Operational directives layered, not edited into the schema.** The
  base `VTO_SYSTEM_PROMPT` stays training-distribution-faithful; the
  routing rules (only-on-explicit-request, occasion-clarification) are
  appended in agent code so the schema-fluency doesn't drift.
- **Debug bundle = full reproduction kit.** Every saved turn captures
  enough to replay end-to-end (input request + Sigmoi prompts both
  directions + Gemini config). Useful when iterating on prompts.

## Smoke test definition

```sh
# Prerequisites:
#   - inference server up at 127.0.0.1:8080
#   - GEMINI_API_KEY in .env (or env)
python -m backend.vto.smoke_test
```

Asserts:
- Style agent produced a recommendation for Jamie.
- VTO Sigmoi call returned valid JSON.
- Gemini returned image bytes (JPEG or PNG magic).
- `image_mime` is `image/jpeg` or `image/png`.
- Debug image written under `backend/vto/output/smoke/`, ≥1 KB.
- `sigmoi_response` contains `scene`, `outfit`, `prompt`.

## Known gaps / future work

- **No clarifying turn yet exercised in smoke.** The smoke uses a clean
  request where occasion is implied by context; the
  `VtoClarificationRequired` path isn't hit. Should add a smoke variant.
- **No retry/backoff on Gemini.** Single attempt; raises on failure.
  Acceptable for demo. Worth adding when this becomes a Lambda.
- **No content-safety handling.** If Gemini rejects the prompt for
  safety reasons, we surface as `VtoAgentError`. Could be smoother.

## Out of scope (deferred to other components)

- Session state, intent routing → orchestrator (`backend/stylist`).
- Episode persistence (`vto.json` + `vto.png` write) → orchestrator.
- Conversation logging → orchestrator.
- Frontend rendering of the image → frontend (orchestrator passes
  `image_b64` through).
- Product matching → later phase, will populate the `outfit` field.
