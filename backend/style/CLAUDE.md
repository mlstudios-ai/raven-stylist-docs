# Style Agent

Stateless sub-agent that produces a personalised style recommendation for a
user query. Invoked as a tool by the stylist orchestrator. Local for the
demo; deploys as a Lambda later with no surface change.

## Contract

```
run(user_id: str, request: dict) -> dict
```

## Conversation window

`request.conversation` should be **the last ~3 turns** of the active
session, ending on the user's current ask. This matches the training
distribution: training data was filtered to 0–3 prior turns due to context
budget. Going wider drifts off-distribution and degrades output quality.

## Files

| File | Purpose |
|---|---|
| `template.py` | `STYLE_SYSTEM_PROMPT` (with embedded output schema) + `STYLE_USER_PROMPT_TEMPLATE` + builder helpers. |
| `prompt_exmaple.txt` | Filled user-prompt example (3 turns). |
| `response_exmaple.json` | Example structured output. |

## Out of scope
- Prompt construction for other agents — each agent owns its own templates