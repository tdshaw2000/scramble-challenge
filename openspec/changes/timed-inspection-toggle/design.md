# Design

## Context

Inspection timing is entirely client-driven today: the server trusts whatever `plus_two` and
`time_ms` the browser reports (per `solve-timing`'s client-trusted-timing requirement), and
`inspection_expired` just records a DNF whenever the browser decides 17 seconds passed. There is
currently no field anywhere that says whether a round is timed or untimed — the client's
inspection countdown in `app/static/challenge.js` always runs the same WCA logic. `Round` already
carries round-scoped settings (`puzzle`), so a round-scoped mode fits the existing shape; a
challenge-level or player-level setting would not, since the owner wants it changeable per round.

## Goals / Non-Goals

**Goals:**
- Let the CO flip timed inspection on/off per round, defaulting like the puzzle default.
- Keep the existing trust boundary: the server still doesn't independently verify inspection
  timing in either mode, it just stops enforcing the 15s/17s cutoffs when the round is untimed.
- Every player in a round sees the same mode consistently, including a late joiner or a
  reconnect mid-round.

**Non-Goals:**
- No per-player override of a round's mode — it's one setting for the whole round, same as puzzle.
- No change to the +2/DNF honour-system trust model itself.
- No retroactive change to already-completed rounds or their stored results.

## Decisions

- **Store the mode on `Round`**, as `timed_inspection: Mapped[bool]` with
  `default=True, server_default=true()` (mirrors `Solve.plus_two`'s existing
  default/server_default pairing), set once in `services.start_round` alongside `puzzle` and
  never changed afterward. Alternative considered: a `Challenge`-level setting — rejected, since
  the owner explicitly wants it changeable per round, not per challenge.
- **`services.start_round` gains a `timed_inspection: bool | None = None` parameter**, defaulting
  via a new `next_timed_inspection_default(challenge)` helper that mirrors
  `next_puzzle_default` (round 1 → `True`; later rounds → the previous round's value). The
  socket handler `on_start_round` reads `data.get("timed_inspection")` the same way it reads
  `data.get("puzzle")`.
- **The server stays mostly passive about enforcement**, consistent with the existing trust
  boundary, but rejects the two events that should never fire client-side in an untimed round
  rather than silently accepting them: `services.inspection_expired` raises `InvalidState` if
  called for a round with `timed_inspection=False` (a defensive check beats silently accepting
  a DNF that shouldn't be possible), and `services.start_solve` raises `InvalidState` if called
  with `plus_two=True` in an untimed round, for the same reason.
- **The client reads the round's mode off the state already pushed to it** (the round payload
  sockets already send on `start_round`/on connect) rather than a separate event, and branches
  `challenge.js`'s inspection countdown: timed mode keeps today's 15s/17s timers; untimed mode
  shows "Start inspection" leading straight to an unlimited wait with no countdown UI, no +2
  auto-flag, and no expiry timer armed.
- **Switch default on page load** (`next_timed_inspection_default`) is computed server-side and
  rendered into the lobby template the same way `default_puzzle` already is, so it's correct on
  first paint without a round-trip.

## Risks / Trade-offs

- [A late joiner mid-round could, in principle, race the mode] → Mitigated the same way `puzzle`
  already is: mode is read from the `Round` row (immutable once created), not inferred
  client-side, so every joiner — early or late — gets the same value.
- [Adding a NOT-NULL-with-default column needs a migration like `solves.plus_two` did] →
  Low risk: same pattern already proven in this codebase (migration `5c1f0d2a7e3b`), batch mode
  is already configured for SQLite ALTERs.
- [Six theme.css files need the new switch control, but the mockup only styled `plain`] →
  Tracked as an explicit task; not a correctness risk, just remaining work before this ships.

## Migration Plan

1. Add the `rounds.timed_inspection` column via a new Alembic revision (default `true`, so
   existing/in-flight rounds keep today's behaviour unchanged).
2. Ship server + client together in one deploy (no feature flag needed — the column default
   preserves current behaviour until a CO actively flips the switch).
3. No rollback complexity beyond the usual: reverting the deploy leaves the column unused but
   harmless; the migration itself only adds a column with a default, so it's safe to leave in
   place even if the feature is later reverted.
