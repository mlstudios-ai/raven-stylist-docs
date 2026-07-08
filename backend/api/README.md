# API Service

Shared backend FastAPI service for the Raven prototype. Phase 1 exposes
read-only access to demo user profiles. Future phases will add product,
search, and other shared backend endpoints under the same service.

Profiles live on disk under `profiles/{user_id}/` — each folder is named
after the `user_id` exactly (e.g. `profiles/usr_007_maya/`). Each profile
contains:

```
profiles/{user_id}/
├── derived/
│   ├── profile.json
│   └── persona.json
└── evidence/
    └── photo_observations.json
```

## Run

```bash
uvicorn backend.api.app.main:app --reload --port 8001
```

OpenAPI docs: <http://localhost:8001/docs>

## Endpoints

### Implemented (phase 1, read-only)

| Method | Path | Description |
|---|---|---|
| `GET` | `/attributes` | List supported attribute keys + descriptions. |
| `GET` | `/users` | List users (id, name, archetype, profile photo) for the picker. |
| `GET` | `/users/{user_id}?attributes=...` | Return a single user with caller-selectable attributes. |

`attributes` is a comma-separated list. Omit it to get the minimum
(always-on) attributes. Pass `attributes=all` to get everything.

### Planned (phase 2, returns 501)

| Method | Path | Description |
|---|---|---|
| `POST` | `/users` | Create a new user. |
| `PUT` | `/users/{user_id}` | Replace a user. |
| `PATCH` | `/users/{user_id}` | Partially update a user. |
| `DELETE` | `/users/{user_id}` | Delete a user. |

## Examples

```bash
# Minimum — identity, archetype, personality, photos:
curl http://localhost:8001/users/usr_007_maya

# Add body + style_dna:
curl 'http://localhost:8001/users/usr_007_maya?attributes=body,style_dna'

# Everything:
curl 'http://localhost:8001/users/usr_007_maya?attributes=all'

# Picker list:
curl http://localhost:8001/users
```

## Layout

```
backend/api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app + routes
│   ├── models.py        # Profile, Persona, PhotoList, UserRecord
│   ├── attributes.py    # attribute key → source/path map
│   └── repository.py    # load_user(user_id), list_user_ids()
├── profiles/            # on-disk fixtures (read-only)
├── PLAN.md
├── changelog.md
└── README.md
```
