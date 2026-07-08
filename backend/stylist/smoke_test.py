"""Smoke test for the stylist orchestrator.

Multi-turn end-to-end exercise via in-process FastAPI TestClient (no
uvicorn needed). Covers:

  1. Greeting       → hardcoded chat reply
  2. Style ask      → style sub-agent → outfit card
  3. VTO follow-up  → vto sub-agent → image_b64
  4. Thumb-down + re-ask → rejected_styles flows into next style request

Prerequisites:
- ``backend/inference`` server running locally (Sigmoi for both sub-agents).
- ``GEMINI_API_KEY`` set (for the VTO step).

Usage:
    python -m backend.stylist.smoke_test
"""

from __future__ import annotations

import base64
import json
import sys
from typing import Any

from fastapi.testclient import TestClient

# Monkey-patch the style agent's profile loader to go through the API
# in-process via TestClient. In production the stylist talks to backend/api
# over HTTP; for the smoke we keep everything in one process.
import backend.style.agent as _style_agent
from backend.api.app.main import app as _api_app

_api_client = TestClient(_api_app)


def _in_process_profile_loader(user_id: str) -> dict:
    r = _api_client.get(
        f"/users/{user_id}",
        params={"attributes": "identity,body,style_signals,behaviour,context"},
    )
    r.raise_for_status()
    return r.json()


_style_agent.fetch_profile_http = _in_process_profile_loader
# style_run's default arg was bound at def time — patch it explicitly.
_style_agent.run.__kwdefaults__["profile_loader"] = _in_process_profile_loader

from backend.stylist.app.main import app  # noqa: E402  (after monkey-patch)
from backend.stylist.app.sessions import store  # noqa: E402

SESSION_ID = "smoke_session"
USER_ID = "usr_006_jamie"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


def _fail(msg: str) -> None:
    print(f"[smoke] FAIL — {msg}", file=sys.stderr)
    sys.exit(1)


def _post(client: TestClient, message: str, signals: list[dict[str, str]] | None = None) -> dict[str, Any]:
    payload = {"session_id": SESSION_ID, "user_id": USER_ID, "message": message}
    if signals:
        payload["signals"] = signals
    r = client.post("/turn", json=payload)
    if r.status_code != 200:
        _fail(f"POST /turn returned {r.status_code}: {r.text}")
    return r.json()


def main() -> None:
    # Reset the session store so re-runs start clean.
    store.reset(SESSION_ID)

    client = TestClient(app)

    # --- 1) Greeting ---
    print("[smoke] turn 1: greeting")
    resp = _post(client, "hi")
    if resp["type"] != "chat":
        _fail(f"greeting expected chat, got {resp['type']!r}")
    if "Raven" not in resp["text"]:
        _fail(f"greeting reply missing 'Raven': {resp['text']!r}")
    print(f"[smoke]   {resp['text']!r}")

    # --- 2) Style ask ---
    print()
    print("[smoke] turn 2: style ask")
    resp = _post(
        client,
        "I've got a friend's birthday next week — dinner then bars. Want to look sharp but not flashy.",
    )
    if resp["type"] != "outfit":
        _fail(f"style ask expected outfit, got {resp['type']!r}: {resp['text']!r}")
    card = resp["outfit_card"]
    if not card or not card.get("label") or not card.get("pieces"):
        _fail(f"outfit_card missing or empty: {card!r}")
    print(f"[smoke]   text:  {resp['text']!r}")
    print(f"[smoke]   label: {card['label']!r}")
    print(f"[smoke]   pieces: {len(card['pieces'])}")

    first_outfit_label = card["label"]

    # --- 3) VTO follow-up ---
    print()
    print("[smoke] turn 3: VTO follow-up")
    resp = _post(client, "show me what that looks like on me")
    if resp["type"] != "vto":
        _fail(f"VTO ask expected vto, got {resp['type']!r}: {resp['text']!r}")
    vto = resp["vto"]
    if not vto or not vto.get("image_b64"):
        _fail("vto block missing image_b64")
    img_bytes = base64.b64decode(vto["image_b64"])
    if not (img_bytes.startswith(PNG_MAGIC) or img_bytes.startswith(JPEG_MAGIC)):
        _fail(f"image_b64 didn't decode to image (first bytes: {img_bytes[:8]!r})")
    if vto.get("image_mime") not in ("image/jpeg", "image/png"):
        _fail(f"unexpected image_mime: {vto.get('image_mime')!r}")
    print(f"[smoke]   text: {resp['text']!r}")
    print(f"[smoke]   image_mime: {vto['image_mime']}")
    print(f"[smoke]   image bytes: {len(img_bytes)}")
    print(f"[smoke]   description: {vto['description']!r}")

    # --- 4) Thumb-down + re-ask: rejected_styles must flow into next style ---
    print()
    print("[smoke] turn 4: thumb-down previous outfit + re-ask")
    resp = _post(
        client,
        "give me a different angle on this — same occasion",
        signals=[{"kind": "thumb_down", "label": first_outfit_label}],
    )
    if resp["type"] != "outfit":
        _fail(f"re-ask expected outfit, got {resp['type']!r}: {resp['text']!r}")
    new_card = resp["outfit_card"]
    if not new_card.get("label"):
        _fail("re-ask outfit_card missing label")
    print(f"[smoke]   text:  {resp['text']!r}")
    print(f"[smoke]   label: {new_card['label']!r}")

    # Verify the rejected_styles list now has the first outfit's label
    session = store.get_or_create(SESSION_ID, USER_ID)
    rejected_labels = [r["label"] for r in session.rejected_styles]
    if first_outfit_label not in rejected_labels:
        _fail(
            f"first outfit label not added to rejected_styles. "
            f"rejected: {rejected_labels}"
        )
    print(f"[smoke]   session.rejected_styles labels: {rejected_labels}")

    # Sanity: the new label should ideally differ from the rejected one. Not a
    # hard requirement for the smoke (sampling can reproduce), but worth noting.
    if new_card["label"] == first_outfit_label:
        print(
            "[smoke]   note: new outfit has same label as rejected — sampling collision",
            file=sys.stderr,
        )

    # Conversation grew correctly: 4 user turns + 4 assistant turns = 8.
    if len(session.conversation) != 8:
        _fail(f"expected 8 conversation entries, got {len(session.conversation)}")
    print(f"[smoke]   conversation length: {len(session.conversation)}")

    print()
    print("[smoke] PASS")


if __name__ == "__main__":
    main()
