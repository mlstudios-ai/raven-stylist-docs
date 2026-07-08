# API

Shared backend FastAPI service. Phase 1 exposes read-only access to demo
user profiles; create/update/delete are reserved as 501 stubs for phase 2.
This service will grow to host other shared backend functionality (products,
search, etc.) — it is not limited to profiles.

Profile folders are named after the `user_id` (e.g. `profiles/usr_007_maya/`)
and contain `derived/profile.json`, `derived/persona.json`, and
`evidence/photo_observations.json`.

## API
- `GET /users` — picker list (id, name, archetype, profile photo).
- `GET /users/{user_id}?attributes=key1,key2` — single user, attribute-filtered.
  Omit `attributes` for minimum, pass `attributes=all` for everything.
- `GET /attributes` — list supported attribute keys.
- `POST /users`, `PUT/PATCH/DELETE /users/{user_id}` — 501, phase 2.

## Known gap — episode create endpoint

The stylist orchestrator (`backend/stylist`) needs to write episode
bundles atomically to `profiles/{user_id}/episodes/{ep_id}/` containing
`request.json` + `style.json` + `vto.json` + `vto.png`. Until this
service exposes a `POST /users/{user_id}/episodes` create endpoint, the
orchestrator writes to the filesystem directly. Adding the endpoint is a
phase-2 task that lets the orchestrator switch from filesystem writes to
HTTP without changing its episode schema.

Always-on (minimum) attributes: `identity`, `archetype`, `personality`, `photos`.

## Attribute mapping
Caller-facing keys map to `(source file, JSON path)` in `app/attributes.py`.
Update that table — not the routes — when the on-disk layout changes.

## Photos
`photo_observations.json` is the source. Each photo gets an `image_url: null`
stub field until real images are produced.

## Run
```
uvicorn backend.api.app.main:app --reload --port 8001
```

See `README.md` for the full attribute table and examples.
See `PLAN.md` for status. See `changelog.md` for history.
