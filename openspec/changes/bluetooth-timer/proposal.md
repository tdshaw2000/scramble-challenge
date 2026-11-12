# Proposal

## Why

Speedcubers practise on a real timer with pads, not a phone screen. Letting a player connect
their own Bluetooth timer makes a round feel like a real attempt, and the timer measures the
solve itself, which is more accurate than a finger on glass. The owner uses a Speed Stacks G5
timer with a QiYi Bluetooth adapter, and also has a GAN Smart Timer, so both can be tested on
real hardware.

## What Changes

- Add an optional "Connect timer" button with a stopwatch icon on the scramble screen, under
  the Show time toggle (mockup D, chosen by the owner). It reads "Timer connected" and is
  highlighted once connected, and it is shown only in browsers that
  support Web Bluetooth (Chrome and Edge on Android and desktop). It is hidden on iPhones and
  in Safari, where players keep using the screen as they do today.
- Connecting is one button press plus picking the timer from the browser's own Bluetooth list.
  No Chrome flags and no codes to type in.
- Inspection works as today: the player taps "Start inspection" on the screen, and the
  browser runs the WCA countdown (+2 after 15 s, DNF at 17 s) when the round has timed
  inspection on. The timer pads then start and stop the solve. This matches a WCA
  competition, where the judge starts inspection and the competitor starts the timer.
- The time recorded is the time the timer measured, not the phone's.
- While a timer is connected, the screen and spacebar no longer start or stop a solve, so a
  brushed phone can't end an attempt. If the timer disconnects, the screen takes over again
  straight away, including in the middle of a solve.
- First supported device: the QiYi Bluetooth protocol (QiYi Smart Timer, and the QiYi adapter
  that plugs into a Speed Stacks G5 or similar). GAN Smart Timer support is planned as a
  follow-up change once this works, using the same connect button and behaviour.
- No server changes. The browser sends the same start and stop messages it sends today, and the
  honour system is unchanged.

## Capabilities

### New Capabilities
- `bluetooth-timer`: connecting an optional Bluetooth timer, how its start and stop signals
  drive a player's solve, what happens on disconnect, and where it is available.

### Modified Capabilities
(none) `solve-timing` keeps its inspection, one-attempt and honour-system rules. A
Bluetooth-timed solve follows them unchanged, and the new capability says how the timer feeds
into them.

## Impact

- `app/templates/challenge.html`: the new button on the scramble screen, with an inline
  stopwatch SVG icon (Material Symbols "timer", Apache 2.0). The Bluetooth logo is not used,
  because it is a Bluetooth SIG trademark.
- `app/static/challenge.js`: solve start and stop can come from a timer as well as a tap or the
  spacebar. Screen input is ignored while a timer is connected.
- New `app/static/bluetooth-timer.js`: the QiYi protocol (our own implementation; csTimer is
  GPL and is used only as a reference for how the protocol behaves), and a small driver
  interface so GAN can be added later.
- New vendored library under `app/static/vendor/` for AES-128 (the QiYi protocol encrypts
  every message with a fixed, publicly known key).
- Theme CSS: style the new button in every skin.
- Tests: Playwright end-to-end tests with a fake `navigator.bluetooth` that plays back QiYi
  messages. Real-hardware checks by the owner (Android Chrome with the G5 and QiYi adapter).
