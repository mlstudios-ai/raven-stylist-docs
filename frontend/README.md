# Frontend

Demo client for the Raven AI Stylist — a conversational UI for picking a
persona profile, asking for style guidance, and seeing the result as an
outfit card in chat plus a virtual try-on image in the left canvas.

> **Status:** scaffolding stage. Spec is in `CLAUDE.md`; mockups are in
> `../docs/ui/screens/`. App code is not yet committed.

## Stack

- Next.js (SPA usage)
- Tailwind CSS — espresso palette
- Image assets in `./images/`

## Layout at a glance

```
┌──────────────────────────────────────────────────────────┐
│  RAVEN — AI STYLIST DEMO              Profile: [▾]       │
├────────────────────────────────────┬─────────────────────┤
│         VTO canvas (hero)          │  Chat               │
│         empty / loading / image    │  text + outfit cards│
│                                    │  [ input box  ↑ ]   │
└────────────────────────────────────┴─────────────────────┘
```

See mockups: `../docs/ui/screens/landing-screen.png`,
`profile-selection-screen.png`, `main-screen.png`.

## How it talks to the backend

The frontend is a thin client over the stylist orchestrator. One chat
turn = one HTTP call to `backend/stylist`; the orchestrator returns a
payload that may contain (chat text, outfit card data, VTO image) in any
combination, and the frontend renders accordingly.

The **only** other backend it touches directly is `backend/api` — and only
to populate the profile picker before a session exists.

```
frontend
  ├── POST  →  backend/stylist     (every chat turn)
  └── GET   →  backend/api/users   (profile picker only)
```

It does **not** call `backend/style`, `backend/vto`, or
`backend/inference` — those are sub-agents the orchestrator coordinates.

## Key behaviours

- **Profile = session.** Picking or switching a profile resets chat, the
  VTO canvas, and allocates a new session id. No login.
- **Outfit cards.** Style recommendations land in chat as cards with
  mini item cards inside (role / category / color / styling note);
  informational, non-clickable.
- **Thumbs feed the next request.** Up/down on either the outfit card or
  the VTO image goes into the session's liked/rejected lists, which the
  orchestrator passes to the next style call. Flagged items stay visually
  marked for the rest of the session.
- **VTO canvas auto-updates.** Whenever the orchestrator returns a new
  VTO image, the canvas replaces what's there. Includes a loading state
  for the 5–15s Gemini Flash call.

## Running locally (planned)

Once the app is scaffolded, expect something like:

```sh
# in frontend/
npm install
npm run dev          # http://localhost:3000
```

Backend prerequisites for an end-to-end run:

| Service | Path | Default port |
|---|---|---|
| Stylist orchestrator | `backend/stylist` | TBD |
| Profile API | `backend/api` | 8001 |
| Inference (model) | `backend/inference` | 8080 |

The orchestrator owns the chain — frontend doesn't need to know about the
others.

## Out of scope for the demo

- Voice input
- User-supplied images (VTO uses the profile photo from `backend/api`)
- Authentication / sign-up

These are deliberately left out so the demo focuses on the
personalisation story. See `CLAUDE.md` for the full design spec and the
forward path.

## Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | Full design spec — read this before building or changing UI behaviour. |
| `README.md` | This file. |
| `images/` | Static image assets. |
