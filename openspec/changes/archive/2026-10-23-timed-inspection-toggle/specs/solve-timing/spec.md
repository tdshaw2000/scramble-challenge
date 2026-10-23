# Spec Delta

## MODIFIED Requirements

### Requirement: WCA-style inspection
For a round started with timed inspection on, starting a solve SHALL apply WCA inspection
timing: no penalty within 15 seconds, a +2 penalty between 15 and 17 seconds, and a DNF if 17
seconds pass with no solve started. Inspection timing is decided by the browser, not the server.

#### Scenario: Starting within 15 seconds
- **WHEN** a player starts their solve before the 15-second mark in a timed-inspection round
- **THEN** no penalty is applied

#### Scenario: Starting between 15 and 17 seconds
- **WHEN** a player starts their solve between 15 and 17 seconds into inspection in a
  timed-inspection round
- **THEN** the solve is recorded with a +2 penalty

#### Scenario: Inspection times out
- **WHEN** 17 seconds of inspection pass with no solve started in a timed-inspection round
- **THEN** the player's solve is recorded as a DNF with no time, and the leaderboard updates
  immediately

## ADDED Requirements

### Requirement: Untimed inspection
For a round started with timed inspection off, a player SHALL be able to start their solve at
any point after pressing "Start inspection", with no countdown, no +2 penalty, and no
inspection-timeout DNF.

#### Scenario: Starting an untimed-inspection round
- **WHEN** a player presses "Start inspection" in a round where timed inspection is off
- **THEN** no countdown or inspection-expiry penalty applies, and the player can start their
  solve whenever they are ready

#### Scenario: A full untimed solve
- **WHEN** a player starts and stops their solve timer in an untimed-inspection round
- **THEN** a timed result is recorded with no +2 penalty, the same as any other solve
