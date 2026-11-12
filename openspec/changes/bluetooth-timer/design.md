# Design

## Context

All solve timing happens in `app/static/challenge.js`. `pressTimer()` starts the solve during
inspection (working out +2 from the inspection clock and sending `start_solve {plus_two}`), and
stops it while solving (sending `stop_solve {time_ms}`). Screen pointer events and the spacebar
call it through `holdOrStop()` and `letGo()`, and `setHeld()` sets `data-ready` on `#game`
so each theme can light the screen up. The server trusts the browser's time (see
`openspec/specs/solve-timing`), so a Bluetooth timer needs no server change.

Web Bluetooth only works in Chromium browsers (Chrome and Edge on Android, Windows and macOS).
Safari and every iOS browser lack it. The owner plays on Android Chrome.

## Goals / Non-Goals

**Goals:**
- QiYi-protocol timers work with one button press on Android Chrome.
- The timer slots in behind the same start and stop paths as the screen, so inspection,
  penalties and the server stay as they are.
- A driver shape that GAN can be added to later without touching `challenge.js` again.

**Non-Goals:**
- GAN timers (a follow-up change), Stackmat audio-cable input, and smart cubes.
- iOS support (not possible without Web Bluetooth; the Bluefy browser may work but isn't
  tested or supported).
- Reconnecting automatically after a page reload (Chrome only allows that behind a flag).
- Any server-side check of timer times (honour system unchanged).

## Decisions

### Inspection: screen starts it, timer pads start and stop the solve
This was the owner's choice (option A) over "timer does everything" and "untimed inspection for
timer users". It mirrors a WCA competition and reuses the existing countdown. The QiYi
protocol also reports an `INSPECTION` state and an inspection time; we ignore both, so the
round's inspection mode is decided in one place only.

### A driver interface in its own file
`app/static/bluetooth-timer.js` exposes `window.BluetoothTimer` with `supported()`,
`connect()` (opens the device chooser, filtered to known name prefixes, and returns a
connection), and on the connection: `onState(fn)` with `ready`, `running`, `stopped {timeMs}`,
`idle` and `disconnected`, plus `disconnect()`. Each device family is a driver behind that.
`challenge.js` only knows the neutral states. GAN later becomes a second driver.

### Timer events reuse the existing start and stop paths
`running` during inspection calls the same start code as a screen release (so +2 and the
17-second DNF check are shared). `stopped` while solving calls the stop code with the timer's
`timeMs` instead of `performance.now()`. `ready` sets the same `data-ready` the screen hold sets.
Events in any other phase are ignored.
*Alternative*: let the timer's own `RUNNING` time drive a separate path. Rejected because it
would duplicate the penalty logic.

### Screen input is ignored while a timer is connected
A brushed phone or a cube knocked onto the spacebar must not end an attempt that the pads are
timing. If the timer disconnects, screen input is re-enabled at once; a solve already running
is then stopped on the screen and timed from the browser's own start timestamp, which is taken
when the `running` event arrives.
*Alternative*: accept both inputs. Rejected because accidental stops are the more likely
failure, and the disconnect fallback covers the stuck case.

### QiYi protocol, written from scratch
Behaviour learned from csTimer's `qiyitimer.js` (GPL-3, used only as a reference, no code
copied): GATT service `0000fd50-0000-1000-8000-00805f9b34fb`, write and notify
characteristics, messages framed with sequence numbers, command, length and CRC16/MODBUS, and
each 16-byte block AES-128-ECB encrypted with a fixed key. The connection opens with a "hello"
message that includes the device's MAC address. Status messages carry the state and time;
"record" messages carry the final time and must be acknowledged.

### Getting the MAC without a Chrome flag
csTimer reads the MAC from Bluetooth advertisements, which needs Chrome's "Experimental Web
Platform features" flag. That is the step the owner had to enable on desktop. Instead we
derive it from the advertised name, as csTimer's own fallback does: `QY-Adapter-ABCD` gives
`CC:A8:00:00:AB:CD`, and `QY-Timer-ABCD` gives `CC:A1:00:00:AB:CD`. **This is unverified on
the owner's hardware and is the first task.** If it does not hold, the fallback is a one-time
"timer code" box whose answer is remembered on the device (a cookie, like Show time), not a
flag.

### The button: stopwatch icon and text (mockup D)
A full-width button under Show time, sharing its `.show-time`-style look in each skin, with
an inline stopwatch SVG (Material Symbols "timer", Apache 2.0) and the text "Connect timer",
which changes to "Timer connected" with `aria-pressed="true"` once connected. The owner
picked this from four mockups (`mockups/bluetooth-timer/` in the project files). The
Bluetooth logo was avoided because it is a Bluetooth SIG trademark reserved for members'
certified products, and a stopwatch says "timer" more plainly.

### AES-128 from a small vendored library
WebCrypto does not offer raw AES-ECB block encryption and decryption. We vendor a small
MIT-licensed AES implementation (e.g. `aes-js`) into `app/static/vendor/`, alongside the
existing `socket.io.min.js`, and pin its version in a comment.

### Testing with a fake Bluetooth device
Playwright can't reach real Bluetooth, so end-to-end tests install a fake `navigator.bluetooth`
with `add_init_script` that returns a device which plays back encrypted QiYi frames.
Protocol pieces (CRC, framing, encryption round-trip, parsing a status or record message) get
focused tests driven through the same page. Fixture frames are generated by the test helper
with the fixed key, and checked against at least one real capture from the owner's adapter
once available.

## Risks / Trade-offs

- [The name-to-MAC guess is wrong for some adapters] → First task checks it on the owner's
  adapter; the remembered timer-code box is the fallback.
- [Adapter drops its connection mid-solve (reported by one csTimer user)] → Screen takes over
  at once with a clear message; the solve can still be finished.
- [Bluetooth delay makes the +2 boundary slightly late] → Tens of milliseconds at most and
  only at the 15 s edge; accepted.
- [No automated test against real hardware] → An owner hardware checklist (task group 6) must
  pass before merge.
- [iPhone players can't use it] → The button is hidden for them; nothing else changes.
