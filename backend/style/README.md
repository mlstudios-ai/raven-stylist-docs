# Style Agent

Stateless sub-agent in the Raven multi-agent system. Given a user's current
style ask and their profile, returns a personalised, structured outfit
recommendation.

Invoked by the stylist orchestrator (`backend/stylist`) as a tool call.
Lives behind the same OpenAI-compatible inference service as the other
agents (`backend/inference`).

## Public surface

```python
from backend.style.agent import run

result = run(user_id="usr_006_jamie", request={
    "conversation": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "..."},
    ],
    "liked_styles":   [{"label": "...", "reason": "..."}],
    "rejected_styles": [{"label": "...", "reason": "..."}],
})
```

`result` is JSON conforming to the output schema embedded in
`template.py` (`STYLE_SYSTEM_PROMPT`). See `response_exmaple.json` for an
example.

## Inputs

| Field | Source | Notes |
|---|---|---|
| `user_id` | Orchestrator | Resolved from session before call. |
| `request.conversation` | Orchestrator | Last ~3 turns of the active session. Matches training distribution; do not pass full history. |
| `request.liked_styles` | Orchestrator | Items the user thumbed up this session. |
| `request.rejected_styles` | Orchestrator | Items the user thumbed down this session. |

The historical conversation log at
`backend/api/profiles/{user_id}/evidence/conversations.jsonl` is **not**
input to this agent. 

## Running

Smoke test (uses `usr_006_jamie/episodes/ep_010/request.json` against the
local inference server):

```sh
python -m backend.style.smoke_test
```

Prerequisites:
- `backend/inference` server running locally (see
  `backend/inference/README.md`).
- For end-to-end runs (not smoke), `backend/api` running on `:8001`.

## Files

| File | Role |
|---|---|
| `agent.py` | Public `run()` entry point, profile fetch, model call, JSON parse. |
| `template.py` | System prompt (with output schema) and user-prompt template. |
| `smoke_test.py` | Self-contained verification using on-disk fixtures. |
| `prompt_exmaple.txt` | Reference: filled user prompt (3 turns). |
| `response_exmaple.json` | Reference: example structured output. |

## Where this fits

```
frontend
   │
   ▼
stylist orchestrator   ── owns session state, conversation log, request shaping
   │   tool call: style.run(user_id, request)
   ▼
style agent (this)     ── stateless: profile + request → model → JSON
   │
   ├── HTTP → backend/api  (profile/persona)
   └── HTTP → backend/inference  (model)
```
