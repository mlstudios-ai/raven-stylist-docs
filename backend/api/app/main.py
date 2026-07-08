"""FastAPI app for the shared backend API service.

Phase 1 read endpoints (user profiles) are implemented; create/update/delete
endpoints are stubs that return 501 so the OpenAPI surface is reserved for
phase 2. Future phases will add product, search, and other shared endpoints
under the same app.

Run locally:
    uvicorn backend.api.app.main:app --reload --port 8001
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import attributes as attr
from .repository import UserNotFound, list_user_ids, load_user

PROFILES_ROOT = Path(__file__).resolve().parents[1] / "profiles"

app = FastAPI(
    title="Raven Backend API",
    description=(
        "Shared backend service. Phase 1: read-only access to demo user "
        "profiles. Future phases will add product, search, and other "
        "shared endpoints."
    ),
    version="0.1.0",
)

# Demo CORS — frontend hits this from localhost:3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- response / request models ----------

class AttributeInfo(BaseModel):
    key: str
    description: str
    always_on: bool


class UserCard(BaseModel):
    """Minimal user info for list / picker views."""
    user_id: str
    name: str | None = None
    archetype: str | None = None
    profile_photo: dict[str, Any] | None = None


class CreateUserRequest(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    profile: dict[str, Any]
    persona: dict[str, Any]
    photos: list[dict[str, Any]] | None = None


class UpdateUserRequest(BaseModel):
    profile: dict[str, Any] | None = None
    persona: dict[str, Any] | None = None
    photos: list[dict[str, Any]] | None = None


# ---------- helpers ----------

def _parse_attributes(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [a.strip() for a in raw.split(",") if a.strip()]


def _not_implemented() -> HTTPException:
    return HTTPException(
        status_code=501,
        detail="Not implemented — planned for phase 2.",
    )


# ---------- read endpoints ----------

@app.get("/attributes", response_model=list[AttributeInfo],
         summary="List supported attribute keys")
def list_attributes() -> list[AttributeInfo]:
    return [
        AttributeInfo(key=spec.key, description=spec.description,
                      always_on=spec.always_on)
        for spec in attr.ATTRIBUTES.values()
    ]


@app.get("/users", response_model=list[UserCard],
         summary="List users (for the profile picker)")
def list_users() -> list[UserCard]:
    cards: list[UserCard] = []
    for uid in list_user_ids():
        try:
            user = load_user(uid)
        except UserNotFound:
            continue
        cards.append(UserCard(
            user_id=user.user_id,
            name=(user.profile.get("identity.name")),
            archetype=(user.persona.get("archetype.name")),
            profile_photo=_photo_with_stub(
                user.photo_list.profile_photo, user_id=user.user_id
            ),
        ))
    return cards


@app.get("/users/{user_id}", summary="Get a user with selectable attributes")
def get_user(
    user_id: str,
    attributes: str | None = Query(
        None,
        description=("Comma-separated attribute keys. "
                     "Omit for minimum, pass `all` for everything. "
                     "See GET /attributes for valid keys."),
    ),
) -> dict[str, Any]:
    try:
        user = load_user(user_id)
    except UserNotFound:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")

    try:
        keys = attr.resolve(_parse_attributes(attributes))
    except KeyError as e:
        unknown = e.args[0]
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_attributes",
                "unknown": unknown,
                "valid": attr.all_keys(),
            },
        )

    return user.to_dict(keys)


# ---------- photo files ----------

@app.get(
    "/users/{user_id}/photos/{filename}",
    summary="Serve a photo file from the user's photos directory",
    response_class=FileResponse,
)
def get_photo(user_id: str, filename: str) -> FileResponse:
    # Defend against path traversal — only basename, no slashes.
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    path = PROFILES_ROOT / user_id / "photos" / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found.")
    return FileResponse(str(path))


# ---------- CRUD stubs (501) ----------

@app.post("/users", status_code=501, summary="Create user (not implemented)")
def create_user(_payload: CreateUserRequest) -> None:
    raise _not_implemented()


@app.put("/users/{user_id}", status_code=501,
         summary="Replace user (not implemented)")
def replace_user(user_id: str, _payload: CreateUserRequest) -> None:
    raise _not_implemented()


@app.patch("/users/{user_id}", status_code=501,
           summary="Patch user (not implemented)")
def patch_user(user_id: str, _payload: UpdateUserRequest) -> None:
    raise _not_implemented()


@app.delete("/users/{user_id}", status_code=501,
            summary="Delete user (not implemented)")
def delete_user(user_id: str) -> None:
    raise _not_implemented()


# ---------- internal ----------

def _photo_with_stub(
    photo: dict[str, Any] | None, user_id: str | None = None
) -> dict[str, Any] | None:
    """Backfill image_url for the picker card.

    Profile photo on disk is `headshot.png` per profile (see
    scripts/generate_profile_photos.py). Hardcode that filename — the
    photo_observations.json entries don't carry the canonical headshot
    id, but the file is consistent across all users.
    """
    if photo is None:
        return None
    image_url = photo.get("image_url")
    if not image_url and user_id:
        image_url = f"/users/{user_id}/photos/headshot.png"
    return {**photo, "image_url": image_url}
