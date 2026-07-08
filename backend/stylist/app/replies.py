"""Static reply strings used as safety nets when sub-agents fail.

Conversational replies are produced by the orchestrator's LLM call.
Nothing in this file is user-facing in the happy path.
"""

SUB_AGENT_FAILURE = (
    "I had trouble pulling that together — give me a second and try again, "
    "or rephrase what you're after."
)
