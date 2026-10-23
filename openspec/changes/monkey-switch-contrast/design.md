# Design

## Context

The switch markup is shared by every skin (`.switch` > `input` + `.switch-track` >
`.switch-thumb`, in `app/templates/challenge.html`). Each skin styles it in its own
`theme.css`. Monkey's current rules:

- off: track `--parchment`, border `--wood-dark`, knob `--wood-dark`
- on: track `--parchment` (unchanged), border `--yellow`, knob `--yellow`

Yellow (#ffd23f) on parchment (#f3e2b6) is about 1.2:1, so the "on" knob nearly vanishes.

## Goals / Non-Goals

**Goals:**
- On and off look clearly different at a glance, and the knob stands out from the track in
  both states.
- Use only colours already in the Monkey palette.

**Non-Goals:**
- Other skins. Measured while preparing this, the Minimal and DOS "off" knobs are also faint
  against their tracks (about 1.5:1 and 2.9:1), but the owner hasn't raised them, so they're
  left alone here.
- ON/OFF text inside the switch (the owner turned that down).
- Size or layout changes.

## Decisions

- **On state inverts the off state.** On = `--wood-dark` track, `--yellow` border,
  `--parchment` knob on the right. Off stays parchment track with a `--wood-dark` knob on the
  left. The track flipping between light and dark is what makes the state obvious, and the
  knob is about 9:1 against its track either way. Alternatives mocked up: a yellow track
  (option A) and red/green knobs (option B); the owner chose C's colours.
- **Keep the yellow border for "on".** It matches the yellow used for "lit" verbs elsewhere
  in the skin (the +2/DNF toggles and the show-time toggle) and the focus outline.
- **Test with computed colours, not screenshots.** A browser test reads the computed track and
  knob colours in each state, like `tests/e2e/test_dark_skin.py` does for text contrast. It
  checks the track colour differs between on and off, and the knob has at least 3:1 contrast
  against its track in both states (the WCAG level for UI controls). Screenshot comparisons
  would be brittle across font rendering.

## Risks / Trade-offs

- [The focus outline is also `--yellow`, drawn inside the track] → on a dark track it shows
  up better than before, so no change needed.
