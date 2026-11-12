# Tasks

## 1. Hardware check (owner, before any code)

- [x] 1.1 Owner checks the QiYi adapter's Bluetooth name and address with the nRF Connect app on
      Android and confirms the address is `CC:A8:00:00:` followed by the four characters at the
      end of the name (`QY-Adapter-ABCD` → `CC:A8:00:00:AB:CD`). If it matches, keep the design
      as written. If not, add the remembered "timer code" fallback to group 3 before starting.
- [x] 1.2 Owner screenshots the adapter's expanded advertisement in nRF Connect (manufacturer
      data, company 0x0504), which carries the address reversed; verify it agrees with 1.1.
      (Live status messages are not captured here: the timer likely sends nothing before the
      app's hello. Real frames are captured in 6.2 instead.)

Result (2026-11-11, owner's adapter): name `QY-Adapter-2B0F`, address `CC:A8:00:00:2B:0F`, a
match. Manufacturer data (company 0x0504) is `0F2B0000A8CC 0121080001055A`: the first six bytes
are the same address reversed. The rest matches the fixed part of the hello message. The name
rule holds, so no fallback is needed. The advertisement also lists 16-bit service `0xFF01`.

## 2. Protocol building blocks

- [x] 2.1 Vendor a pinned MIT AES-128 library into `app/static/vendor/` with its licence text;
      verify a test page can encrypt and decrypt one 16-byte block with the fixed key and get
      the original back
- [ ] 2.2 Write failing tests, then implement CRC16/MODBUS, message framing (sequence numbers,
      command, length, CRC, 16-byte blocks) and block encryption in
      `app/static/bluetooth-timer.js`; verify against known vectors and, once 6.2 has captured some,
      real frames from the owner's adapter
      (Done apart from the real frames, which come from 6.2 after deploy.)
- [x] 2.3 Write failing tests, then implement parsing of status messages (idle, ready, running,
      stopped with time) and record messages (final time, which must be acknowledged); verify
      each maps to the neutral `ready`/`running`/`stopped {timeMs}`/`idle` states

## 3. Connecting

- [x] 3.1 Build the fake `navigator.bluetooth` Playwright helper (device chooser, GATT service,
      characteristics, notifications) and verify an e2e test can "connect" to it
- [x] 3.2 Write a failing e2e test, then add the "Connect timer" button (stopwatch SVG icon +
      text, mockup D) under Show time on the scramble screen, shown only when `navigator.bluetooth` exists; verify it is absent when the fake is not
      installed
- [x] 3.3 Write a failing e2e test, then implement connect: device chooser filtered to `QY-Timer`
      and `QY-Adapter`, MAC from the name, hello message; verify the button shows "connected"
      and the hello frame the fake received decodes to the right MAC
- [x] 3.4 Write failing e2e tests for a cancelled chooser and a failed connection, then show the
      short "not connected" message; verify the screen still starts and stops solves
- [x] 3.5 Write a failing e2e test, then make pressing the button again disconnect; verify
      screen input works again afterwards
- [x] 3.6 Style the button in every theme's `theme.css` to match mockup D (same look as Show
      time, "on" highlight when connected, icon sized to the text) and verify the per-theme CSS test covers
      the new class

## 4. Timer drives the solve

- [x] 4.1 Write a failing e2e test: connected player starts inspection, fake timer sends ready,
      then running, then stopped with 12345 ms; verify `data-ready` shows during ready, and the
      recorded result is 12.34
- [x] 4.2 Write a failing e2e test that a timer start 15–17 s into timed inspection gives a +2,
      and that inspection still runs out to a DNF at 17 s with no timer start; verify both
- [x] 4.3 Write a failing e2e test that timer events in the lobby or after finishing do nothing;
      verify no `start_solve`/`stop_solve` is sent
- [x] 4.4 Write a failing e2e test that screen taps and the spacebar neither start nor stop a
      solve while connected; implement and verify
- [x] 4.5 Verify an untimed-inspection round works with the timer (no countdown, no +2)

## 5. Losing the timer

- [x] 5.1 Write a failing e2e test: fake timer disconnects during inspection; verify the message
      shows, the countdown continues and a screen release starts the solve
- [x] 5.2 Write a failing e2e test: fake timer disconnects while solving; verify the message
      shows and a screen tap stops the solve with a browser-measured time from the timer's start

## 6. Integration and real hardware

- [x] 6.1 Run the full suite (`uv run pytest`, including e2e) and verify it is green
- [ ] 6.2 Owner checks on Android Chrome with the G5 and QiYi adapter, on a deployed preview or
      the live site: connect with one press and no flags, a full solve where the shown time
      matches the G5's display, a +2 start, a brushed screen doing nothing, and switching the
      adapter off mid-solve then finishing on the screen; save a few real
      frames from the browser console log for the protocol tests
- [x] 6.3 Update the README's feature list to mention Bluetooth timers (Android/desktop Chrome
      and Edge only)

## Workflow follow-up

- Archive this change once it has shipped and the review process is complete.
- Then propose GAN Smart Timer support as its own change, as a second driver behind the same
  button.
