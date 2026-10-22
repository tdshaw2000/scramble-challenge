# Tasks

## 1. Data model

- [ ] 1.1 Write a failing test asserting a new `Round` defaults to `timed_inspection=True`, then
      add `Round.timed_inspection: Mapped[bool]` (`default=True, server_default=true()`) and
      verify the test passes
- [ ] 1.2 Generate an Alembic migration for `rounds.timed_inspection` (batch mode, matching the
      `solves.plus_two` migration) and verify `uv run flask db upgrade` applies cleanly against
      a copy of the existing SQLite data

## 2. Round-start default and service layer

- [ ] 2.1 Write a failing test for `services.next_timed_inspection_default`: `True` for round 1,
      and the previous round's value from round 2 onward; implement it (mirroring
      `next_puzzle_default`) and verify the test passes
- [ ] 2.2 Write a failing test that `services.start_round` stores the CO's chosen
      `timed_inspection` value (and falls back to the default when omitted); add the
      `timed_inspection: bool | None = None` parameter and verify the test passes
- [ ] 2.3 Write a failing test that `services.inspection_expired` raises `InvalidState` when the
      round's `timed_inspection` is `False`; add the check and verify the test passes

## 3. Socket layer

- [ ] 3.1 Write a failing socket test that `start_round` reads `data.get("timed_inspection")`
      and the created round reflects it; wire `on_start_round` to pass it through and verify the
      test passes
- [ ] 3.2 Write a failing socket test that the round payload sent to clients (on `start_round`
      and on a late joiner's/reconnect's state push) includes `timed_inspection`; add the field
      and verify the test passes

## 4. Lobby UI and client inspection flow

- [ ] 4.1 Add the timed-inspection switch to `app/templates/challenge.html` between the
      QR/share buttons and the puzzle dropdown (per the approved mockup on branch
      `mockup/timed-inspection-toggle`), submitting `timed_inspection` with the start-round
      request; verify a browser test finds the control in that position and that its initial
      state matches the server-rendered default
- [ ] 4.2 Style the switch in every `theme.css` (`plain` already done in the mockup; `dos`,
      `dark`, `mario64`, `monkeyisland2`, `neon80s` still need it) and verify the existing
      per-theme CSS test (`.share-label` etc. pattern) covers the new classes too
- [ ] 4.3 Write a failing browser test that an untimed-inspection round shows no countdown and
      lets the player start their solve immediately with no +2; branch `challenge.js`'s
      inspection handling on the round's `timed_inspection` field and verify the test passes
- [ ] 4.4 Write a failing browser test that a timed-inspection round is unchanged (countdown,
      +2 at 15s, DNF at 17s still fire); verify it passes without having broken step 4.3

## 5. Spec and integration verification

- [ ] 5.1 Run the full test suite (`uv run pytest`) and verify it's green, including the
      browser tests
- [ ] 5.2 Manually verify in a running instance: start a round with the switch off, confirm no
      countdown/penalty; start the next round, confirm the switch defaults to off (carried
      forward); flip it on, confirm the round after that defaults to on

## Workflow follow-up

- Archive this change once it has shipped and the review process is complete.
- Verify the archived spec deltas landed in `openspec/specs/round-flow/spec.md` and
  `openspec/specs/solve-timing/spec.md`.
