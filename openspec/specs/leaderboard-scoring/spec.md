# leaderboard-scoring

## Purpose

Covers how solves are ranked and displayed live, how a player can correct their own result
after the fact, and how points accumulate across a challenge.

## Requirements

### Requirement: Live leaderboard
As each solve completes, everyone viewing the results SHALL see the leaderboard update and
re-sort, without reloading the page.

#### Scenario: A solve completes mid-round
- **WHEN** any player's solve is recorded (timed or DNF)
- **THEN** all connected players viewing the round see the leaderboard re-sorted to include it

### Requirement: Tied ranking
Two results that match to the hundredth, after any +2 is applied, SHALL share the same rank.
Times are truncated to hundredths, never rounded, before comparing.

#### Scenario: Two players tie for first
- **WHEN** two players' counted times are equal to the hundredth
- **THEN** both are shown at rank 1, and the next distinct time is shown at rank 3, not rank 2

#### Scenario: DNFs rank after all timed results
- **WHEN** a round has both timed results and DNFs
- **THEN** every DNF is listed after every timed result, regardless of when it was recorded

### Requirement: Self-correcting a result
A player whose solve has a time SHALL be able to toggle +2 and DNF on their own most recent
result, until the next round starts. No player can change another player's result.

#### Scenario: Player adds a +2 after the fact
- **WHEN** a player's own timed solve has no +2 and they toggle +2 on
- **THEN** 2 seconds are added wherever that time is counted, shown, or ranked, and the
  leaderboard updates for everyone

#### Scenario: Player marks their own solve DNF
- **WHEN** a player toggles DNF on their own timed solve
- **THEN** the solve counts as a DNF while keeping its original timed value, so turning DNF off
  again restores the time

#### Scenario: +2 cannot be toggled while DNF is on
- **WHEN** a player's solve currently has DNF toggled on
- **THEN** the +2 toggle is disabled until DNF is turned off

#### Scenario: Toggling after the round moves on
- **WHEN** the next round has already started
- **THEN** the player's prior-round result can no longer be toggled

### Requirement: Points
Winning a round SHALL award one point, shared by everyone tied for first; a round where every
player DNFs SHALL award no points. Points are computed from completed rounds, not stored.

#### Scenario: Single winner
- **WHEN** one player has the fastest counted time in a completed round
- **THEN** they receive one point for that round

#### Scenario: Tied winners
- **WHEN** two or more players tie for the fastest counted time in a completed round
- **THEN** each of them receives one point for that round

#### Scenario: All DNF round
- **WHEN** every player's result in a completed round is a DNF
- **THEN** no points are awarded for that round

#### Scenario: Points shown alongside names
- **WHEN** a player's name is shown anywhere in the app (players list, leaderboard, summary,
  admin pages)
- **THEN** their accumulated points are shown in brackets after their name, e.g. "Amy (2)"
