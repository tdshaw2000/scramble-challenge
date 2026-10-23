# Proposal

## Why

On the Monkey skin the timed-inspection switch looks almost the same on and off. Both states
keep the parchment track, and "on" only swaps the knob and border to yellow, which barely
stands out against parchment. The owner found it hard to tell the control is a switch at all
when it's on.

## What Changes

- Restyle the switch's **on** state in the Monkey skin only: the track turns dark wood with a
  yellow border, and the knob turns parchment and slides right.
- The **off** state stays as it is today: parchment track, dark wood border and knob on the
  left.
- Same size as now (48 x 26 px), no ON/OFF text. These are the colours of mockup option C from
  the owner's pick, without its labels.
- No other skin changes, and nothing about how the switch behaves changes.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none) This is a visual change to one skin. The `theming` spec covers how skins are chosen
and kept, not how each one looks, and no gameplay behaviour changes, so the change sets
`skip_specs: true`.

## Impact

- `app/static/themes/monkeyisland2/theme.css`: the two `.switch input:checked` rules.
- A new browser test for the Monkey switch's colours on and off.
- No template, JavaScript, server or database changes.
