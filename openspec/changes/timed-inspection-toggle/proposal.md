# Proposal

## Why

Timed inspection (WCA-style, +2 at 15s, DNF at 17s) is currently always on. Casual groups and
younger/newer solvers find the countdown pressure takes the fun out of a social game, and the
owner wants the CO to be able to turn it off per round rather than for the whole challenge.

## What Changes

- Add a CO-only on/off switch in the lobby, between the QR code/share-link buttons and the
  puzzle dropdown, that sets whether the next round starts with timed inspection.
- The chosen setting applies to that one round. It defaults to on, matching today's behaviour,
  and carries forward from the previous round the same way the puzzle default does (so the CO
  doesn't have to re-set it every round, but can still flip it before starting).
- When a round starts with timed inspection off, players get no countdown, no +2, and no
  inspection-timeout DNF: they can start their solve whenever they're ready, with inspection
  effectively untimed.
- Round state needs to remember which mode it started in, since it's decided once at
  "Start round" and must stay consistent for every player in that round (a late joiner or a
  reconnect should not infer a different mode mid-round).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `round-flow`: starting a round now also captures the CO's timed-inspection choice (alongside
  puzzle), and that choice has a default-carries-forward rule like the puzzle default.
- `solve-timing`: the WCA-style inspection requirement becomes conditional on the round's mode;
  add the untimed-inspection behaviour for rounds started with the switch off.

## Impact

- `app/templates/challenge.html`, theme CSS (new switch control, `plain` already mocked up on
  branch `mockup/timed-inspection-toggle`; other skins still need their own styling).
- `app/services.py` (`start_round`), `app/models.py` (`Round` needs a `timed_inspection` column
  + migration), `app/sockets.py` (`start_round`, `start_inspection`, `start_solve`,
  `inspection_expired` handlers all currently assume timed inspection unconditionally).
- `app/static/challenge.js` (client inspection countdown/penalty logic needs an untimed path).
- `openspec/specs/round-flow/spec.md`, `openspec/specs/solve-timing/spec.md`.
