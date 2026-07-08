"""Smoke test for the style agent.

Verifies the full path: profile fetch (in-process FastAPI TestClient) →
template fill → real model call (local llama-server) → JSON parse →
schema sanity check.

Prerequisites:
- ``backend/inference`` server running locally. See backend/inference/README.md.
- Editable install of the repo (``uv pip install -e .`` from repo root).

Usage:
    python -m backend.style.smoke_test
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.api.app.main import app as api_app
from backend.style.agent import run

REPO_ROOT = Path(__file__).resolve().parents[2]
EPISODE_PATH = REPO_ROOT / "backend/api/profiles/usr_006_jamie/episodes/ep_010/request.json"
CONVERSATION_WINDOW = 3  # match training distribution

REQUIRED_TOP_LEVEL = ["intent", "context", "analysis", "recommendations"]
REQUIRED_RECOMMENDATION = ["label", "logic_summary", "pieces"]
REQUIRED_PIECE = ["role", "category", "color", "styling_note"]


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


def _validate(result: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_TOP_LEVEL if k not in result]
    if missing:
        _fail(f"missing top-level keys: {missing}")

    recs = result.get("recommendations")
    if not isinstance(recs, list) or not recs:
        _fail("recommendations is empty or wrong type")

    rec = recs[0]
    rec_missing = [k for k in REQUIRED_RECOMMENDATION if k not in rec]
    if rec_missing:
        _fail(f"recommendation missing keys: {rec_missing}")

    pieces = rec.get("pieces")
    if not isinstance(pieces, list) or not pieces:
        _fail("recommendation.pieces is empty or wrong type")

    for i, piece in enumerate(pieces):
        piece_missing = [k for k in REQUIRED_PIECE if k not in piece]
        if piece_missing:
            _fail(f"piece[{i}] missing keys: {piece_missing}")


def main() -> None:
    request = json.loads(EPISODE_PATH.read_text())
    user_id = request["user_id"]
    request["conversation"] = request.get("conversation", [])[-CONVERSATION_WINDOW:]

    print(f"[smoke] user_id={user_id}")
    print(f"[smoke] conversation_turns={len(request['conversation'])}")
    print(f"[smoke] liked_styles={len(request.get('liked_styles') or [])}")
    print(f"[smoke] rejected_styles={len(request.get('rejected_styles') or [])}")
    print("[smoke] calling style agent...")

    api_client = TestClient(api_app)
    result = run(user_id, request, profile_loader=_in_process_profile_loader(api_client))

    print()
    print(json.dumps(result, indent=2))
    print()

    _validate(result)
    print("[smoke] PASS")


if __name__ == "__main__":
    main()
