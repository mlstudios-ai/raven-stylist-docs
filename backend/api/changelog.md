# API Service — Changelog

## Unreleased
### Changed
- Renamed component from `backend/database` to `backend/api`. Service is
  intended to host shared backend endpoints, not just profile data. Module
  paths updated: `backend.api.app.main:app`.

### Added
- Initial FastAPI service (`app/`) with read endpoints:
  - `GET /attributes` — list supported attribute keys.
  - `GET /users` — list users with name, archetype, profile photo.
  - `GET /users/{user_id}?attributes=` — fetch a single user with caller-
    selectable attributes. Always-on minimum: identity, archetype,
    personality, photos.
- CRUD stubs (`POST /users`, `PUT/PATCH/DELETE /users/{user_id}`) reserved for
  phase 2; they return `501 Not Implemented` but advertise their request
  models in OpenAPI.
- Attribute mapping table (`app/attributes.py`) decouples user-facing keys
  from on-disk JSON paths, so internal layout can change without breaking
  API consumers.
- Domain objects (`Profile`, `Persona`, `PhotoList`, `UserRecord`) wrap the
  three on-disk files.
- Photo entries are returned with an `image_url: null` stub field; real URLs
  will arrive when images are produced.
