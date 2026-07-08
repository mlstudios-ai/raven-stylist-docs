"""Smoke tests against the four fixture profiles.

Run from repo root:
    uv run pytest backend/api/tests -q
or:
    uv run python -m backend.api.tests.test_smoke
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import attributes as attr
from backend.api.app.main import app
from backend.api.app.repository import list_user_ids

EXPECTED_USER_IDS = {
    "usr_006_jamie",
    "usr_007_maya",
    "usr_025_lerato",
    "usr_034_youssef",
}

client = TestClient(app)


def test_fixture_profiles_present() -> None:
    assert set(list_user_ids()) == EXPECTED_USER_IDS


def test_list_attributes() -> None:
    r = client.get("/attributes")
    assert r.status_code == 200
    keys = {a["key"] for a in r.json()}
    assert "identity" in keys and "style_dna" in keys and "photos" in keys


def test_list_users_returns_picker_cards() -> None:
    r = client.get("/users")
    assert r.status_code == 200
    cards = r.json()
    assert {c["user_id"] for c in cards} == EXPECTED_USER_IDS
    for c in cards:
        assert c["name"], f"missing name for {c['user_id']}"
        assert c["archetype"], f"missing archetype for {c['user_id']}"


def test_get_user_minimum() -> None:
    r = client.get("/users/usr_007_maya")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "usr_007_maya"
    # always-on attributes appear
    for k in attr.always_on_keys():
        assert k in body, f"missing always-on key {k}"
    # non-always-on does not
    assert "body" not in body
    # identity sanity
    assert body["identity"]["name"] == "Maya Chen"
    assert body["archetype"]["name"] == "Creator"
    assert body["personality"]["primary"]["type"] == "Classic"


def test_get_user_with_filtered_attributes() -> None:
    r = client.get("/users/usr_007_maya", params={"attributes": "body,style_dna"})
    assert r.status_code == 200
    body = r.json()
    assert "body" in body and body["body"]["height_cm"] == 158
    assert "style_dna" in body and body["style_dna"]["palette_logic"]
    # always-on still included
    assert "identity" in body


def test_get_user_all_attributes() -> None:
    r = client.get("/users/usr_007_maya", params={"attributes": "all"})
    assert r.status_code == 200
    body = r.json()
    for k in attr.all_keys():
        assert k in body


def test_unknown_attribute_returns_400() -> None:
    r = client.get("/users/usr_007_maya", params={"attributes": "bogus"})
    assert r.status_code == 400
    assert "bogus" in r.json()["detail"]["unknown"]


def test_unknown_user_returns_404() -> None:
    r = client.get("/users/usr_does_not_exist")
    assert r.status_code == 404


def test_photo_image_url_stub() -> None:
    r = client.get("/users/usr_007_maya")
    photos = r.json()["photos"]
    assert photos and all(p["image_url"] is None for p in photos)


def test_crud_stubs_return_501() -> None:
    payload = {
        "user_id": "usr_new",
        "profile": {},
        "persona": {},
    }
    assert client.post("/users", json=payload).status_code == 501
    assert client.put("/users/usr_007_maya", json=payload).status_code == 501
    assert client.patch("/users/usr_007_maya", json={}).status_code == 501
    assert client.delete("/users/usr_007_maya").status_code == 501


if __name__ == "__main__":
    # ad-hoc runner without pytest
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all smoke tests passed")
