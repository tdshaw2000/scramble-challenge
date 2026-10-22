# round-flow

## Purpose

Covers how the Challenge Owner starts and ends a round, what puzzle gets picked by default,
and the conditions under which a round completes.

## Requirements

### Requirement: Starting a round
Only the CO, and only while the challenge is `waiting` or `round_results`, SHALL be able to
start a round. Starting one generates a scramble, creates the round, and moves every connected
player to the scramble-reveal screen.

#### Scenario: CO starts a round
- **WHEN** the CO selects a puzzle and presses "Start round"
- **THEN** a scramble is generated for that puzzle, a new `Round` row is created in `active`
  status, the challenge's status becomes `round_active`, and every connected player's screen
  switches to show the scramble and an "Start inspection" button

#### Scenario: Non-CO cannot start a round
- **WHEN** a non-CO player attempts to start a round
- **THEN** the action is rejected and no round is created

### Requirement: Puzzle default
Round 1 of a challenge SHALL default to 3x3 (`333`). Round 2 onward SHALL default to whichever
puzzle was used in the immediately preceding round, though the CO can always override it via
the dropdown.

#### Scenario: First round defaults to 3x3
- **WHEN** the CO opens the puzzle dropdown for round 1
- **THEN** 3x3 is pre-selected

#### Scenario: Later round defaults to the previous puzzle
- **WHEN** the CO opens the puzzle dropdown after a round using 4x4 has completed
- **THEN** 4x4 is pre-selected

### Requirement: Round completion
A round SHALL end either when every connected player has a completed solve (timed or DNF), or
when the CO force-ends it.

#### Scenario: Everyone finishes naturally
- **WHEN** every player connected to the round has a recorded solve outcome
- **THEN** the round's status becomes `complete`, its `ended_at` is set, and the challenge's
  status becomes `round_results`

#### Scenario: CO force-ends the round
- **WHEN** the CO presses "End round" while the round is still active
- **THEN** every connected player without a recorded result is given a DNF with no time, the
  round becomes `complete`, and the challenge moves to `round_results`

### Requirement: Round repeat
Once a round is complete, the CO's screen SHALL offer the puzzle dropdown (defaulted per the
puzzle-default rule) and a "Start round" button to begin the next one.

#### Scenario: Starting the next round
- **WHEN** the round-results screen is showing and the CO presses "Start round" again
- **THEN** a new round is created following the same starting-a-round behavior, with the round
  number incremented
