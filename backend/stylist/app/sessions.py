"""In-memory session store for the stylist orchestrator.

A session is one user interacting with one selected profile until they
switch profile or close the app. Profile switch = new session id and a
fresh entry here. Demo-grade: single-process, in-memory dict; no
persistence between server restarts.

A future phase will replace this with a backed store; the public surface
(``get_or_create``, ``reset``) stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    session_id: str
    user_id: str

    # Full active-session conversation. Sub-agent calls receive a trimmed
    # window (last ~3 turns) — that windowing happens at call time, not here.
    conversation: list[dict[str, str]] = field(default_factory=list)

    # Thumbs-up/down accumulating across the session. Each entry shape:
    # {"label": str, "reason": str}. Passed verbatim into style requests.
    liked_styles: list[dict[str, str]] = field(default_factory=list)
    rejected_styles: list[dict[str, str]] = field(default_factory=list)

    # Last sub-agent outputs — used so a "show me" turn can follow a style
    # turn without re-running style, and so signals can resolve labels.
    last_style: dict[str, Any] | None = None
    last_vto: dict[str, Any] | None = None

    # Monotonic per-session counter for turn ids in responses.
    turn_count: int = 0

    def append_user(self, text: str) -> None:
        self.conversation.append({"role": "user", "content": text})

    def append_assistant(self, text: str) -> None:
        self.conversation.append({"role": "assistant", "content": text})

    def next_turn_id(self) -> str:
        self.turn_count += 1
        return f"t{self.turn_count:03d}"


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str, user_id: str) -> Session:
        existing = self._sessions.get(session_id)
        if existing is None:
            self._sessions[session_id] = Session(session_id=session_id, user_id=user_id)
            return self._sessions[session_id]
        if existing.user_id != user_id:
            # Profile switch on the same session_id — reset.
            self._sessions[session_id] = Session(session_id=session_id, user_id=user_id)
            return self._sessions[session_id]
        return existing

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# Module-level singleton — single process, single store for the demo.
store = SessionStore()
