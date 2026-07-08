# API Service — Plan

## Goal
Shared backend FastAPI service. Phase 1 covers read-only access to demo
user profiles for the Stylist Master / Style / VTO agents and the frontend
profile picker. Future phases extend the same service with product, search,
and other shared backend endpoints.

## Phase 1 (this branch)
| Task | Status |
|---|---|
| Scaffold `app/` package (`main.py`, `models.py`, `attributes.py`, `repository.py`) | completed |
| Implement `GET /users` (picker list) | completed |
| Implement `GET /users/{user_id}?attributes=` with attribute filter | completed |
| Implement `GET /attributes` (self-documenting) | completed |
| Stub CRUD endpoints (`POST/PUT/PATCH/DELETE`) returning 501 | completed |
| PLAN.md, changelog.md, README.md, CLAUDE.md update | completed |
| Smoke test against the 4 fixture profiles | completed |
| Rename component `backend/database` → `backend/api` | completed |

## Phase 2

| Task | Status | Notes |
|---|---|---|
| `POST /users/{user_id}/episodes` create endpoint | ⏳ pending | Needed by stylist orchestrator for atomic episode persistence. Should accept `request.json + style.json + vto.json + vto.png` as a single multipart payload and write the bundle atomically. Until this lands, stylist writes to filesystem directly under `profiles/{user_id}/episodes/`. |
| Implement remaining CRUD handlers (replace/patch/delete) | ⏳ pending | Write to disk for now; move to S3-backed storage when infra is up. |
| Real photo URLs in `photo_observations.json` | ✅ done (2026-05-10) | All four demo users now have headshot + 4 outfit photos under `profiles/<user>/photos/`. The `image_url: null` stub fields can be patched to point at these next. |
| Episode and evidence-level read endpoints | ⏳ pending | Currently only `derived/` and the profile photo are exposed. |
| Auth + caching + pagination | ⏳ pending | When profile count grows. |

## Open questions / dependencies
- Final hosting target (Lambda) — service is plain ASGI so it should drop in
  via Mangum without rework.
- Whether other agents should call this service over HTTP or import the
  repository module directly. Default plan: HTTP, to keep the microservice
  boundary clean.
- Episode create endpoint payload shape — multipart vs JSON+base64. Likely
  multipart since `vto.png` can be ~700KB; cleaner over the wire.
