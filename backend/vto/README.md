# VTO Agent

Stateless sub-agent in the Raven multi-agent system. Given a user's
explicit visualisation request and the style agent's recommendation,
returns a photoreal try-on image plus structured scene metadata.

Invoked by the stylist orchestrator (`backend/stylist`) only when the
user explicitly asks to see how an outfit looks. The agent does not run
alongside every style turn — orchestrator routes on intent.

## Two-stage pipeline

```
caller (orchestrator)
    │  user_id, request{prompt, style}
    ▼
VTO agent
    │
    ├── Sigmoi (fine-tuned model, via backend/inference)
    │       returns {scene, outfit, prompt}  ← outfit ignored at runtime
    │
    └── Gemini Flash Image (gemini-3.1-flash-image-preview)
            prompt.system + prompt.user, headshot reference
            returns image bytes
    ▼
{image_b64, description, scene, sigmoi_response}
```

## Public surface

```python
from backend.vto.agent import run

result = run(user_id="usr_006_jamie", request={
    "prompt": "yeah show me what that looks like",
    "style": {  # full output of backend/style.run()
        "intent": {...},
        "context": {...},
        "analysis": {...},
        "recommendations": [...],
    },
})
# result == {
#     "image_b64": "/9j/4AAQSkZJRg...",        # base64-encoded image bytes
#     "image_mime": "image/jpeg",              # mime — Gemini typically returns JPEG
#     "description": "<scene-derived blurb>",
#     "scene": {"occasion": ..., "setting": ..., "lighting": ..., "time_of_day": ..., "mood": ...},
#     "sigmoi_response": {...},                # full Sigmoi JSON for episode persistence
# }
```

The orchestrator decodes `image_b64` and forwards bytes to the frontend
(rendered on the left VTO canvas), synthesises a chat reply using
`description` and `scene` as input, and writes `sigmoi_response` to the
user's episode store as `vto.json` (atomically with `request.json` /
`style.json` for the same turn).

## Inputs

| Field | Source | Notes |
|---|---|---|
| `user_id` | Orchestrator | Resolved from session before call. |
| `request.prompt` | Orchestrator | The user's most recent message — the one that triggered this VTO ask. |
| `request.style` | Orchestrator | Full output dict from the style agent for this turn. |
| `request.conversation` | Orchestrator | Optional, last ~3 turns. Pass only if needed to disambiguate occasion. |
| Headshot | `backend/api` | `profiles/{user_id}/photos/headshot.png`, used as Gemini face reference. |

## Running

Smoke test (Jamie, hardcoded `request.style` and a "show me" prompt):

```sh
python -m backend.vto.smoke_test
```

Prerequisites:
- `backend/inference` server running locally (Sigmoi step).
- `GEMINI_API_KEY` exported or present in `.env` (Gemini step).
- For end-to-end runs: `backend/api` running on `:8001` (headshot lookup).
- `google-genai` installed:

  ```sh
  uv add -r requirements.txt
  ```

The smoke test makes real calls to both Sigmoi and Gemini, writes the
PNG to `backend/vto/output/<session>/<turn>.png`, and asserts the file
exists and is non-empty.

## Storage

This agent does **not** persist anything in the user's profile. The
orchestrator owns episode persistence and writes the atomic bundle
(`request.json` + `style.json` + `vto.json` + `vto.png`) under
`backend/api/profiles/{user_id}/episodes/{ep_id}/` after the turn.

For developer inspection during the demo, this agent additionally
writes a per-turn reproduction kit to:

```
backend/vto/output/
  {session_id}/
    {turn_id}.{ext}           # rendered image — ext follows mime (jpg/png/webp)
    {turn_id}.meta.json       # input request, Sigmoi prompts in/out, Gemini config
```

`meta.json` is enough to replay any turn end-to-end (re-send the
captured Sigmoi prompt, re-send the captured Gemini prompt with the
headshot path). Not the canonical store — safe to delete. The source of
truth (once the orchestrator lands) is the user's episode folder.

## Clarifying turn

If the model can't infer the occasion, it returns a clarifying turn
instead of the full schema. The agent surfaces this as a
`VtoClarificationRequired` exception; the orchestrator then asks the
user a follow-up rather than rendering anything.

Only `occasion` is treated as critical. Setting, lighting, mood, and
time-of-day are filled by the model and Gemini.

## Out of scope

- Inferring whether the user wants VTO (orchestrator routes)
- Conversation logging (orchestrator)
- Mapping descriptive pieces to real products — coming in a later phase
  with a product-search tool, at which point the `outfit` field becomes
  meaningful

See `CLAUDE.md` for the full design spec, including the `outfit`-ignored
runtime contract and Gemini API specifics.
