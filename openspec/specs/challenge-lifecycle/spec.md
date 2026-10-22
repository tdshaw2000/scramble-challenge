# challenge-lifecycle

## Purpose

Covers how a challenge is created, how others join it (including mid-round), how the owner's
absence is handled, how a challenge ends, and how it's shared and reviewed afterward.

## Requirements

### Requirement: Challenge creation
A visitor at the root URL who enters a name and starts a new challenge becomes its Challenge
Owner (CO). The system SHALL create a `Challenge` row (`status: waiting`) and a `Player` row for
the CO (`is_co: true`), and set a device-identity cookie for them.

#### Scenario: Starting a new challenge
- **WHEN** a visitor enters a display name and presses "Start new challenge"
- **THEN** a new challenge is created in `waiting` status with that visitor as CO, and their
  browser shows the share/QR buttons, puzzle dropdown, "Start round" button, and a players list
  containing only themselves

### Requirement: Joining via the challenge link
Anyone opening a challenge's link SHALL be prompted for a name unless they already hold a
device-identity cookie scoped to that challenge, in which case they rejoin as the same player.

#### Scenario: New visitor joins
- **WHEN** a visitor with no cookie for this challenge opens the link and submits a name
- **THEN** a `Player` row is created for them, a device-identity cookie is set, and everyone
  currently viewing the challenge sees the players list update live

#### Scenario: Returning visitor rejoins
- **WHEN** a visitor who already has a device-identity cookie for this challenge opens the link
  again
- **THEN** they rejoin as their existing `Player` row rather than being prompted for a name

#### Scenario: Remembered display name
- **WHEN** a visitor has previously entered a display name on this device (for any challenge)
- **THEN** the name entry field is pre-filled with that remembered name, read from a separate
  long-lived cookie independent of any specific challenge

### Requirement: Mid-round joins
A player who joins while a round is already active SHALL receive that round's scramble
immediately rather than waiting for the next round.

#### Scenario: Joining during an active round
- **WHEN** a visitor joins a challenge whose status is `round_active`
- **THEN** their screen shows the current round's scramble and an "Start inspection" button, the
  same as players who were present when the round started

### Requirement: Challenge Owner absence grace period
If the CO's connection drops, the challenge SHALL NOT end immediately. The system SHALL record
when the CO's last connection closed and end the challenge automatically only if the CO has not
reconnected within a fixed grace period.

#### Scenario: CO reconnects within the grace period
- **WHEN** the CO's socket disconnects (e.g. a page refresh) and they reconnect before the grace
  period elapses
- **THEN** the challenge continues unaffected and the recorded absence is cleared

#### Scenario: CO does not return within the grace period
- **WHEN** the CO's socket disconnects and they have not reconnected once the grace period
  elapses
- **THEN** the challenge ends automatically, the same way an explicit "End challenge" does

### Requirement: Explicit challenge end
The CO SHALL be able to end the challenge for everyone from the round-results screen, with a
confirmation step.

#### Scenario: CO ends the challenge
- **WHEN** the CO presses "End challenge" and confirms "End the challenge for everyone?"
- **THEN** the challenge's status becomes `ended`, everyone currently connected is notified, and
  their pages move to the challenge summary

#### Scenario: A page opens an already-ended challenge
- **WHEN** anyone opens the challenge's join link or its original room after it has ended
- **THEN** they are routed to the challenge summary rather than the waiting room

### Requirement: Sharing the challenge link
The waiting-room screen SHALL offer the CO a QR code of the challenge link and a share-link
control, so other players can join without the CO reading out a URL.

#### Scenario: CO shows the QR code
- **WHEN** the CO presses "QR code"
- **THEN** a QR code encoding the shareable challenge link is displayed, closable by tapping
  outside it

#### Scenario: CO shares the link
- **WHEN** the CO presses "Share link" on a device with share support
- **THEN** the device's native share sheet opens with the challenge link; on a device without
  share support, the link is copied to the clipboard instead

### Requirement: Challenge summary page
Once a challenge has ended, its link SHALL lead to a summary page showing final standings and
every round played, available to anyone with the link regardless of how the challenge ended.

#### Scenario: Viewing the summary after the challenge ends
- **WHEN** anyone opens the challenge's link once it has ended
- **THEN** they see "This challenge has ended," the final standings ranked by points (ties
  sharing a place), and a "View rounds" control that reveals each round's puzzle, scramble and
  results

#### Scenario: Summary with no rounds played
- **WHEN** a challenge ends with zero rounds ever started
- **THEN** the summary shows the ended state and standings with no players ranked, and no "View
  rounds" control is shown
