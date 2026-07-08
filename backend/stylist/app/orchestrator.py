"""Per-turn orchestration via a single structured-output call.

ONE LLM call per turn. The model returns both a chat message and a
structured ``next_action`` describing what to do next. Mirrors the
prelegal pattern exactly.

Backend: OpenRouter routing to ``openai/gpt-oss-120b`` on Cerebras —
fast, cheap, reliable structured output. The local fine-tuned
llama-server stays the worker for style/VTO content generation; it is
NOT used here for orchestration.

Out of scope (Phase 1):
- Episode persistence (Phase 2)
- Conversation logging (Phase 3)
- SSE streaming (Phase 4)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from litellm import completion
from pydantic import BaseModel, ValidationError

from backend.style.agent import StyleAgentError
from backend.style.agent import run as style_run
from backend.vto.agent import VtoAgentError, VtoClarificationRequired
from backend.vto.agent import run as vto_run

from . import replies
from .sessions import Session, store

logger = logging.getLogger(__name__)

ORCHESTRATOR_MODEL = "openrouter/openai/gpt-oss-120b"
ORCHESTRATOR_PROVIDER = {"provider": {"order": ["cerebras"]}}

CONVERSATION_WINDOW = 3   # turns sent to sub-agents (training distribution)
HISTORY_WINDOW = 12       # turns sent to the orchestrator


SYSTEM_PROMPT = """You are Raven — a warm, observant AI stylist with editorial taste. The user has selected a persona profile and is chatting with you.

For every user message, evaluate TWO INDEPENDENT INTENTS, then build the `next_actions` list. Both can be true at once.

INTENT 1 — STYLE (output a new recommendation)
True if the user is asking for ANY of:
  - what to wear / what they should wear
  - an outfit for a specific occasion (wedding, dinner, date, work, etc.)
  - dressing for weather or context
  - "another", "different", "new", "fresh", "alternative", "else" option
  - "give me a look"
If true → include "recommend_outfit" in next_actions.

INTENT 2 — VISUAL (render the outfit as an image on the user)
True if the user message contains ANY of these words/phrases:
  show, see, render, try on, visualize, visualise, draw, look like, on me, let me see, picture, image
If true → include "render_vto" in next_actions.
EXCEPTION: if INTENT 2 is true but no recommendation exists yet AND INTENT 1 is false, do NOT include render_vto — instead chat briefly asking the user what they're dressing for, and leave next_actions empty.

DECISION EXAMPLES (notice "show me a different X" triggers BOTH):
  "what should I wear to a wedding"   → STYLE:yes, VISUAL:no → ["recommend_outfit"]
  "give me a date night look"         → STYLE:yes, VISUAL:no → ["recommend_outfit"]
  "another option"                    → STYLE:yes, VISUAL:no → ["recommend_outfit"]
  "show me what that looks like"      → STYLE:no,  VISUAL:yes → ["render_vto"]
  "let me see it on me"               → STYLE:no,  VISUAL:yes → ["render_vto"]
  "render it"                         → STYLE:no,  VISUAL:yes → ["render_vto"]
  "show me a different style"         → STYLE:yes, VISUAL:yes → ["recommend_outfit", "render_vto"]
  "show me another look on me"        → STYLE:yes, VISUAL:yes → ["recommend_outfit", "render_vto"]
  "give me another, and show me"      → STYLE:yes, VISUAL:yes → ["recommend_outfit", "render_vto"]
  "different one, render it"          → STYLE:yes, VISUAL:yes → ["recommend_outfit", "render_vto"]
  "hi" / "thanks" / "ok bye"          → STYLE:no,  VISUAL:no  → []

ORDERING: when both actions are present, "recommend_outfit" must come first.

THIRD FIELD — `avoid_previous_style` (boolean):
Set to TRUE when the user explicitly asks for a NEW / DIFFERENT outfit (signal words: "different", "another", "new", "fresh", "alternative", "else", "something else", "switch it up"). False otherwise.
  "show me a different style"  → avoid_previous_style: true
  "another option"             → avoid_previous_style: true
  "give me something else"     → avoid_previous_style: true
  "what should I wear"         → avoid_previous_style: false  (first ask, nothing to avoid)
  "show me what that looks like" → avoid_previous_style: false  (no new outfit asked for)
  "thanks" / "hi"              → avoid_previous_style: false

MESSAGE: brief, conversational, warm, 1–2 sentences. No markdown, no emojis, no analysis. When triggering actions, just acknowledge briefly — the outfit card and image appear alongside."""


class AgentResponse(BaseModel):
    message: str
    next_actions: list[Literal["recommend_outfit", "render_vto"]] = []
    # When the user explicitly asked for a NEW / DIFFERENT outfit, set true so
    # the orchestrator marks the most recent outfit as rejected before calling
    # the style agent again. This prevents the model getting stuck on the
    # same recommendation when the user is clearly asking to move on.
    avoid_previous_style: bool = False


# ---------- response shape helpers ----------

def _chat_response(session: Session, turn_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "chat",
        "text": text,
        "outfit_card": None,
        "vto": None,
        "session_id": session.session_id,
        "turn_id": turn_id,
    }


def _outfit_response(
    session: Session, turn_id: str, text: str, style_output: dict[str, Any]
) -> dict[str, Any]:
    rec = (style_output.get("recommendations") or [{}])[0]
    return {
        "type": "outfit",
        "text": text,
        "outfit_card": {
            "label": rec.get("label", ""),
            "summary": rec.get("logic_summary", ""),
            "pieces": rec.get("pieces", []),
        },
        "vto": None,
        "session_id": session.session_id,
        "turn_id": turn_id,
    }


def _vto_response(
    session: Session, turn_id: str, text: str, vto_output: dict[str, Any]
) -> dict[str, Any]:
    return {
        "type": "vto",
        "text": text,
        "outfit_card": None,
        "vto": {
            "image_b64": vto_output["image_b64"],
            "image_mime": vto_output["image_mime"],
            "description": vto_output["description"],
            "scene": vto_output.get("scene") or {},
        },
        "session_id": session.session_id,
        "turn_id": turn_id,
    }


def _clarification_response(session: Session, turn_id: str, question: str) -> dict[str, Any]:
    return {
        "type": "clarification",
        "text": question,
        "outfit_card": None,
        "vto": None,
        "session_id": session.session_id,
        "turn_id": turn_id,
    }


# ---------- signal handling ----------

def _apply_signals(session: Session, signals: list[dict[str, str]] | None) -> None:
    if not signals:
        return
    for sig in signals:
        kind = sig.get("kind")
        label = sig.get("label")
        if not kind or not label:
            continue
        entry = {"label": label, "reason": sig.get("reason") or label}
        if kind == "thumb_up":
            session.liked_styles.append(entry)
        elif kind == "thumb_down":
            session.rejected_styles.append(entry)


# ---------- orchestrator decision call ----------

def _decide(session: Session) -> AgentResponse:
    """One LLM call (with one retry on empty response).

    Returns chat message + next_action via structured output.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    history = session.conversation[-HISTORY_WINDOW:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": t["role"], "content": t["content"]} for t in history)

    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            response = completion(
                model=ORCHESTRATOR_MODEL,
                messages=messages,
                response_format=AgentResponse,
                reasoning_effort="low",
                extra_body=ORCHESTRATOR_PROVIDER,
                api_key=api_key,
            )
            content = response.choices[0].message.content
            if content:
                return AgentResponse.model_validate_json(content)
            logger.info("orchestrator returned empty content on attempt %d", attempt)
            last_exc = RuntimeError("empty content")
        except Exception as exc:
            logger.info("orchestrator attempt %d failed: %s", attempt, exc)
            last_exc = exc
    raise last_exc or RuntimeError("orchestrator decision failed")


# ---------- sub-agent runners ----------

def _build_style_request(session: Session) -> dict[str, Any]:
    return {
        "conversation": session.conversation[-CONVERSATION_WINDOW:],
        "liked_styles": list(session.liked_styles),
        "rejected_styles": list(session.rejected_styles),
    }


def _run_style(session: Session) -> dict[str, Any] | None:
    """Call style sub-agent. Returns the raw result on success, None on failure or
    degenerate output. Updates session.last_style on success."""
    try:
        result = style_run(session.user_id, _build_style_request(session))
    except StyleAgentError as exc:
        logger.warning("style sub-agent failed: %s", exc)
        return None
    rec = (result.get("recommendations") or [{}])[0]
    if not rec.get("label") or not rec.get("pieces"):
        return None
    session.last_style = result
    return result


def _run_vto(
    session: Session, turn_id: str, message: str
) -> dict[str, Any] | None | VtoClarificationRequired:
    """Call VTO sub-agent. Returns:
        dict          → success
        None          → unexpected failure
        VtoClarificationRequired exception (returned as-is) → ask user
    """
    if session.last_style is None:
        return None
    try:
        return vto_run(
            session.user_id,
            {"prompt": message, "style": session.last_style},
            session_id=session.session_id,
            turn_id=turn_id,
        )
    except VtoClarificationRequired as exc:
        return exc
    except VtoAgentError as exc:
        logger.warning("vto sub-agent failed: %s", exc)
        return None


# ---------- entry point ----------

def handle_turn(
    session_id: str,
    user_id: str,
    message: str,
    signals: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    session = store.get_or_create(session_id, user_id)
    _apply_signals(session, signals)
    session.append_user(message)
    turn_id = session.next_turn_id()

    try:
        decision = _decide(session)
    except (ValidationError, Exception) as exc:
        logger.warning("orchestrator decision failed: %s", exc)
        text = replies.SUB_AGENT_FAILURE
        session.append_assistant(text)
        return _chat_response(session, turn_id, text)

    # Normalise actions: dedupe while preserving order, ensure recommend_outfit
    # runs before render_vto so the new outfit exists before it renders.
    seen: set[str] = set()
    actions: list[str] = []
    for a in decision.next_actions:
        if a not in seen:
            seen.add(a)
            actions.append(a)
    if "recommend_outfit" in actions and "render_vto" in actions:
        actions = ["recommend_outfit", "render_vto"]

    intro = decision.message
    style_payload: dict[str, Any] | None = None
    vto_payload: dict[str, Any] | None = None
    clarification: str | None = None

    if "recommend_outfit" in actions:
        # If the user asked for a different outfit, mark the previous one as
        # rejected so the style agent moves away from it.
        if decision.avoid_previous_style and session.last_style is not None:
            prev = (session.last_style.get("recommendations") or [{}])[0]
            prev_label = prev.get("label")
            prev_summary = prev.get("logic_summary") or prev_label or ""
            if prev_label and not any(
                r.get("label") == prev_label for r in session.rejected_styles
            ):
                session.rejected_styles.append({
                    "label": prev_label,
                    "reason": (prev_summary or "user asked for a different style"),
                })
        style_payload = _run_style(session)

    if "render_vto" in actions:
        vto_result = _run_vto(session, turn_id, message)
        if isinstance(vto_result, VtoClarificationRequired):
            clarification = vto_result.question
        elif vto_result is not None:
            vto_payload = vto_result
            session.last_vto = vto_payload

    # Append assistant turn once, then build the response.
    if clarification:
        session.append_assistant(clarification)
        return _clarification_response(session, turn_id, clarification)

    session.append_assistant(intro)

    rec = None
    if style_payload:
        rec = (style_payload.get("recommendations") or [{}])[0]

    has_outfit = bool(rec and rec.get("label") and rec.get("pieces"))
    has_vto = vto_payload is not None

    if has_outfit and has_vto:
        return {
            "type": "outfit_vto",
            "text": intro,
            "outfit_card": {
                "label": rec["label"],
                "summary": rec.get("logic_summary", ""),
                "pieces": rec.get("pieces", []),
            },
            "vto": {
                "image_b64": vto_payload["image_b64"],
                "image_mime": vto_payload["image_mime"],
                "description": vto_payload["description"],
                "scene": vto_payload.get("scene") or {},
            },
            "session_id": session.session_id,
            "turn_id": turn_id,
        }
    if has_outfit:
        return _outfit_response(session, turn_id, intro, style_payload)
    if has_vto:
        return _vto_response(session, turn_id, intro, vto_payload)
    return _chat_response(session, turn_id, intro)
