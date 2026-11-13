# Tasks

## 1. Hardware check and capture (owner, before any code)

- [ ] 1.1 Owner scans with the nRF Connect app on Android, with the GAN timer switched on:
      note the timer's name exactly, and screenshot its expanded advertisement (services and
      manufacturer data). Verify the name prefix to filter on.
- [ ] 1.2 Owner connects to the timer in nRF Connect, opens service `FFF0`, turns on
      notifications for characteristic `FFF5`, and does one normal solve and one solve stopped
      with a +2-style late start (any order is fine). Then shares the log (nRF Connect's
      "Log" tab, or screenshots of the values). Verify the packets start `FE` and the stopped
      time matches the timer's display; record the byte layout and CRC in this file.

## 2. Protocol building blocks

- [ ] 2.1 Save the capture as `tests/e2e/fixtures/gan-smart-timer-<date>.log` and write
      `tests/e2e/gan.py`, an independent Python description of the packet (CRC, state, time);
      verify it decodes every captured packet and its CRC matches
- [ ] 2.2 Write failing tests, then implement the GAN packet parser in
      `app/static/bluetooth-timer.js`; verify every captured packet maps to the expected neutral
      state, a bad CRC is dropped, and a stop's time is minutes, seconds and milliseconds added
      up

## 3. Connecting

- [ ] 3.1 Extend the fake `navigator.bluetooth` to play a GAN timer (its service, the
      notifying characteristic, no writes expected); verify an e2e test can connect to it
- [ ] 3.2 Write a failing e2e test, then widen the device-list filter to GAN's prefix and list
      both services; verify the request the fake receives includes QiYi and GAN, and that
      picking a GAN device connects and shows "Timer connected"
- [ ] 3.3 Write a failing e2e test that a GAN connection writes nothing to the timer (no hello)
      and logs received packets with `?timerlog`; implement and verify

## 4. Timer drives the solve

- [ ] 4.1 Write a failing e2e test: connected GAN player starts inspection, fake timer sends
      getting set, running, then stopped with a time; verify the screen shows ready and the
      result is recorded with the timer's time
- [ ] 4.2 Write a failing e2e test that a stopped followed by finished records one result;
      verify
- [ ] 4.3 Write a failing e2e test that the GAN timer disconnecting mid-solve shows "Timer lost"
      and the screen takes over; verify

## 5. Integration and real hardware

- [ ] 5.1 Run the full suite and verify it is green
- [ ] 5.2 Owner checks on Android Chrome with the GAN timer on the live site, as for QiYi:
      connect with one press, a full solve with the time matching the timer's display, the
      screen lighting up ready on the pads, a +2 start, a brushed screen doing nothing, and
      switching the timer off mid-solve then finishing on the screen. Captures the
      `?timerlog` log; add any new frames to the fixture tests. Also connect the QiYi adapter
      once more to confirm it still works.
- [ ] 5.3 Update the README's Bluetooth timers section to name GAN

## Workflow follow-up

- Archive this change once it has shipped and the owner's 5.2 check passes.
