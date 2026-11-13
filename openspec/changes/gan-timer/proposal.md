# Proposal

## Why

The Bluetooth timer feature works with QiYi devices (shipped 2026-11-12, tested by the owner
with a Speed Stacks G5 and the QiYi adapter). The owner also has a GAN Halo Smart Timer, and GAN
timers are the other common Bluetooth timer among speedcubers. The first change planned this
as a follow-up: a second driver behind the same "Connect timer" button.

## What Changes

- The same "Connect timer" button also finds GAN timers (the owner's GAN Halo, and the original GAN Smart Timer, which is described as speaking the same protocol). The browser's device list shows both
  QiYi and GAN timers, and the app picks the right protocol from the name of the one chosen.
  Still one press, no flags, nothing to type.
- Everything a player sees and does stays as it is for QiYi: inspection on the screen, the
  timer's pads start and stop the solve, the timer's own time is recorded, the screen and
  spacebar are ignored while connected, and the screen takes over if the timer is lost.
- GAN timers report when the player's hands are ready on the pads, so with a GAN timer the
  screen lights up "ready" the way it does for a held finger (the QiYi adapter on a G5 never
  reported this).
- The on-page log (`?timerlog`) also shows GAN packets, so real frames can be captured on a
  phone the same way.
- No server changes.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `bluetooth-timer`: "Connecting a timer" names GAN timers as supported alongside QiYi, and the
  device list offers both.

## Impact

- `app/static/bluetooth-timer.js`: a GAN driver next to the QiYi one, and device-list filters
  for both. Our own code. The MIT-licensed `gan-web-bluetooth` library and csTimer are used
  only as descriptions of how the timer behaves; nothing is copied and no new dependency is
  added (that library needs RxJS, which this app doesn't use).
- `app/static/challenge.js`: no change expected, since it only sees neutral states.
- Tests: a Python description of the GAN protocol in `tests/e2e/gan.py`, the fake
  `navigator.bluetooth` extended to play a GAN timer, and protocol tests against real frames
  the owner captures.
- README: the Bluetooth timers section names GAN as supported.
