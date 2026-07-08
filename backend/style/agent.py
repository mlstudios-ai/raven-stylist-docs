"""Style agent. Stateless tool that returns a personalised style recommendation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

import httpx

from raven.inference_client import make_client

from .template import (
    STYLE_OUTPUT_SCHEMA,
    STYLE_SYSTEM_PROMPT,
    STYLE_USER_PROMPT_TEMPLATE,
    build_conversation,
    build_style_signals,
    build_styles,
    build_use_cases,
)

DEFAULT_API_BASE = os.environ.get("RAVEN_API_BASE", "http://127.0.0.1:8001")
PROFILE_ATTRIBUTES = "context"


class StyleAgentError(ValueError):
    """Raised when the model returns output that does not parse to the expected schema."""


# ---------- profile fetch (DI seam) ----------

def fetch_profile_http(user_id: str, base_url: str = DEFAULT_API_BASE) -> dict[str, Any]:
    """Default profile loader: GET backend/api /users/{user_id}?attributes=..."""
    with httpx.Client(timeout=10.0) as client:
        r = client.get(
            f"{base_url}/users/{user_id}",
            params={"attributes": PROFILE_ATTRIBUTES},
        )
        r.raise_for_status()
        return r.json()


# ---------- prompt construction ----------

def _build_user_prompt(profile: dict[str, Any], request: dict[str, Any]) -> str:
    """Fill STYLE_USER_PROMPT_TEMPLATE from API-shape profile + request payload."""

    return STYLE_USER_PROMPT_TEMPLATE.format(
        liked_styles=build_styles(request.get("liked_styles") or []),
        rejected_styles=build_styles(request.get("rejected_styles") or []),
    )


# ---------- response parsing ----------

def _strip_fences(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s
    s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.rstrip().endswith("```"):
        s = s.rstrip()[:-3].rstrip()
    return s


def _parse_response(raw: str) -> dict[str, Any]:
    text = _strip_fences(raw)
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError as e:
        raise StyleAgentError(
            f"Model returned invalid JSON: {e}\n--- raw output ---\n{raw}"
        ) from e
    if not isinstance(obj, dict):
        raise StyleAgentError(
            f"Model returned JSON of type {type(obj).__name__}, expected object.\n"
            f"--- raw output ---\n{raw}"
        )
    return obj


# ---------- entry point ----------

def run(
    user_id: str,
    request: dict[str, Any],
    *,
    profile_loader: Callable[[str], dict[str, Any]] = fetch_profile_http,
    client_factory: Callable[[], tuple[Any, str]] = make_client,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Run the style agent.

    Args:
        user_id: Resolved by the orchestrator before calling.
        request: ``{conversation, liked_styles, rejected_styles}``. ``conversation``
            should be the last ~3 turns of the active session (training-distribution
            match); the orchestrator owns this windowing.
        profile_loader: Override for testing. Defaults to HTTP against backend/api.
        client_factory: Override for testing. Defaults to raven.inference_client.make_client.
        temperature: Sampling temperature for the model.

    Returns:
        Parsed JSON conforming to the output schema embedded in
        ``STYLE_SYSTEM_PROMPT``. See ``response_exmaple.json`` for shape.

    Raises:
        StyleAgentError: The model returned text that did not parse as JSON.
        httpx.HTTPError: Profile fetch failed.
    """
    profile = profile_loader(user_id)
    user_prompt = _build_user_prompt(profile, request)

    client, model = client_factory()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": STYLE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "style_recommendation",
                "strict": True,
                "schema": STYLE_OUTPUT_SCHEMA,
            },
        },
    )
    raw = resp.choices[0].message.content or ""
    return _parse_response(raw)
