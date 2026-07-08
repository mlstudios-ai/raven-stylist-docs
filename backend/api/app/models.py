"""Domain objects wrapping the on-disk JSON files.

A ``UserRecord`` composes a ``Profile``, a ``Persona``, and a ``PhotoList``.
The objects are thin: they hold the parsed dict and expose ``.get(json_path)``
helpers used by the attribute resolver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .attributes import ATTRIBUTES, Source, AttributeSpec


@dataclass
class _JsonDoc:
    data: dict[str, Any]

    def get(self, json_path: str) -> Any:
        cur: Any = self.data
        for part in json_path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur


class Profile(_JsonDoc):
    """Wraps profile.json."""


class Persona(_JsonDoc):
    """Wraps persona.json."""


@dataclass
class PhotoList:
    photos: list[dict[str, Any]]

    @property
    def profile_photo(self) -> dict[str, Any] | None:
        return self.photos[0] if self.photos else None


@dataclass
class UserRecord:
    user_id: str
    profile: Profile
    persona: Persona
    photo_list: PhotoList

    def to_dict(self, attribute_keys: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {"user_id": self.user_id}
        for key in attribute_keys:
            spec = ATTRIBUTES[key]
            out[key] = self._render(spec)
        return out

    def _render(self, spec: AttributeSpec) -> Any:
        if spec.source is Source.PHOTOS:
            return [
                _with_image_url(p, self.user_id, idx == 0)
                for idx, p in enumerate(self.photo_list.photos)
            ]
        return None


def _with_image_url(photo: dict[str, Any], user_id: str, is_profile: bool) -> dict[str, Any]:
    """Backfill ``image_url`` so the frontend can fetch the file.

    First photo per user is the profile photo (the canonical headshot served
    as ``photos/headshot.png``). The remaining photos use ``photos/{photo_id}.png``
    — the generation script writes them named exactly that.
    """
    if photo.get("image_url"):
        return photo
    if is_profile:
        image_url = f"/users/{user_id}/photos/headshot.png"
    else:
        photo_id = photo.get("photo_id")
        image_url = f"/users/{user_id}/photos/{photo_id}.png" if photo_id else None
    return {**photo, "image_url": image_url}
