# Spec Delta

## MODIFIED Requirements

### Requirement: Starting a round
Only the CO, and only while the challenge is `waiting` or `round_results`, SHALL be able to
start a round. Starting one generates a scramble, creates the round with the CO's chosen puzzle
and timed-inspection setting, and moves every connected player to the scramble-reveal screen.

#### Scenario: CO starts a round
- **WHEN** the CO selects a puzzle, leaves or sets the timed-inspection switch, and presses
  "Start round"
- **THEN** a scramble is generated for that puzzle, a new `Round` row is created in `active`
  status with the chosen timed-inspection setting, the challenge's status becomes
  `round_active`, and every connected player's screen switches to show the scramble and a
  "Start inspection" button

#### Scenario: Non-CO cannot start a round
- **WHEN** a non-CO player attempts to start a round
- **THEN** the action is rejected and no round is created

## ADDED Requirements

### Requirement: Timed inspection default
Round 1 of a challenge SHALL default the timed-inspection switch to on. Round 2 onward SHALL
default to whichever setting was used in the immediately preceding round, though the CO can
always override it via the switch before starting.

#### Scenario: First round defaults to timed inspection on
- **WHEN** the CO opens the lobby for round 1
- **THEN** the timed-inspection switch is on

#### Scenario: Later round defaults to the previous round's setting
- **WHEN** the CO reaches the lobby after a round that was started with timed inspection off
- **THEN** the timed-inspection switch is off

#### Scenario: CO overrides the default
- **WHEN** the CO flips the timed-inspection switch before pressing "Start round"
- **THEN** the round starts with the switch's new setting, not the carried-forward default
