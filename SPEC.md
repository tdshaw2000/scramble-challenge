# Scramble Challenge — Build Spec

## Overview

A live, multiplayer scramble-timing party game. One player (the **Challenge Owner**, CO) starts a challenge and gets a shareable link. Others join via that link, entering a name to identify themselves. The CO picks a puzzle and starts a round; everyone gets the same scramble, times their own solve in-browser (WCA-style inspection + stopwatch), and results appear live as a leaderboard. Repeat for as many rounds as the group wants.

This is a spiritual sibling to tnoodle-scratch but a new project, not an extension of it — it reuses TNoodle for scramble generation but the interaction model (live, multiplayer, real-time) is entirely new.

**Stack**
- **Backend:** Flask + Flask-SocketIO (real-time is the core new technical challenge here — no precedent in tnoodle-scratch)
- **Scrambles:** TNoodle JAR, called the same way tnoodle-scratch already does
- **Identity:** cookie-based, no passwords — a device-bound ID paired with a self-chosen display name, scoped per challenge
- **Persistence:** a real database is now in scope (rounds/solves need to survive restarts, and future history/recall depends on it)
- **Hosting:** OCI Always Free (Ampere A1), Docker Compose — per existing setup, not revisited here

**Honour system.** No anti-cheat, no solve verification. Times are self-timed and self-reported by design — this is a bit of fun, not a sanctioned competition.

## Data model

**Challenge**
- `id` (uuid, primary key)
- `slug` (short, url-safe, used in the shareable link — distinct from `id` so links can be short/friendly while ids stay stable)
- `co_player_id` (FK → Player)
- `status`: `waiting` | `round_active` | `round_results` (mirrors the CO's screen state — see Lifecycle)
- `current_round_id` (FK → Round, nullable)
- `created_at`

**Player**
- `id` (uuid, primary key)
- `challenge_id` (FK → Challenge)
- `cookie_id` (the device-bound identity — see Overview)
- `display_name`
- `is_co` (bool)
- `connected` (bool — tracks live socket connection, drives the dynamic Players list)
- `joined_at`
- *(future, not v1): `wca_id`, `avatar_url`*

**Round**
- `id` (uuid, primary key)
- `challenge_id` (FK → Challenge)
- `round_number` (sequential within the challenge, starting at 1)
- `puzzle` (e.g. `333` — TNoodle event code; round 1 always `333`)
- `scramble_text` (from TNoodle, generated once when the round starts, fixed for the round)
- `scramble_svg` (rendered image, generated alongside the text)
- `status`: `active` | `complete`
- `started_at`, `ended_at` (`ended_at` set either when everyone has finished naturally or when the CO hits End Round)

**Solve**
- `id` (uuid, primary key)
- `round_id` (FK → Round)
- `player_id` (FK → Player)
- `time_ms` (nullable — null means DNF)
- `result`: `ok` | `dnf`
- `started_inspection_at`, `started_solve_at`, `finished_at` (raw timestamps — useful for later, e.g. inspection-overrun penalties if ever added; not used for anything in v1 beyond computing `time_ms`)

One `Solve` row per (round, player) — created when a player presses Start Inspection, filled in when they stop the timer, left with `time_ms = null, result = dnf` if the round ends before they finish.

## Lifecycle

**Challenge creation**
1. CO enters name on landing page, presses "Start new challenge" → `Challenge` row created (`status: waiting`), `Player` row created for CO (`is_co: true`), cookie set.
2. CO's browser shows: shareable link, puzzle dropdown (defaulted to `333`) + "Start round" button, and the live Players list (just themselves so far).

**Joining**
1. Friend opens the link → prompted for a name if they don't already have a cookie for this challenge → `Player` row created, cookie set, joins the challenge's socket room.
2. Everyone currently viewing the waiting/results screen (CO included) sees the Players list update live.
3. If a challenge is `round_active` when someone joins, they join the current round too (see "Mid-round joins" below) rather than waiting.

**Starting a round**
1. Only the CO can do this, and only from `waiting` or `round_results` status.
2. CO selects puzzle (default: `333` for round 1, otherwise whatever was used last round) and presses "Start round."
3. Server generates a scramble via TNoodle, creates the `Round` row (`status: active`), sets `Challenge.status = round_active` and `current_round_id`.
4. All connected players' screens switch to: scramble text + image, "Start inspection" button.

**Per-player solve flow** (independent per player — no synchronised countdown across players)
1. Player scrambles their physical puzzle, presses "Start inspection" → 15→0 countdown, screen otherwise blank.
2. A press anywhere starts the solve timer. If the countdown reaches 0 first, the attempt is a DNF (a house rule, simpler than WCA's +2-then-DNF).
3. A subsequent press anywhere stops it → `Solve` row filled with `time_ms`, `result: ok`.
4. Player's screen returns to the Players list / live leaderboard for this round.

**Mid-round joins.** A player joining while a round is `active` gets the current round's scramble immediately and can attempt it — not held back to the next round.

**Live leaderboard.** As each `Solve` completes, all players viewing the results screen see the list update and re-sort by time. Ties share the same position (e.g. two players tied for 1st are both shown as "1st").

**Round end.** A round ends when either:
- every connected player has a completed `Solve` (`ok` or `dnf`), or
- the CO presses **End Round** (emergency stop) — any player without a recorded time at that point gets `result: dnf, time_ms: null`.

Either way: `Round.status = complete`, `ended_at` set, `Challenge.status = round_results`. The CO's screen returns to the puzzle dropdown + "Start round" button (dropdown now defaults to the puzzle just used), ready to repeat.

**Points.** Winning a round is worth one point, and points add up across the challenge. Everyone tied for first gets a point; a round where everyone DNFs awards none. A round counts once it has ended. Points show in brackets after each player's name wherever it appears (players list, leaderboard, admin pages), e.g. "Amy (2)". They are worked out from the finished rounds, not stored.

**Disconnects.** A player who disconnects for any reason (closed tab, lost connection, refresh) mid-round simply misses that round — no reconnect-into-timer logic. They can rejoin for the next round normally.

**CO leaves.** If the CO disconnects, the challenge ends — no ownership transfer in v1. This is an accepted limitation, not a bug to design around.

## Socket event contract

One room per challenge (room name = `Challenge.slug` or `id`). REST endpoints handle the initial page load / cookie-and-name entry; everything after that is sockets.

**Client → Server**

| Event | Payload | Who | Effect |
|---|---|---|---|
| `join_challenge` | `{ challenge_slug, cookie_id, display_name }` | anyone | Joins room; creates `Player` if new; broadcasts `player_list` |
| `start_round` | `{ puzzle }` | CO only | Generates scramble, creates `Round`, broadcasts `round_started` |
| `start_inspection` | `{}` | player, during `round_active` | Records `started_inspection_at` |
| `start_solve` | `{}` | player, mid-inspection | Records `started_solve_at` (client-side inspection countdown; this just marks the transition) |
| `inspection_expired` | `{}` | player, mid-inspection | Countdown reached 0: fills `Solve` (`result: dnf`), broadcasts `leaderboard_update` |
| `stop_solve` | `{ time_ms }` | player, mid-solve | Fills `Solve` (`time_ms`, `result: ok`), broadcasts `leaderboard_update` |
| `end_round` | `{}` | CO only | Force-ends round: unfinished players marked `dnf`, broadcasts `round_complete` |

**Server → Client**

| Event | Payload | Sent to | When |
|---|---|---|---|
| `player_list` | `[{ player_id, display_name, is_co, connected, points }]` | room | Any join/leave/disconnect, and after `round_complete` |
| `round_started` | `{ round_id, round_number, puzzle, puzzle_name, scramble_text, scramble_svg_url }` | room | CO starts a round |
| `leaderboard_update` | `{ round_id, results: [{ player_id, display_name, time_ms, result, position, points }] }` | room | Any solve completes (live reordering) |
| `round_complete` | `{ round_id, results: [...] }` | room | All finished, or CO ends round early |
| `challenge_ended` | `{}` | room, or one page joining an ended challenge | The challenge ends (today: the CO doesn't come back within the grace period). The page reloads and lands on the summary |

Note: `time_ms` is sent by the client in `stop_solve` — this is fine and consistent with the honour-system stance (no server-side timing enforcement). If that ever changes, the fix is server-side timestamping on `start_solve`/`stop_solve` receipt rather than trusting the client payload — worth a one-line comment in the code flagging this as the trust boundary, so it's an easy toggle later even though v1 doesn't need it.

## Screens

**Landing (everyone)** — name entry field, then either "Start new challenge" (if arriving at the root URL) or "Join" (if arriving via a challenge link, in which case the challenge slug is already known from the URL).

**Waiting room (all players, between rounds)**
- Players list (live, name + connected status)
- CO only, additionally: shareable link with a "Share" button (the phone's share sheet; copies the link where sharing isn't available), puzzle dropdown, "Start round" button
- Non-CO players: just see the list and a "waiting for the challenge owner to start a round" message

**Scramble reveal (all players, on `round_started`)**
- Scramble text + rendered image (from TNoodle, same rendering tnoodle-scratch already does)
- "Start inspection" button

**Inspection (per player, after they press Start inspection)**
- Screen goes blank except a large 15→0 countdown
- Tap/click anywhere transitions to solving. On a keyboard, hold Space and let go to start (like a real cubing timer)

**Solving (per player)**
- Blank screen, timer running (not displayed live — WCA convention is you don't watch your own time tick up, it's distracting; just a solving indicator)
- Tap/click anywhere, or press Space, stops the timer, submits `stop_solve`, returns to leaderboard

**Leaderboard / results (all players, during and after a round)**
- Sorted list: position, name, time (or DNF), live-updating as solves come in
- CO only, additionally: "End round" button (visible whenever the round is still active) and, once the round is complete, the puzzle dropdown + "Start round" button to begin the next one

**Challenge summary (everyone, once the challenge has ended)** — at `/c/<slug>/summary`
- Opens with "This challenge has ended", then the final standings (everyone by points, most first, ties sharing a place and listed by name), then each round in order: puzzle, scramble text and picture, and its results. Names carry final points, e.g. "Amy (2)". A "Start a new challenge" link goes to the landing page.
- Depends only on the challenge having ended, not on how it ended, so any future way of ending (e.g. a manual "End challenge") gets the same page.
- Anyone with the link can see it. Once a challenge has ended, its challenge link and join form lead here. Before that, the summary address leads back to the challenge.

## Rules reference

- **Same scramble per round, always.** Generated once when the round starts, stored on the `Round`, never regenerated per player.
- **One attempt per player per round.** No retries within a round.
- **Ties share position.** Two players whose `time_ms` match to the hundredth (times are truncated, not rounded, as in WCA results) both get the same rank number (e.g. both shown as 1st); the next distinct time takes the rank after (1, 1, 3 — not 1, 1, 2).
- **DNF.** No separate DNF button/flow — it's simply what a player ends up with if the round is force-ended (via CO's End Round) before they stop their timer, if they disconnect mid-round, or if their inspection countdown reaches 0. Shown as "DNF" in the leaderboard, sorted after all timed results.
- **Puzzle defaults.** Round 1 of any challenge always defaults to 3x3 (`333`). Round 2 onward defaults to whatever puzzle was used in the immediately preceding round. CO can always override via the dropdown.
- **Puzzle list.** The WCA puzzles TNoodle scrambles, without variants: 2x2 to 7x7, Pyraminx, Skewb, Square-1, Megaminx and Clock. The blindfolded (`333ni`, `444ni`, `555ni`), fewest-moves (`333fm`) and fast-4x4 (`444fast`) variants are deliberately left out. The dropdown and round heading show names ("Megaminx"); events and the database use TNoodle codes (`minx`).

## Future enhancements (explicitly out of v1 scope)

- **Round history/recall.** Persist all challenges/rounds/solves for later review (schema already supports this — v1 just needs a way to browse it, e.g. an admin-only view).
- **WCA ID → avatar.** Optional field on join; if present, look up and display the player's WCA avatar. Purely cosmetic, no effect on gameplay logic.
- **Async mode.** A genuinely different interaction model, not a toggle on this one: same challenge link, but players attempt a round whenever they're free rather than all being live simultaneously (closer to the original daily-challenge concept this project evolved from). Would reuse the `Challenge`/`Round`/`Solve` model but replace the socket-driven live flow with an open-window-per-round approach. Treat as a separate build once live mode is solid, not a day-one requirement.
