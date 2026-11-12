# Spec Delta

## Purpose

Lets a player optionally use a Bluetooth speedcubing timer, instead of the screen or spacebar,
to start and stop their own solve, while inspection stays on the screen.

## ADDED Requirements

### Requirement: Offering a timer connection
The scramble screen SHALL offer a "Connect timer" control only in browsers that support Web
Bluetooth. Where it is not supported, the control SHALL NOT appear and solving works by screen
and spacebar exactly as before.

#### Scenario: Supported browser
- **WHEN** a player opens a challenge in a browser with Web Bluetooth (e.g. Chrome on Android)
- **THEN** the scramble screen shows a "Connect timer" button with a stopwatch icon, under
  the Show time toggle

#### Scenario: Unsupported browser
- **WHEN** a player opens a challenge in a browser without Web Bluetooth (e.g. Safari on iPhone)
- **THEN** no timer control is shown, and the screen and spacebar work as they do today

### Requirement: Connecting a timer
Connecting a timer SHALL need only the button press and choosing the timer from the
browser's own Bluetooth device list: no browser flags, settings changes or typed codes. The
first supported timers SHALL be the QiYi protocol devices (the QiYi Smart Timer, and the QiYi
Bluetooth adapter fitted to a Speed Stacks timer).

#### Scenario: Successful connection
- **WHEN** a player presses "Connect timer" and picks their QiYi timer or adapter in the
  browser's device list
- **THEN** the button reads "Timer connected" and is highlighted the way an "on" toggle is in
  that skin, and the timer controls that player's
  solves from then on

#### Scenario: Connection fails or is cancelled
- **WHEN** the player cancels the device list, or the timer cannot be connected
- **THEN** a short message says the timer is not connected, and the screen and spacebar keep
  working as usual

#### Scenario: Disconnecting on purpose
- **WHEN** a connected player presses the timer button again
- **THEN** the timer is disconnected and the screen and spacebar take over again

#### Scenario: New page load
- **WHEN** a player who had a timer connected reloads or reopens the challenge page
- **THEN** the timer is not connected, and the player presses "Connect timer" again (browsers
  only allow a Bluetooth connection from a button press)

### Requirement: Inspection stays on the screen
With a timer connected, a player SHALL still start inspection with the "Start inspection" button,
and inspection SHALL follow the round's mode (WCA-timed or untimed) exactly as for screen
solving. The timer does not start inspection.

#### Scenario: Timer activity before inspection
- **WHEN** a connected timer is started or stopped while the player is not inspecting or solving
  (for example in the lobby, or after their attempt is finished)
- **THEN** nothing is recorded and the player's state does not change

#### Scenario: Penalty from the timer start
- **WHEN** the timer starts between 15 and 17 seconds into a timed inspection
- **THEN** the solve gets a +2, as if the player had started it on the screen at that moment

#### Scenario: Inspection runs out with a timer connected
- **WHEN** 17 seconds of timed inspection pass without the timer starting
- **THEN** the attempt is a DNF, exactly as for screen solving

### Requirement: The timer starts and stops the solve
While a timer is connected, the timer starting SHALL start the player's solve during inspection,
and the timer stopping SHALL stop it. The recorded time SHALL be the time the timer reports,
not the browser's clock. Screen taps and the spacebar SHALL NOT start or stop a solve while a
timer is connected.

#### Scenario: A full timer solve
- **WHEN** a connected player starts inspection, starts the timer, and stops the timer
- **THEN** the solve is recorded with the time the timer displayed, with any +2 applied, and the
  finished screen shows it as for any other solve

#### Scenario: Getting ready on the pads
- **WHEN** the player's hands have been on the pads long enough for the timer to be ready to
  start
- **THEN** the screen shows the same "ready" state it shows while a finger is held down

#### Scenario: Brushing the screen
- **WHEN** a connected player touches the screen or presses the spacebar while inspecting or
  solving
- **THEN** the solve is neither started nor stopped

### Requirement: Losing the timer
If the timer disconnects, the screen and spacebar SHALL take over at once, and the player SHALL
be told, so an attempt can always be finished.

#### Scenario: Disconnect during inspection
- **WHEN** the timer disconnects while the player is inspecting
- **THEN** a message says the timer was lost, the inspection countdown carries on, and the
  player can start the solve on the screen

#### Scenario: Disconnect during a solve
- **WHEN** the timer disconnects while the player is solving
- **THEN** a message says the timer was lost, and the player stops the solve on the screen; the
  time is measured by the browser from when the timer started
