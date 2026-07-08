# Style Agent — Build Plan

> Three-doc convention: **CLAUDE.md** = what it is. **README.md** =
> developer guide. **PLAN.md** = the recipe a coding agent would use to
> rebuild this from scratch.

## Status

✅ Built and verified end-to-end against the local fine-tuned model.
Smoke test passes with `usr_006_jamie/episodes/ep_010/request.json`.

## Materials needed

| Item | Where it lives | Purpose |
|---|---|---|
| Sigmoi system prompt + output schema | `template.py` :: `STYLE_SYSTEM_PROMPT` | Contains `<\|SIGMOI_STYLE\|>` task tag and embedded JSON schema. |
| User-prompt template | `template.py` :: `STYLE_USER_PROMPT_TEMPLATE` | Profile + request slots. |
| Builder helpers | `template.py` :: `build_use_cases / build_style_signals / build_conversation / build_styles` | Format list-of-dicts into the YAML-ish prompt body. Use **dict access** (`p['role']`, not `p.role`). |
| Reference filled prompt | `prompt_exmaple.txt` | Anchors expected training distribution; the builder helpers must produce text matching this shape exactly. |
| Reference output | `response_exmaple.json` | Anchors expected response schema. |
| Profile data | `backend/api/profiles/{user_id}/derived/profile.json` (read via API) | Identity, body, style signals, behaviour, contextual needs. |
| OpenAI-compatible client | `raven.inference_client.make_client()` | Wraps the local llama-server (or remote endpoint via env vars). |
| Inference server | `scripts/serve_model.py --model models/sigmoi/stylist_gguf/model-q4_k_m.gguf --ctx-size 8192 -- --jinja` | Must be running on `127.0.0.1:8080` for any model call. |
| Backend API | `backend/api/app/main.py` | `GET /users/{id}?attributes=...` returns profile data shaped by caller-facing keys. |

## Build tasks

| # | Task | Status |
|---|---|---|
| 1 | Fix builder helpers to use dict access (training data is plain JSON, not Python objects) | ✅ |
| 2 | Drop the `user_request: {user_prompt}` line from `STYLE_USER_PROMPT_TEMPLATE` so rendered prompts match `prompt_exmaple.txt` exactly | ✅ |
| 3 | `agent.py` skeleton — `run(user_id, request) → dict` with DI seams (`profile_loader`, `client_factory`) | ✅ |
| 4 | `_fetch_profile` over HTTP with `attributes=identity,body,style_signals,behaviour,context` | ✅ |
| 5 | `_build_user_prompt` mapping API-shape keys (`behaviour`, `body`, …) to the template's nested structure (`behavioural_profile`, `body_profile`, …) | ✅ |
| 6 | Model call with `temperature=0.2`, `response_format={"type":"json_object"}` | ✅ |
| 7 | `_parse_response` using `JSONDecoder().raw_decode()` to tolerate trailing junk; raise `StyleAgentError` on real failure | ✅ |
| 8 | `smoke_test.py` — uses FastAPI `TestClient` for in-process profile fetch (no separate uvicorn), trims conversation to last 3 turns, validates required schema keys | ✅ |
| 9 | Catch free-form clarifying turns (parser currently fails if model emits non-JSON) | ⏳ Pending. Mirror VTO's `VtoClarificationRequired` if needed. |

## Key decisions

- **Conversation window is the orchestrator's responsibility.** This agent
  trusts whatever `request.conversation` it gets. The 3-turn cap matches
  training distribution; the smoke test trims explicitly to demonstrate.
- **Profile fetch is HTTP, not disk read.** Same code in demo and Lambda;
  smoke test uses in-process `TestClient` to keep it hermetic without
  needing a uvicorn process.
- **Specific attribute list, not `?attributes=all`.** Persona/style_dna
  fields aren't used by the user-prompt template; fetching them only
  bloats the request.
- **Temperature 0.2 + `json_object` response format.** Structured output
  belongs near greedy decoding; content variety comes from the prompt.
- **Defensive `raw_decode` parsing** belt-and-braces against trailing
  garbage (one early model run emitted a stray `}`).

## Smoke test definition

```sh
# Prerequisite: inference server up at 127.0.0.1:8080
python -m backend.style.smoke_test
```

## Out of scope (deferred to other components)

- Session state, conversation history → orchestrator (`backend/stylist`).
- User_id resolution from session → orchestrator.
- Episode persistence → orchestrator (writes `episodes/{ep}/style.json`).
- Profile/persona storage → `backend/api`.
