# SPEC.md → openspec/specs migration — deviations found

Draft audit, 2026-10-22. SPEC.md was last edited 2026-09-27 (commit 558a830); 52+ commits have
landed on main since then. Root `SPEC.md` is left in place untouched — this is a draft for
review, not a committed migration.

## Capabilities drafted

- `challenge-lifecycle` — creation, joining, mid-round joins, CO grace period, ending, sharing
  (QR/link), summary page
- `round-flow` — starting/ending rounds, puzzle defaults
- `solve-timing` — inspection, start/stop solve, show-time toggle, honour-system trust boundary
- `leaderboard-scoring` — live leaderboard, ties, self-correction toggles, points
- `theming` — skin picker (new capability, not in SPEC.md at all)
- `admin-area` — read-only challenge browser (new capability, not in SPEC.md at all)

## Real contradictions in SPEC.md (not just gaps)

1. **Challenge.status enum is incomplete.** SPEC.md's Data Model table lists only `waiting |
   round_active | round_results`, but the actual enum (and SPEC.md's own Lifecycle/Socket
   sections) has a fourth value, `ended`. The table was never updated when `end_challenge`
   shipped.
2. **CO-leaves behavior is stricter in SPEC.md than in the app.** SPEC.md's "CO leaves" section
   says "If the CO disconnects, the challenge ends — no ownership transfer in v1," with no
   mention of any delay. The actual code gives the CO a 30-second grace period
   (`Challenge.co_left_at`, `CO_GRACE_SECONDS = 30`) before ending it. This is a real behavior
   change since SPEC.md was written, not documented anywhere in it.
3. **`game_error` event is undocumented.** The Server→Client socket table in SPEC.md has no row
   for `game_error`, even though it's a real event the server emits (see `app/sockets.py`).

## Gaps: shipped features with no mention in SPEC.md at all

4. **Theming/skin system.** A gear-menu skin picker with 6 skins (Minimal, Dark, DOS, Mario,
   Monkey, VHS — `app/config.py` THEMES), persisted via a `scramble_skin` cookie. Nothing in
   SPEC.md acknowledges this exists.
5. **Admin area.** A password-gated, read-only `/admin` area for the site owner to browse every
   challenge ever played (`app/admin.py`), with login lockout after repeated wrong passwords.
   This is a different actor/concept (site owner, not CO) that SPEC.md never introduces.
6. **Remembered display-name cookie.** A separate `scramble_name` cookie pre-fills the name
   field from a previous visit, independent of the per-challenge device-identity cookie SPEC.md
   does document.

## Open questions for the owner (judgment calls, not bugs)

- **Should the `ended` status and the CO grace period be folded into the root SPEC.md too, or
  is SPEC.md meant to go away/become historical once openspec/specs/ is the source of truth?**
  Recommendation: once this migration is reviewed and merged, treat `openspec/specs/` as the
  living spec and either delete SPEC.md or demote it to a "v1 design note" — maintaining two
  specs in parallel will just drift again.
- **Is the "honour system, no anti-cheat" framing from SPEC.md's Overview still the intended
  product stance,** given admin area and persistence now exist? (Nothing found suggests this
  changed — recorded here only because it's a product-level statement worth the owner
  re-confirming rather than silently carrying forward.)
- **Capability granularity** — this draft splits round/solve/leaderboard into three capabilities
  rather than one monolithic "gameplay" spec, and separates sharing/summary into
  challenge-lifecycle rather than its own "sharing" capability. Reasonable alternative
  groupings exist; flagging the choice rather than assuming it's final.
- **Socket event contract** — original SPEC.md documented client/server events as explicit
  tables. This draft folds that detail into requirement scenarios instead (OpenSpec's
  behavior-first convention) rather than keeping a protocol table. If the owner wants the literal
  event/payload names kept as a reference (useful for client/server contract tests), that could
  be re-added as a table inside one of the specs, or kept in SPEC.md as a technical appendix even
  after the rest of SPEC.md is retired.

## Not covered in this draft (out of scope for a first pass)

- No deep audit of client-side JS/CSS behavior beyond what's needed to confirm the
  requirements above (e.g. exact wake-lock or ad-blocker-rename fixes aren't spec-level
  behavior and were left out deliberately).
- `openspec validate --specs --strict` passes clean on all six drafted files.
