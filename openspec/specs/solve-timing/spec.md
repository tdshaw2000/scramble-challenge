# solve-timing

## Purpose

Covers each player's own inspection-and-solve flow: WCA-style inspection timing, how a solve is
started and stopped, the optional show-time display, and the honour-system trust boundary.

## Requirements

### Requirement: WCA-style inspection
Starting a solve SHALL apply WCA inspection timing: no penalty within 15 seconds, a +2 penalty
between 15 and 17 seconds, and a DNF if 17 seconds pass with no solve started. Inspection timing
is decided by the browser, not the server.

#### Scenario: Starting within 15 seconds
- **WHEN** a player starts their solve before the 15-second mark
- **THEN** no penalty is applied

#### Scenario: Starting between 15 and 17 seconds
- **WHEN** a player starts their solve between 15 and 17 seconds into inspection
- **THEN** the solve is recorded with a +2 penalty

#### Scenario: Inspection times out
- **WHEN** 17 seconds of inspection pass with no solve started
- **THEN** the player's solve is recorded as a DNF with no time, and the leaderboard updates
  immediately

### Requirement: Starting and stopping the solve
A player SHALL start inspection, then start and stop their own solve timer independently of
every other player in the round, with no synchronized countdown across players.

#### Scenario: A full timed solve
- **WHEN** a player presses/holds to start inspection, then starts and stops the solve timer
- **THEN** a timed result is recorded for that player's `Solve` row, and their own screen shows
  the time full-screen for one second before returning to the leaderboard

#### Scenario: One attempt only
- **WHEN** a player has already completed a timed or DNF solve for the current round
- **THEN** they cannot start another attempt in that round

### Requirement: Show-time toggle
A player SHALL be able to choose, per device, whether their running solve time is displayed
live while solving. The choice SHALL persist across sessions on that device.

#### Scenario: Show time off (default)
- **WHEN** a player has not changed the show-time setting
- **THEN** the solving screen shows a solving indicator only, not the running time

#### Scenario: Show time on
- **WHEN** a player has turned the show-time toggle on
- **THEN** the solving screen shows the running time, updating live, excluding any +2 (which is
  added once the solve stops)

#### Scenario: Preference persists
- **WHEN** a player sets their show-time preference and returns later on the same device
- **THEN** their previous choice is still in effect, without being asked again

### Requirement: Client-trusted timing (honour system)
The solved time SHALL be supplied by the player's own browser; the server does not independently
verify it. This is a deliberate trust boundary, not an oversight.

#### Scenario: Server accepts the client's reported time
- **WHEN** a player's browser reports a solve time on stopping the timer
- **THEN** the server stores that time as given, without comparing it to its own timestamps
