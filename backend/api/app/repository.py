"""File-backed user repository.

Folders under ``profiles/`` are named exactly after the ``user_id``
(e.g. ``profiles/usr_007_maya/``). Each user has:

    derived/profile.json
    derived/persona.json
    evidence/photo_observations.json

The repository is read-only at this stage.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import Persona, PhotoList, Profile, UserRecord

PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"


class UserNotFound(Exception):
    pass


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_user_ids() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.name for p in PROFILES_DIR.iterdir() if p.is_dir())


@lru_cache(maxsize=128)
def load_user(user_id: str) -> UserRecord:
    user_dir = PROFILES_DIR / user_id
    if not user_dir.is_dir():
        raise UserNotFound(user_id)

    profile = Profile(_read_json(user_dir / "derived" / "profile.json"))
    persona = Persona(_read_json(user_dir / "derived" / "persona.json"))

    photos_path = user_dir / "evidence" / "photo_observations.json"
    photos_data = _read_json(photos_path) if photos_path.exists() else {}
    photos = photos_data.get("photos", []) or []

    return UserRecord(
        user_id=user_id,
        profile=profile,
        persona=persona,
        photo_list=PhotoList(photos=photos),
    )
