# Stylist Master Agent

The orchestrator. Single point of contact for the frontend. Receives
each user turn, decides how to fulfil it, coordinates the stateless
sub-agents (`backend/style`, `backend/vto`) as tool calls, and persists
the turn as an episode in the user's profile.

Local for the demo; deploys as a Lambda later with no surface change.

## Responsibilities

This is the only stateful component in the backend.

- **Session state.** Active conversation history, plus the `liked_styles`
  / `rejected_styles` lists accumulated from thumbs-up/down events this
  session, plus `last_style` (the most recent style output, used as VTO
  input) and `last_vto`. In-memory dict keyed by `session_id` for the
  demo; later phase moves to a session store.
- **Decision call.** Per turn, ONE structured-output LLM call returns the
  chat message **plus** a list of `next_actions` (any combination of
  `recommend_outfit`, `render_vto`) **plus** an `avoid_previous_style`
  flag. Both intents are evaluated independently, so a single user turn
  can drive style + VTO together (e.g. *"show me a different style"*).
- **Request shaping.** Builds the `request` dict each sub-agent expects
  from session state — last ~3 turns of conversation (training-distribution
  match), liked/rejected lists, the current style output if calling VTO.
- **Episode persistence.** After each turn, atomically writes the bundle
  to the user's profile (see *Episode persistence* below).
- **Frontend response synthesis.** Takes structured sub-agent outputs and
  composes the user-facing chat reply + tells the frontend what to render
  on the VTO canvas. Streams via SSE.
- **Failure handling.** Catches sub-agent errors and surfaces a graceful
  message to the user rather than letting raw exceptions reach the
  frontend.

## Contract

Frontend → orchestrator. One `POST /turn` per user message, JSON in,
JSON out (SSE deferred to Phase 4):

```
POST /turn
{
    "session_id": str,
    "user_id": str,
    "message": str,
    "signals"?: [{"kind": "thumb_up|thumb_down", "label": "<outfit-label>", "reason"?: "..."}]
}

Response (200, application/json):
{
    "type": "chat" | "outfit" | "vto" | "outfit_vto" | "clarification",
    "text": "...",                          # the orchestrator's chat message
    "outfit_card": {label, summary, pieces} | null,
    "vto": {image_b64, image_mime, description, scene} | null,
    "session_id": "...",
    "turn_id": "..."
}
```

`outfit_card` and `vto` are independent — either, both, or neither may
be populated. The frontend renders whichever fields are present.

## Decision logic (LLM)

Routing is **not** keyword-based. The orchestrator makes one structured
call per turn against `openai/gpt-oss-120b` via OpenRouter pinned to
Cerebras (fast + cheap; `~$0.001/turn`). The local fine-tuned llama-server
remains the worker for `<|SIGMOI_STYLE|>` / `<|SIGMOI_VTO|>` content; it
is **not** used for orchestration.

Response model:

```python
class AgentResponse(BaseModel):
    message: str
    next_actions: list[Literal["recommend_outfit", "render_vto"]] = []
    avoid_previous_style: bool = False
```

System prompt evaluates two independent intents per turn:

| Intent | True when |
|---|---|
| STYLE | user asks for any kind of outfit / what-to-wear / "another"/"different"/"fresh" option |
| VISUAL | user message contains show / see / render / try on / look like / on me / picture / image |

Both can be true, e.g. *"show me a different style"* → both fire,
`avoid_previous_style: true`. When `avoid_previous_style` is true and a
previous outfit exists, the orchestrator appends that outfit's label to
`session.rejected_styles` before calling style — so the style agent
moves on instead of repeating itself. When both actions are present they
run in order: `recommend_outfit` first so the new outfit exists before
VTO renders it.

Pure-chat replies (greetings, thanks, clarifications) go straight from
`AgentResponse.message` — no sub-agent call, no template lookup.

Failure handling: empty / invalid LLM responses retry once; a hard
failure surfaces a graceful chat string from `replies.SUB_AGENT_FAILURE`.

## Conversation window

The orchestrator passes **the last ~3 turns** of the active session to
sub-agents in `request.conversation`. This matches the model's training
distribution (filtered to 0–3 prior turns due to context budget). The
window is computed at call time; sub-agents do not trim.

## Episode persistence

After each turn that produced a sub-agent call, the orchestrator writes
an atomic bundle to:

```
backend/api/profiles/{user_id}/episodes/{ep_id}/
  request.json     # built from session state at turn start
  style.json       # full style agent output (if style was called)
  vto.json         # sigmoi_response field from VTO output (if VTO was called)
  vto.png          # decoded image_b64 from VTO output (if VTO was called)
```

**Atomic** = all files for the turn are written together (or all skipped
on failure). Use a temp directory + atomic rename so a partially-written
episode is never observable.

Episode IDs are allocated by scanning the existing `episodes/*/` and
taking the next `ep_NNN`. Future phase moves this behind a backend/api
create endpoint (see below).

Pure chat turns do not produce an episode — episodes capture
recommendation-bearing turns only.

## Backend/api dependencies

| Need | Endpoint | Status |
|---|---|---|
| Read profile + persona | `GET /users/{user_id}` | Exists. |
| Read headshot | served alongside profile data | Exists. |
| Allocate / write episode | `POST /users/{user_id}/episodes` (or similar) | **Does not exist yet.** Needed when this agent ships. Until then, the orchestrator writes to the filesystem directly under `backend/api/profiles/`. |

Filesystem writes are a temporary expedient. When the API gains a create
endpoint, the orchestrator switches to HTTP without changing its episode
schema.

## Conversation logging

Selective: log a row to `backend/api/profiles/{user_id}/evidence/conversations.jsonl`
only when the turn produced a load-bearing signal — style request,
recommendation returned, thumbs up/down event. Plain chitchat is not
logged. The JSONL is the source corpus for the offline distillation that
updates `derived/profile.json` later, so noise hurts; sparse high-signal
rows help.

Minimal row shape:

```json
{
  "conversation_id": "...",
  "message_id": "...",
  "user_id": "...",
  "session_id": "...",
  "timestamp": "...",
  "speaker": "user|assistant",
  "text": "...",
  "event": "style_request|style_response|vto_request|vto_image|thumb_up|thumb_down"
}
```

Topic tags / phase fields get added offline.

## Out of scope

- Profile / persona storage → `backend/api`
- Style recommendations → `backend/style`
- VTO image generation → `backend/vto`
- Frontend rendering → `frontend`
- Authentication → later phase

## Reference

Multi-agent orchestrator pattern: `../../mlstudios/tutorials/alex/backend/`.
Borrow the structure (orchestrator + stateless tool agents + atomic
session persistence), not the financial-domain code.
