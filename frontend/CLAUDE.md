# Frontend — Raven AI Stylist

Single-page web app. Demo client for the Raven multi-agent system.

## Stack

- Next.js (SPA usage)
- Tailwind CSS (espresso palette — tokens added later)
- Image assets in `./images`

Aim: sleek, professional UI/UX.

## Layout

Fixed two-pane split under a top header.

```
┌──────────────────────────────────────────────────────────┐
│  RAVEN — AI STYLIST DEMO              Profile: [▾]       │
├────────────────────────────────────┬─────────────────────┤
│                                    │  Ask Raven          │
│         VTO canvas                 │  ┌───────────────┐  │
│         (left, hero)               │  │ chat stream   │  │
│                                    │  │ + outfit cards│  │
│                                    │  └───────────────┘  │
│                                    │  [ input box  ↑ ]   │
└────────────────────────────────────┴─────────────────────┘
```

- **Header**: app name + profile selector (top-right).
- **Left pane**: VTO canvas (hero). Renders the latest VTO image. Empty
  state, loading state, image state.
- **Right pane**: chat ("Ask Raven"). User turns + assistant turns +
  outfit cards inline.

## Profile picker

Modal opened from the header dropdown.

- Profile list is fetched from `backend/api` (`GET /users` returns
  `{user_id, name, archetype, photo}` per entry). The names shown in the
  current mockup (Tom Smith / Sarah Belle / Michelle Kim / Lara Minh) are
  placeholders — final names come from the API.
- Selecting an entry on the left fills the right-hand detail card. Detail
  card content is judgement-led but should communicate *why this persona
  styles differently*: profile photo, full name, archetype + personality
  with a one-line description (the persona JSON's `think` fields are good
  source material), style palette chips, and 2–3 hallmark style signals
  (e.g. from `style_signals.aesthetic_tags_inferred`). Keep it scannable.
- "Select" confirms. **Selecting a profile starts a new session**
  (see *Session lifecycle*).

## Session lifecycle

- One session = one selected profile.
- Switching the profile from the header dropdown **resets everything**:
  clears chat, clears VTO canvas, allocates a new session id, drops all
  outfit/VTO verdicts, and drops the queue of pending thumbs-up/down
  signals. Every piece of session-scoped state is cleared in
  `resetSession` in `app/page.tsx` — keep that callsite the single source
  of truth.
- No login. The demo is "select-user-only". Real auth is a later phase.

## Chat panel

Two kinds of assistant turns:

1. **Plain text** — clarifying questions, conversational replies. Rendered
   as a normal chat bubble.
2. **Outfit card** — the synthesised style recommendation. Rendered inline
   in the chat stream as a card containing:
   - **Label** (the recommendation's `label`).
   - **Brief explanation** (a short prose synthesis of `logic_summary` /
     `analysis.why_this_works_now` — the orchestrator decides the wording).
   - **Mini item cards**, one per piece in `recommendations[0].pieces`:
     `role`, `category`, `color`, `styling_note`. Sized to fit the chat
     panel width; non-clickable; informational only.
   - **Thumbs up / thumbs down** controls on the card (see *Feedback signals*).

Item cards must not link out — the user can't navigate into a piece. The
card is a static visual rendering of the model's structured output.

## VTO canvas (left pane)

- **Empty state**: copy along the lines of *"Style guides appear in chat.
  Ask Raven to show you."*
- **Loading state**: spinner / skeleton in the espresso palette while a VTO
  call is in flight (Gemini Flash typically 5–15s). Without this the demo
  reads as broken during generation. The frontend speculatively flips to
  loading on plausible VTO phrasing ("show me", "try", "render", …) and
  reverts if the backend response carries no `vto`.
- **Image state**: the returned VTO image, full-bleed in the pane, with
  overlay controls in a corner: thumbs up, thumbs down, fullscreen.
  Default fit is `object-contain` so the full headshot+outfit is visible;
  the user can toggle to fill mode.
- **Auto-update**: whenever the orchestrator returns a new VTO image, the
  canvas replaces its current content and `vtoVerdict` resets. The
  frontend doesn't decide when to show VTO — it just renders whatever the
  latest VTO output is.

## Multi-action turns

A single `/turn` response can carry **both** an `outfit_card` and a `vto`
image (e.g. *"show me a different style"* triggers a new style **and** a
new render). The frontend reads the two fields independently — it does
not assume the response shape. The chat appends an outfit message when
`outfit_card` is present; the canvas updates when `vto` is present.

## Feedback signals

Thumbs up / thumbs down appear in two places:

- On the outfit card in chat (controlled, toggleable — clicking the same
  thumb twice neutralises it).
- On the VTO image in the left pane (separate state from the cards;
  resets every time a new image lands).

State keying:

- **Card verdicts** (`verdicts`) are keyed by **chat-message id**, not by
  outfit label. Two outfit cards that happen to share a label do not share
  verdict state. The card UI carries the label only so the queued signal
  goes to the backend with the right label.
- **VTO verdict** (`vtoVerdict`) is a single value tied to the currently
  displayed image. It clears on every new image and on profile switch.
- **Pending signals** (`pendingByLabel`) are keyed by label so toggling
  the same label before send replaces rather than duplicates. They are
  flushed on the next `/turn` call and cleared on profile switch.

Both surfaces feed the same session-scoped `liked_styles` /
`rejected_styles` lists, which the orchestrator includes in the next
style/vto request.

## Backend boundary

The frontend talks **only** to the stylist orchestrator
(`backend/stylist`). It does not call `backend/style`, `backend/vto`, or
`backend/inference` directly. The orchestrator returns a payload
containing whatever combination of (chat text, outfit card data, VTO image)
the turn produced; the frontend renders accordingly.

Profile data is the one exception: the picker reads `backend/api/users`
directly because it has to populate the picker before any session exists.

## Out of scope for the demo

- Voice input (mic icon currently in mockup — remove)
- User image upload (image icon currently in mockup — remove). The VTO
  pipeline uses the user's profile photo from `backend/api`; a later
  phase will let users supply their own.
- Authentication / sign-up

## Multi-recommendation note

The current style output schema caps `recommendations` at 1 due to
training-time token limits. The downstream pipeline already supports more,
and a future phase will surface multiple options in chat. Build the outfit
card so adding sibling cards in the same chat turn is a styling change,
not a structural one.
