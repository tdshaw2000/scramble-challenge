# Design

## Context

`app/static/bluetooth-timer.js` already has the driver shape the first change planned for:
`connect()` opens the browser's device list, a driver turns the timer's messages into neutral
states (`ready`, `running`, `stopped {timeMs}`, `idle`, `disconnected`), and `challenge.js`
acts only on those. Adding GAN means a second driver and a wider device-list filter.

What we know about GAN timers (the Halo and the original Smart Timer, which are described as sharing one protocol) comes from public descriptions (the MIT
`gan-web-bluetooth` library and csTimer), not from the owner's own timer yet. Unlike QiYi, the
protocol is believed to be simple:

- Service `0000fff0-0000-1000-8000-00805f9b34fb`. The timer sends its state as notifications
  on characteristic `0000fff5-...`. Another characteristic, `0000fff2-...`, can be read for
  the last few recorded times; we don't need it.
- No encryption, no hello message, no acknowledgements, and no address needed, so nothing has
  to be worked out from the device name.
- Each notification is a short packet starting `0xFE`, with the state, a time (minutes,
  seconds, milliseconds) and a CRC16 check.
- States: getting set (hands held long enough), hands on, hands off, running, stopped (with
  the final time), finished, idle, and disconnecting.

The exact byte layout and CRC variant are the first things to confirm on the owner's timer
(task 1), before any code depends on them.

## Goals / Non-Goals

**Goals:**
- The owner's GAN Halo works with one press on Android Chrome, exactly like QiYi.
- No change to `challenge.js` or the spec's behaviour, only to which timers are supported.
- Real frames from the owner's timer in the tests from the start, not after shipping.

**Non-Goals:**
- GAN smart cubes (a different protocol, and not a timer).
- Reading the timer's stored past times (`fff2`).
- GAN models the owner doesn't have. Ones that use the same service should work, but only the
  owner's timer is tested.
- Remembering which timer a player used last.

## Decisions

### One button, driver chosen by name
The device list is filtered to the known name prefixes of both families (`QY-Timer`,
`QY-Adapter`, and GAN's prefixes, confirmed in task 1), with both services listed as optional
services so the page may use them. The name of the chosen device picks the driver. One button
keeps the screen as it is and players don't need to know which protocol their timer speaks.
If the GAN name turns out to be unpredictable, filter by GAN's service instead (Web Bluetooth
allows a service filter alongside name filters).

### Hardware capture first
QiYi's frames only reached the tests after the live test. GAN needs no app to talk to it, so the
owner can capture real notifications with the nRF Connect app before any code is written (task
1), and the protocol tests are written against those from the start.

### State mapping
- getting set → `ready` (the screen lights up as for a held finger)
- hands on, hands off, idle → `idle`
- running → `running`
- stopped, with a time above zero → `stopped {timeMs}` (the time is minutes × 60000 +
  seconds × 1000 + milliseconds)
- finished → nothing (the stop already ended the solve)
- disconnecting → `disconnected`

If the capture shows the timer sends no separate stop before finished, or puts the time only
on finished, the mapping follows the capture.

### Own implementation
The GAN protocol is small, so writing it ourselves is short and keeps one style across both
drivers. Using the MIT library would be allowed, but it brings RxJS and its own connection
handling, which would sit awkwardly beside the QiYi driver.

## Risks / Trade-offs

- [The owner's timer differs from the public description] → the nRF Connect capture in task 1
  happens before code, and the live test (task 5) captures again with `?timerlog`.
- [A stop and finished both carry a time, so a solve could be stopped twice] → `challenge.js`
  already ignores a stop when no solve is running; a test covers it.
- [The device list now shows two kinds of timers] → harmless; players pick their own by name.
