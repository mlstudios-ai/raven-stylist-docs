# VTO Agent

Stateless sub-agent that returns a virtual try-on image plus structured
scene metadata for a user style ask. Invoked as a tool by the stylist
orchestrator **only when the user explicitly requests a visualisation**.
Local for the demo; deploys as a Lambda later with no surface change.

The point of this agent in the demo is to visualise the style fine-tune in
action — it is not the headline feature. The fine-tune is.

## When this runs

Triggered only by explicit user intent — phrases like *"show me"*, *"try
it on"*, *"how does it look"*, *"see it on me"*. The orchestrator decides
routing; this agent does not introspect intent and never runs alongside
every style turn. The system prompt reinforces this so the model also
declines to render unprompted.

## Contract

```python
def run(user_id: str, request: dict) -> dict
```

Inputs:

| Field | Type | Source | Notes |
|---|---|---|---|
| `user_id` | str | Orchestrator | Resolved from session before call. |
| `request.prompt` | str | Orchestrator | The user's most recent message — the one that triggered this VTO ask. Lifted from the last entry of the active chat history. Becomes part of `prompt.user` that Sigmoi composes for Gemini. |
| `request.style` | dict | Orchestrator | The full output of the style agent for this turn. Provides intent, context, and the recommendation pieces that drive what Gemini renders. |
| `request.conversation` | list | Orchestrator | Optional, last ~3 turns. Not required (style already ingested it); pass only if needed to disambiguate occasion. |

Output:

```python
{
    "image_b64": str,         # base64-encoded image bytes — transport-safe
    "image_mime": str,        # "image/jpeg" | "image/png" — Gemini typically returns JPEG
    "description": str,       # mechanical blend of scene fields; orchestrator may rewrite
    "scene": dict,            # raw scene block from Sigmoi (occasion, setting, lighting, time_of_day, mood)
    "sigmoi_response": dict,  # full Sigmoi JSON for the orchestrator to persist as vto.json
}
```

`image_b64` is base64 rather than a filesystem path so the contract works
identically when VTO is in-process (demo) and when it's a separate
Lambda. The orchestrator decodes and forwards bytes to the frontend
canvas; it never needs filesystem access to this module's output.

The orchestrator owns the chat-facing message synthesis. The
`description` returned here is a deterministic concatenation of `scene`
fields meant as input to that synthesis, not as final user-facing copy.

`sigmoi_response` is included so the orchestrator can write a complete
`vto.json` to the user's episode store atomically with `request.json`
and `style.json` (see *Episode persistence* below). VTO does not write
this file itself.

Raises:
- `VtoAgentError` — Gemini call failed or returned no image, or Sigmoi
  produced invalid JSON.
- `VtoClarificationRequired(question: str)` — Sigmoi flagged occasion as
  unclear; orchestrator surfaces the question to the user instead of
  attempting to render.

## Two-stage flow

```
request → Sigmoi (fine-tuned model) → {scene, outfit, prompt}
       → fetch_identity (backend/api)
       → Gemini Flash Image
            + headshot reference
            + identity-anchor sentence prepended to prompt.user
       → PNG + metadata
```

1. Sigmoi takes `request.prompt` + `request.style`, fills
   `VTO_USER_PROMPT_TEMPLATE` from `template.py`, returns structured JSON
   matching the schema in `VTO_SYSTEM_PROMPT`.
2. `fetch_identity(user_id)` calls
   `GET /users/{user_id}?attributes=identity,body` for `gender_identity`,
   `age`, `body_shape`. Falls back to a generic
   `("person", "adult", "average")` if the call fails.
3. Agent code prepends an **identity-anchor sentence** to `prompt.user`
   using the fetched gender (*"Render exactly ONE person — the same
   {gender_identity} shown in the reference photo. Do not change gender,
   do not generate multiple people, preserve face and body proportions
   from the headshot."*) and calls Gemini with
   `[final_prompt, headshot_image]`.
4. Image is saved to disk; structured payload returned.

## Identity enforcement (Gemini-only)

Gemini Flash will sometimes invent a different person — wrong gender,
multiple subjects, or a generic model — when the prompt is style-heavy
and the headshot signal is weak.

Enforcement happens **only at the Gemini stage**: the identity-anchor
sentence is concatenated onto `prompt.user` after Sigmoi runs, right
before `client.models.generate_content`. Sigmoi itself is **not** fed
identity fields — that just pays generation tokens to produce text we'd
overwrite anyway, and adds latency without changing the rendered image.

The earlier approach (identity slots in the Sigmoi user prompt + IDENTITY
RULES in the Sigmoi system prompt) was reverted for that reason. Sigmoi
exists to write a Gemini-friendly prompt; identity is render-time
metadata for Gemini.

## The `outfit` field is ignored at runtime

The Sigmoi schema declares `outfit.pieces`. The model emits this because
it matches its training distribution. **The agent does not read it.**
Outfit detail is already carried in natural language inside `prompt.user`,
and the authoritative source is the style agent's recommendation passed
via `request.style`.

`outfit` is reserved for a later phase: once a product-search tool and
real inventory exist, the orchestrator will substitute matched products
for the descriptive piece list before VTO runs. Until then, ignore the
field rather than stripping it from the schema — the schema stays so the
model stays on-distribution.

## Reference image

Headshot only — `backend/api/profiles/{user_id}/photos/headshot.png`.

Matches `scripts/generate_profile_photos.py`, which used a headshot-only
reference to render the four outfit photos per profile with strong face
consistency. Adding a full-body photo as a second reference risks
bleeding the existing outfit through into the new render, defeating the
point.

## Gemini API

| | |
|---|---|
| Model | `gemini-3.1-flash-image-preview` (matches `scripts/generate_profile_photos.py`). |
| SDK | `google-genai` — `from google import genai`. |
| Auth | `GEMINI_API_KEY` loaded from `.env`. |
| Image config | `response_modalities=["IMAGE"]`, `image_size="1K"`. |

The reference image is passed as a PIL `Image` alongside the prompt
string in `contents=[prompt, headshot_image]` — same pattern as the
photo-generation script.

## Dependency management

`google-genai` is added in `requirements.txt`. Sync into the `uv` env via:

```sh
uv add -r requirements.txt
```

This keeps the package list source-of-truth in `requirements.txt` (so the
generation script and the VTO agent share the same dep) while still
managing the lockfile through `uv`.

## Episode persistence (not this agent's job)

The user's episode store at
`backend/api/profiles/{user_id}/episodes/{ep_id}/` holds the canonical
record of one user turn — `request.json` + `style.json` + `vto.json` +
`vto.png`. **This agent does not write any of those.** The orchestrator
does, atomically, after a turn completes.

Reasons:
- Episode IDs are allocated by the orchestrator (it knows turn boundaries).
- A single turn may involve only chat, only style, or style+VTO — only
  the orchestrator knows the full bundle.
- `request.json` is the orchestrator's session state, not VTO's.
- Writing `vto.json` alone produces fragmented half-episodes.

VTO returns `image_b64` and `sigmoi_response` and lets the orchestrator
decide whether and where to persist them.

## Local debug output

For developer inspection during the demo, VTO additionally writes a
**reproduction kit** for every turn under:

```
backend/vto/output/
  {session_id}/
    {turn_id}.{ext}           # rendered image — ext is mime-aware (jpg/png/webp)
    {turn_id}.meta.json       # full reproduction kit (see below)
```

`meta.json` shape:

```json
{
  "saved_at": <epoch>,
  "session_id", "turn_id", "user_id",
  "image":  {"filename", "mime_type", "bytes"},
  "input_request":  {"prompt", "style"},               // what came in
  "sigmoi": {"model", "user_prompt_sent", "response"}, // step 1 in/out
  "gemini": {"model", "image_size", "prompt_system_sent",
             "prompt_user_sent", "headshot_used"}      // step 2 inputs
}
```

This is enough to replay any turn end-to-end: re-call Sigmoi with
`sigmoi.user_prompt_sent`, re-call Gemini with `gemini.prompt_*_sent` +
the headshot path, compare to the saved image.

The bundle is **not** the canonical store and is not consumed by the
orchestrator. Safe to delete; the source of truth (once the orchestrator
lands) is the user's episode folder.

## Clarifying turn

Only **occasion** is treated as critical. Everything else (setting,
lighting, mood, time of day) the model can fill plausibly and Gemini can
render reasonably from sparse input.

The system prompt instructs Sigmoi to return a clarifying turn instead of
the full schema when occasion is unclear. The agent detects this and
raises `VtoClarificationRequired`; the orchestrator surfaces the
question to the user as chat copy.

## System-prompt additions

The base `VTO_SYSTEM_PROMPT` in `template.py` is extended at agent build
time with two operational directives:

1. *Only respond when the user has explicitly requested a virtual try-on
   or visualisation. The orchestrator routes — do not invent VTO
   requests.*
2. *If `occasion` is unclear or missing from the user prompt and the
   style context, return `{"clarifying_question": "..."}` instead of the
   full schema.*

These don't change the schema, only the conditions under which the model
chooses between schema-output and clarifying-turn.

## Files

| File | Purpose |
|---|---|
| `template.py` | `VTO_SYSTEM_PROMPT` (with embedded output schema) + `VTO_USER_PROMPT_TEMPLATE` + `build_pieces` helper. |
| `example_prompt.txt` | Reference: filled Sigmoi user prompt. |
| `example_response` | Reference: example Sigmoi structured output. |
| `agent.py` | Public `run()` entry point. To be built. |
| `smoke_test.py` | End-to-end with real Sigmoi + real Gemini. To be built. |
| `output/` | Generated images and metadata, by session. Not committed. |

## Out of scope

- Conversation history / logging → orchestrator (`backend/stylist`)
- Routing decisions (when to call VTO) → orchestrator
- Resolving session → user_id → orchestrator
- Profile storage → `backend/api`
- Rendering the image onto the canvas → frontend (after orchestrator
  forwards `image_path`)
- Product-to-piece matching → later phase, will populate `outfit`

## Reference

Sub-agent pattern mirrors `backend/style`. Photo-generation pattern (PIL
reference image, `google-genai` SDK, image config) mirrors
`scripts/generate_profile_photos.py`.
