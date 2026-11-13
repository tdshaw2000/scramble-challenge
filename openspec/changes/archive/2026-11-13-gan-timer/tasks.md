# Tasks

## 1. Hardware check and capture (owner, before any code)

- [x] 1.1 Owner scans with the nRF Connect app on Android, with the GAN Halo switched on:
      note the timer's name exactly, and screenshot its expanded advertisement (services and
      manufacturer data). Verify the name prefix to filter on.
- [x] 1.2 Owner connects to the timer in nRF Connect, opens service `FFF0`, turns on
      notifications for characteristic `FFF5`, and does one normal solve and one solve stopped
      with a +2-style late start (any order is fine). Then shares the log (nRF Connect's
      "Log" tab, or screenshots of the values). Verify the packets start `FE` and the stopped
      time matches the timer's display; record the byte layout and CRC in this file.

Result (2026-11-13, owner's Halo): it advertises as `GAN-STv4769` with service `0xFFF0`, so the
device list filters on the `GAN` prefix. Two solves were captured on `FFF5` (saved in
`/mnt/project-files/bluetooth-timer/gan-halo-nrf-2026-11-13.txt`). Every packet is `FE`, a
length, `01`, the state, then for a stop the time as minutes, seconds and milliseconds (2 bytes,
low byte first), then a CRC16-CCITT (start 0xFFFF, polynomial 0x1021) of everything after the
length, low byte first. All 11 packets' CRCs check. States seen: 06 hands on, 01 getting set,
03 running, 04 stopped (3.775 s and 4.601 s), 07 finished, 05 idle (time zero, on reset).
A solve is hands on, getting set, running, stopped with the time, finished, as the design
expected. Hands off (02) didn't appear. Nothing has to be written to the timer. The owner
confirmed the Halo displayed 3.77 and 4.60 (times are truncated, so 3.775 shows as 3.77). A third
solve over a minute, `FE-08-01-04-01-07-A2-03-ED-7A`, decodes to 1:07.930, which the Halo
showed too, so the minutes byte works as expected.

## 2. Protocol building blocks

- [x] 2.1 Save the capture as `tests/e2e/fixtures/gan-halo-nrf-2026-11-13.log` and write
      `tests/e2e/gan.py`, an independent Python description of the packet (CRC, state, time);
      verify it decodes every captured packet and its CRC matches
- [x] 2.2 Write failing tests, then implement the GAN packet parser in
      `app/static/bluetooth-timer.js`; verify every captured packet maps to the expected neutral
      state, a bad CRC is dropped, and a stop's time is minutes, seconds and milliseconds added
      up

## 3. Connecting

- [x] 3.1 Extend the fake `navigator.bluetooth` to play a GAN timer (its service, the
      notifying characteristic, no writes expected); verify an e2e test can connect to it
- [x] 3.2 Write a failing e2e test, then widen the device-list filter to GAN's prefix and list
      both services; verify the request the fake receives includes QiYi and GAN, and that
      picking a GAN device connects and shows "Timer connected"
- [x] 3.3 Write a failing e2e test that a GAN connection writes nothing to the timer (no hello)
      and logs received packets with `?timerlog`; implement and verify

## 4. Timer drives the solve

- [x] 4.1 Write a failing e2e test: connected GAN player starts inspection, fake timer sends
      getting set, running, then stopped with a time; verify the screen shows ready and the
      result is recorded with the timer's time
- [x] 4.2 Write a failing e2e test that a stopped followed by finished records one result;
      verify
- [x] 4.3 Write a failing e2e test that the GAN timer disconnecting mid-solve shows "Timer lost"
      and the screen takes over; verify

## 5. Integration and real hardware

- [x] 5.1 Run the full suite and verify it is green
- [x] 5.2 Owner checks on Android Chrome with the GAN Halo on the live site, as for QiYi:
      connect with one press, a full solve with the time matching the timer's display, the
      screen lighting up ready on the pads, a +2 start, a brushed screen doing nothing, and
      switching the timer off mid-solve then finishing on the screen. Captures the
      `?timerlog` log; add any new frames to the fixture tests. Also connect the QiYi adapter
      once more to confirm it still works.

Result (2026-11-13, owner, live site, Android Chrome): the owner confirmed the GAN Halo works. With the Halo the screen lights up "ready" once the player's hands are
on the pads, from the timer's getting-set message (the QiYi adapter on a G5 never sends it).
- [x] 5.3 Update the README's Bluetooth timers section to name GAN

## Workflow follow-up

- Archive this change once it has shipped and the owner's 5.2 check passes.

Archived 2026-11-13. Judgment call from the review of PR #74: GAN timers are found by the `GAN`
name prefix alone (not name plus the FFF0 service), so a GAN smart cube nearby may also be
listed; picking one fails cleanly with "Timer not connected."
