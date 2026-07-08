"""VTO agent. Stateless tool that returns a virtual try-on image plus structured scene metadata.

Triggered by the orchestrator only when the user has explicitly requested
a visualisation (e.g. "show me", "try it on"). The orchestrator routes;
this agent does not introspect intent.

Two-stage flow:
    1. Sigmoi (fine-tuned model, via raven.inference_client) takes the user
       prompt + style agent output and returns structured JSON {scene, outfit,
       prompt} matching the schema in template.VTO_SYSTEM_PROMPT. The `outfit`
       field is ignored at runtime — the authoritative outfit data is on
       request.style.recommendations[0].pieces, and outfit detail is already
       baked into prompt.user.
    2. Gemini Flash Image (gemini-3.1-flash-image-preview) renders the photo
       conditioned on prompt.system + prompt.user and the user's headshot
       (face reference for identity consistency).

The agent does not write to the user's episode store. Episodes are written
atomically by the orchestrator after a turn completes. This agent does
write a debug copy of each render to backend/vto/output/<session>/<turn>.
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image as PILImage

from raven.inference_client import make_client

from .template import VTO_SYSTEM_PROMPT, VTO_USER_PROMPT_TEMPLATE, build_pieces

load_dotenv()

GEMINI_MODEL = "gemini-3.1-flash-image-preview"
GEMINI_IMAGE_SIZE = "1K"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEBUG_OUTPUT_ROOT = Path(__file__).resolve().parent / "output"
DEFAULT_API_BASE = os.environ.get("RAVEN_API_BASE", "http://127.0.0.1:8001")

OPERATIONAL_DIRECTIVES = """

Operational directives (apply to every response):
- Only respond with the full schema when the user has explicitly requested a virtual try-on or visualisation. The orchestrator handles routing; do not invent VTO requests.
- If the occasion is unclear or missing from the user prompt and the style context, return JSON of the form {"clarifying_question": "..."} instead of the full schema. Ask only for the occasion; do not ask about lighting, mood, time of day, or other scene details — the model fills those.
"""


class VtoAgentError(ValueError):
    """Raised when Sigmoi returns invalid JSON or Gemini fails to produce an image."""


class VtoClarificationRequired(Exception):
    """Raised when Sigmoi flags that occasion is unclear and a clarifying turn is needed."""

    def __init__(self, question: str):
        super().__init__(question)
        self.question = question


# ---------- headshot fetch ----------

def fetch_headshot_path(user_id: str) -> Path:
    """Locate the user's headshot on disk.

    Direct disk read — backend/api does not yet serve image bytes. When it
    does, swap to HTTP without changing the caller-facing signature.
    """
    path = REPO_ROOT / "backend/api/profiles" / user_id / "photos" / "headshot.png"
    if not path.exists():
        raise VtoAgentError(f"Headshot not found at {path}")
    return path


def fetch_identity(user_id: str, base_url: str = DEFAULT_API_BASE) -> dict[str, Any]:
    """Fetch identity + body summary from backend/api so the Sigmoi prompt
    can anchor gender, age, and body shape correctly. Returns a dict with
    safe defaults if the API isn't reachable."""
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(
                f"{base_url}/users/{user_id}",
                params={"attributes": "identity,body"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return {"gender_identity": "person", "age": "adult", "body_shape": "average"}

    identity = data.get("identity") or {}
    body = data.get("body") or {}
    return {
        "gender_identity": identity.get("gender_identity") or "person",
        "age": str(identity.get("age") or "adult"),
        "body_shape": body.get("body_shape_inferred") or "average build",
    }


# ---------- Sigmoi step ----------

def _build_sigmoi_user_prompt(user_prompt_text: str, style: dict[str, Any]) -> str:
    """Fill VTO_USER_PROMPT_TEMPLATE from the style agent output."""
    context = style.get("context") or {}
    intent = style.get("intent") or {}
    recs = style.get("recommendations") or []
    if not recs:
        raise VtoAgentError("style.recommendations is empty — VTO needs at least one recommendation")
    rec = recs[0]
    pieces = rec.get("pieces") or []
    if not pieces:
        raise VtoAgentError("recommendation has no pieces")

    return VTO_USER_PROMPT_TEMPLATE.format(
        user_prompt=user_prompt_text,
        occasion=context.get("occasion", ""),
        primary_intent=intent.get("primary_intent", ""),
        label=rec.get("label", ""),
        logic_summary=rec.get("logic_summary", ""),
        pieces=build_pieces(pieces),
    )


def _strip_fences(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s
    s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.rstrip().endswith("```"):
        s = s.rstrip()[:-3].rstrip()
    return s


def _parse_sigmoi_response(raw: str) -> dict[str, Any]:
    text = _strip_fences(raw)
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError as e:
        raise VtoAgentError(f"Sigmoi returned invalid JSON: {e}\n--- raw ---\n{raw}") from e
    if not isinstance(obj, dict):
        raise VtoAgentError(f"Sigmoi returned non-object JSON: {type(obj).__name__}")
    if "clarifying_question" in obj:
        raise VtoClarificationRequired(obj["clarifying_question"])
    return obj


# ---------- Gemini step ----------

def call_gemini(
    prompt_system: str, prompt_user: str, headshot_path: Path
) -> tuple[bytes, str]:
    """Render an image via Gemini Flash Image.

    Returns:
        (image_bytes, mime_type) — typically ("...", "image/jpeg").
    """
    if not os.environ.get("GEMINI_API_KEY"):
        raise VtoAgentError("GEMINI_API_KEY not set")

    client = genai.Client()
    headshot = PILImage.open(headshot_path)

    combined_prompt = f"{prompt_system}\n\n{prompt_user}".strip()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[combined_prompt, headshot],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(image_size=GEMINI_IMAGE_SIZE),
        ),
    )

    for part in response.parts:
        img = part.as_image()
        if img is None or img.image_bytes is None:
            continue
        return img.image_bytes, (img.mime_type or "image/jpeg")

    raise VtoAgentError(
        f"Gemini returned no image. Response text: {getattr(response, 'text', None)!r}"
    )


# ---------- description synthesis ----------

def _compose_description(scene: dict[str, Any]) -> str:
    """Mechanical scene-derived blurb. Orchestrator may rewrite for chat voice."""
    occ = (scene.get("occasion") or "").strip()
    setting = (scene.get("setting") or "").strip()
    tod = (scene.get("time_of_day") or "").strip()
    mood = (scene.get("mood") or "").strip()
    parts = [p for p in (occ, setting, tod, mood) if p]
    return ". ".join(parts) + ("." if parts else "")


# ---------- debug persistence (developer affordance only) ----------

def _ext_for_mime(mime_type: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(
        mime_type, "bin"
    )


def _save_debug(
    session_id: str,
    turn_id: str,
    user_id: str,
    request: dict[str, Any],
    sigmoi_user_prompt: str,
    sigmoi_response: dict[str, Any],
    image_bytes: bytes,
    mime_type: str,
) -> Path:
    """Write a per-turn reproduction kit under backend/vto/output/{session}/.

    Files written:
        {turn_id}.{ext}        — rendered image (jpg/png/webp by mime)
        {turn_id}.meta.json    — input request, Sigmoi prompts in/out, Gemini meta
    """
    out_dir = DEBUG_OUTPUT_ROOT / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    img_path = out_dir / f"{turn_id}.{_ext_for_mime(mime_type)}"
    img_path.write_bytes(image_bytes)

    sigmoi_prompt_block = sigmoi_response.get("prompt") or {}
    meta = {
        "saved_at": time.time(),
        "session_id": session_id,
        "turn_id": turn_id,
        "user_id": user_id,
        "image": {
            "filename": img_path.name,
            "mime_type": mime_type,
            "bytes": len(image_bytes),
        },
        "input_request": {
            "prompt": request.get("prompt"),
            "style": request.get("style"),
        },
        "sigmoi": {
            "model": "raven-stylist (local llama-server)",
            "user_prompt_sent": sigmoi_user_prompt,
            "response": sigmoi_response,
        },
        "gemini": {
            "model": GEMINI_MODEL,
            "image_size": GEMINI_IMAGE_SIZE,
            "prompt_system_sent": sigmoi_prompt_block.get("system"),
            "prompt_user_sent": sigmoi_prompt_block.get("user"),
            "headshot_used": str(REPO_ROOT / "backend/api/profiles" / user_id / "photos" / "headshot.png"),
        },
    }
    (out_dir / f"{turn_id}.meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False)
    )
    return img_path


# ---------- entry point ----------

def run(
    user_id: str,
    request: dict[str, Any],
    *,
    session_id: str | None = None,
    turn_id: str | None = None,
    headshot_loader: Callable[[str], Path] = fetch_headshot_path,
    sigmoi_factory: Callable[[], tuple[Any, str]] = make_client,
    gemini_caller: Callable[[str, str, Path], tuple[bytes, str]] = call_gemini,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Run the VTO agent.

    Args:
        user_id: Resolved by the orchestrator before calling.
        request:
            prompt: str — user's most recent message (the one that triggered VTO).
            style: dict — full style agent output (intent, context, analysis,
                recommendations).
            conversation: optional list — last ~3 turns for context. Not required.
        session_id, turn_id: For the debug-output filename. Defaults to a uuid.
        headshot_loader, sigmoi_factory, gemini_caller: DI seams for tests.
        temperature: Sampling temperature for Sigmoi.

    Returns:
        {
            "image_b64":        base64-encoded image bytes (typically JPEG),
            "image_mime":       MIME type for the bytes ("image/jpeg" or "image/png"),
            "description":      mechanical scene-derived blurb,
            "scene":            raw scene block from Sigmoi,
            "sigmoi_response":  full Sigmoi JSON for the orchestrator to persist
                                as episodes/{ep_id}/vto.json.
        }

    Raises:
        VtoClarificationRequired: Sigmoi flagged occasion as unclear.
            Orchestrator should surface .question to the user instead of
            attempting to render.
        VtoAgentError: Sigmoi returned invalid JSON, or Gemini failed.
    """
    session_id = session_id or "smoke"
    turn_id = turn_id or uuid.uuid4().hex[:8]

    user_prompt = request.get("prompt") or ""
    style = request.get("style") or {}
    if not user_prompt:
        raise VtoAgentError("request.prompt is required")
    if not style:
        raise VtoAgentError("request.style is required")

    identity = fetch_identity(user_id)
    sigmoi_user_prompt = _build_sigmoi_user_prompt(user_prompt, style)
    system_prompt = VTO_SYSTEM_PROMPT + OPERATIONAL_DIRECTIVES

    client, model = sigmoi_factory()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sigmoi_user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or ""
    sigmoi_response = _parse_sigmoi_response(raw)

    prompt_block = sigmoi_response.get("prompt") or {}
    p_system = prompt_block.get("system") or ""
    p_user = prompt_block.get("user") or ""
    if not p_user:
        raise VtoAgentError(f"Sigmoi response missing prompt.user: {sigmoi_response}")

    # Identity anchor for Gemini. Sigmoi doesn't get the identity fields —
    # it would just pay generation tokens to repeat them — so this is where
    # gender / single-subject is enforced. Gemini respects textual prompts
    # heavily; making the constraint un-missable prevents subject drift.
    identity_anchor = (
        f"Render exactly ONE person — the same {identity['gender_identity']} "
        f"shown in the reference photo. Do not change gender, do not generate "
        f"multiple people, preserve face and body proportions from the headshot."
    )
    p_user = f"{identity_anchor}\n\n{p_user}"

    headshot_path = headshot_loader(user_id)
    image_bytes, mime_type = gemini_caller(p_system, p_user, headshot_path)

    _save_debug(
        session_id=session_id,
        turn_id=turn_id,
        user_id=user_id,
        request=request,
        sigmoi_user_prompt=sigmoi_user_prompt,
        sigmoi_response=sigmoi_response,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    scene = sigmoi_response.get("scene") or {}
    return {
        "image_b64": base64.b64encode(image_bytes).decode("ascii"),
        "image_mime": mime_type,
        "description": _compose_description(scene),
        "scene": scene,
        "sigmoi_response": sigmoi_response,
    }
