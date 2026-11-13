## MODIFIED Requirements

### Requirement: Connecting a timer
Connecting a timer SHALL need only the button press and choosing the timer from the
browser's own Bluetooth device list: no browser flags, settings changes or typed codes. The
supported timers SHALL be the QiYi protocol devices (the QiYi Smart Timer, and the QiYi
Bluetooth adapter fitted to a Speed Stacks timer) and the GAN Smart Timer. One button SHALL
offer all of them, and the app SHALL work out which kind of timer was chosen by itself.

#### Scenario: Successful connection
- **WHEN** a player presses "Connect timer" and picks their QiYi timer or adapter, or their
  GAN timer, in the browser's device list
- **THEN** the button reads "Timer connected" and is highlighted the way an "on" toggle is in
  that skin, and the timer controls that player's
  solves from then on

#### Scenario: Both kinds of timer in range
- **WHEN** a player presses "Connect timer" with a QiYi timer and a GAN timer both switched on
  nearby
- **THEN** the device list shows both, and whichever the player picks works

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
