# Stylist Master Agent — Build Plan

> Three-doc convention: **CLAUDE.md** = what it is. **README.md** =
> developer guide. **PLAN.md** = the recipe a coding agent would use to
> rebuild this from scratch.

## Status

🟢 **Phase 1 complete** (2026-05-10). Multi-turn smoke passes end-to-end.
Phases 2–4 deferred to the project backlog (`/BACKLOG.md`); see those
items if/when this work resumes.

## Materials needed

| Item | Where it lives | Purpose |
|---|---|---|
| Component spec | `backend/stylist/CLAUDE.md` | HTTP contract, routing, persistence, conversation logging schema. |
| Style sub-agent | `backend/style/agent.py` :: `run(user_id, request)` | Returns structured recommendation JSON. Already built. |
| VTO sub-agent | `backend/vto/agent.py` :: `run(user_id, request)` | Returns `{image_b64, image_mime, description, scene, sigmoi_response}`. Already built. Raises `VtoClarificationRequired` for ambiguous occasion. |
| Profile API | `backend/api` (port 8001) | `GET /users` for picker; sub-agents call it for profile data. |
| Inference server | local llama-server on 8080 | Used by sub-agents and (potentially) for chat synthesis. |
| Profile root | `backend/api/profiles/{user_id}/` | Episode write target. `evidence/conversations.jsonl` log target. |
| FastAPI | already a project dep | HTTP transport. |

## Build tasks (phased)

### Phase 1 — Core orchestrator (HTTP boundary, in-process logic, JSON response)

| # | Task | Status |
|---|---|---|
| 1 | `backend/stylist/app/main.py` — FastAPI app, `POST /turn` returning JSON (not SSE yet) | ✅ |
| 2 | In-memory session store keyed by `session_id` — holds: full conversation, `liked_styles`, `rejected_styles`, last style output (for VTO follow-up) | ✅ |
| 3 | Decision module — single structured-output LLM call (OpenRouter → `openai/gpt-oss-120b` on Cerebras) returning `{message, next_actions[], avoid_previous_style}`; keyword routing dropped | ✅ |
| 4 | `_build_style_request` — last 3 turns of session conversation + accumulated liked/rejected lists | ✅ |
| 5 | `_build_vto_request` — current user prompt + last style output | ✅ |
| 6 | Sub-agent dispatch with try/except — catch `StyleAgentError`, `VtoAgentError`, `VtoClarificationRequired` and surface gracefully to user | ✅ |
| 7 | Pure-chat handler — `AgentResponse.message` straight through; no template fallback | ✅ |
| 8 | Multi-action support — when both `recommend_outfit` and `render_vto` are returned, run style first then VTO; emit `type=outfit_vto` carrying both `outfit_card` and `vto` in one response | ✅ |
| 9 | `avoid_previous_style` handling — auto-append the previous outfit's label to `session.rejected_styles` before re-calling style, so the agent moves on instead of repeating | ✅ |
| 10 | Response shaper — `{type, text, outfit_card?, vto?}` JSON. `outfit_card` = `{label, summary, pieces}` from style; `vto` = `{image_b64, image_mime, description, scene}` from VTO | ✅ |
| 11 | Smoke: `curl POST /turn` for one style ask + one VTO follow-up + a "different" follow-up; validate multi-action shape | ✅ |

### Phase 2 — Episode persistence — 🅱️ BACKLOG

| # | Task | Status |
|---|---|---|
| 10 | Episode ID allocator — scans `backend/api/profiles/{user_id}/episodes/`, returns next `ep_NNN` | 🅱️ |
| 11 | Atomic episode writer — temp dir + rename. Writes `request.json`, `style.json`, `vto.json`, `vto.png` (only the files relevant to the turn) | 🅱️ |
| 12 | Wire into Phase 1 turn handler | 🅱️ |
| 13 | Smoke: after two turns, two episode folders exist with all relevant files | 🅱️ |

### Phase 3 — Conversation logging — 🅱️ BACKLOG

| # | Task | Status |
|---|---|---|
| 14 | Selective JSONL appender — `evidence/conversations.jsonl` row per `event ∈ {style_request, style_response, vto_request, vto_image, thumb_up, thumb_down}` | 🅱️ |
| 15 | Wire into turn handler + signals endpoint | 🅱️ |
| 16 | Smoke: after a multi-turn session, only meaningful rows in JSONL (no chitchat noise) | 🅱️ |

### Phase 4 — Streaming (post-frontend) — 🅱️ BACKLOG

| # | Task | Status |
|---|---|---|
| 17 | Replace JSON response with `text/event-stream`. Events: `chat_chunk`, `outfit_card`, `vto_loading`, `vto_image`, `done` | 🅱️ |
| 18 | Stream Sigmoi tokens for chat replies (orchestrator's own model calls only, not sub-agent JSON) | 🅱️ |
| 19 | Front the SSE with a small EventSource demo HTML to verify | 🅱️ |

### Phase 5 — End-to-end smoke — 🅱️ BACKLOG

| # | Task | Status |
|---|---|---|
| 20 | Multi-turn script: select Jamie → ask for outfit → thumb-down → ask for VTO → verify (a) correct sub-agents called, (b) episodes written atomically, (c) conversations.jsonl rows present, (d) liked/rejected feed into next style request | 🅱️ |

## Key decisions

- **Single stateful component.** All session state lives here; sub-agents
  are pure functions. This keeps sub-agents Lambda-deployable without
  shared session storage.
- **Routing is a structured LLM call, not keywords.** One
  `litellm.completion` call per turn against `gpt-oss-120b` on Cerebras
  (via OpenRouter), Pydantic `response_format` enforces the
  `{message, next_actions, avoid_previous_style}` shape. Earlier keyword
  heuristic was abandoned — it couldn't handle compound intents
  ("show me a different style" needs both style + VTO) and couldn't tell
  "another" from a fresh ask. The local fine-tuned llama-server stays the
  worker for style/VTO content only.
- **Both intents are independent.** A single turn can emit
  `["recommend_outfit", "render_vto"]`; orchestrator runs them in that
  order so VTO has a fresh style to render.
- **`avoid_previous_style` short-circuits repeats.** When the user asks
  for "different"/"another"/etc., the model sets the flag and the
  orchestrator marks the previous outfit rejected before calling style.
  Without this, style was getting stuck on the same recommendation.
- **Only orchestrator writes episodes.** Atomic per-turn bundle. When
  `backend/api` exposes `POST /users/{id}/episodes`, swap filesystem
  writes for HTTP without changing the schema.
- **Selective conversation logging.** Style/VTO/thumb events only.
  JSONL is corpus for an offline distiller, not a live transcript.
- **JSON response in Phase 1, SSE in Phase 4.** Streaming requires the
  frontend to verify; not worth building blind.

## Open questions to resolve before each phase

These are tracked in conversation, will be re-confirmed at build time:

- Routing keywords (initial set; refine on observation).
- Pure-chat reply set (fixed templates is the current default).
- `request.json` shape — should match training-time shape so sub-agents
  trained on it (style at least) parse cleanly. Use the existing
  `episodes/*/request.json` examples as reference.

## Out of scope

- Profile/persona storage → `backend/api`.
- Style logic → `backend/style`.
- VTO image generation → `backend/vto`.
- Frontend rendering → `frontend`.
- Authentication / login → later phase.
