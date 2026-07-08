"""Smoke test for the VTO agent.

End-to-end: calls style agent for Jamie (in-process API via FastAPI
TestClient), then VTO agent with a "show me" prompt. Verifies image_b64
decodes to a valid PNG and a debug copy lands under backend/vto/output/.

Prerequisites:
- backend/inference server running locally (Sigmoi step). See
  backend/inference/README.md.
- GEMINI_API_KEY exported or present in .env (Gemini step).
- Editable install of the repo (uv pip install -e . from repo root).

Usage:
    python -m backend.vto.smoke_test
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.api.app.main import app as api_app
from backend.style.agent import run as style_run
from backend.vto.agent import VtoAgentError, VtoClarificationRequired, run as vto_run

REPO_ROOT = Path(__file__).resolve().parents[2]
EPISODE_PATH = REPO_ROOT / "backend/api/profiles/usr_006_jamie/episodes/ep_010/request.json"
CONVERSATION_WINDOW = 3
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

USER_ID = "usr_006_jamie"
SHOW_ME_PROMPT = "yeah show me what that looks like on me"


def _in_process_profile_loader(api_client: TestClient):
    def loader(user_id: str) -> dict[str, Any]:
        r = api_client.get(
            f"/users/{user_id}",
            params={"attributes": "identity,body,style_signals,behaviour,context"},
        )
        r.raise_for_status()
        return r.json()

    return loader


def _fail(msg: str) -> None:
    print(f"[smoke] FAIL — {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    print(f"[smoke] step 1: fetching style recommendation for {USER_ID}")
    style_request = json.loads(EPISODE_PATH.read_text())
    style_request["conversation"] = style_request.get("conversation", [])[-CONVERSATION_WINDOW:]

    api_client = TestClient(api_app)
    style_result = style_run(
        USER_ID, style_request, profile_loader=_in_process_profile_loader(api_client)
    )

    print(f"[smoke]   recommendation label: {style_result['recommendations'][0]['label']!r}")
    print(f"[smoke]   pieces: {len(style_result['recommendations'][0]['pieces'])}")

    print()
    print(f"[smoke] step 2: calling VTO agent")
    print(f"[smoke]   user_prompt: {SHOW_ME_PROMPT!r}")

    try:
        result = vto_run(
            USER_ID,
            request={"prompt": SHOW_ME_PROMPT, "style": style_result},
            session_id="smoke",
            turn_id="vto",
        )
    except VtoClarificationRequired as e:
        _fail(f"unexpected clarification needed: {e.question!r}")
    except VtoAgentError as e:
        _fail(str(e))

    print()
    print(f"[smoke]   description: {result['description']!r}")
    print(f"[smoke]   scene: {json.dumps(result['scene'], indent=2)}")

    image_bytes = base64.b64decode(result["image_b64"])
    if not (image_bytes.startswith(PNG_MAGIC) or image_bytes.startswith(JPEG_MAGIC)):
        _fail(f"image_b64 did not decode to PNG or JPEG (first 8 bytes: {image_bytes[:8]!r})")

    mime = result.get("image_mime")
    if mime not in ("image/jpeg", "image/png"):
        _fail(f"unexpected image_mime: {mime!r}")

    debug_dir = Path(__file__).resolve().parent / "output" / "smoke"
    debug_files = list(debug_dir.glob("vto.*")) if debug_dir.exists() else []
    debug_img = next((p for p in debug_files if p.suffix in {".jpg", ".png", ".webp"}), None)
    if debug_img is None:
        _fail(f"debug image not written under {debug_dir}")
    if debug_img.stat().st_size < 1024:
        _fail(f"debug image suspiciously small: {debug_img.stat().st_size} bytes")

    print()
    print(f"[smoke]   image_mime: {mime}")
    print(f"[smoke]   image_b64 length: {len(result['image_b64'])}")
    print(f"[smoke]   decoded image size: {len(image_bytes)} bytes")
    print(f"[smoke]   debug image: {debug_img}")
    print()

    if "sigmoi_response" not in result:
        _fail("missing sigmoi_response in output")
    sr = result["sigmoi_response"]
    for key in ("scene", "outfit", "prompt"):
        if key not in sr:
            _fail(f"sigmoi_response missing {key!r}")

    print("[smoke] PASS")


if __name__ == "__main__":
    main()
