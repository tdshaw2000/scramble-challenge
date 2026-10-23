# Tasks

## 1. Monkey switch colours

- [ ] 1.1 Write a failing browser test (in `tests/e2e/`) that opens the lobby as the
      challenge owner in the Monkey skin and, for the timed-inspection switch, checks that the
      track's background colour differs between on and off, and that the knob has at least
      3:1 contrast against the track in both states; verify it fails on the current CSS (the
      on-state knob is about 1.1:1)
- [ ] 1.2 Change the two `.switch input:checked` rules in
      `app/static/themes/monkeyisland2/theme.css`: track `--wood-dark` with `--yellow` border,
      knob `--parchment`; verify the new test passes and the rest of the suite stays green
- [ ] 1.3 Take on/off screenshots of the switch in the Monkey lobby and check they match the
      approved mockup (`mockups/monkey-toggle/chosen-sheet.png`)
