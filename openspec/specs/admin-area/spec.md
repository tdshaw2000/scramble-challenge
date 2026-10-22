# admin-area

## Purpose

Covers the site owner's own read-only area for browsing every challenge ever played, separate
from any in-challenge CO role. Not part of the original v1 spec — added after launch.

## Requirements

### Requirement: Admin area availability
The admin area SHALL exist only when both a password hash and a session secret are configured
for the deployment; otherwise it SHALL behave as if it does not exist.

#### Scenario: Not configured
- **WHEN** the deployment has no admin password hash or session secret set
- **THEN** every admin route responds as not found

#### Scenario: Configured
- **WHEN** both are set
- **THEN** the admin routes are reachable, gated by login

### Requirement: Password login with lockout
Access to the admin area SHALL require a single shared password. Repeated wrong attempts from
the same visitor within a time window SHALL be temporarily blocked.

#### Scenario: Correct password
- **WHEN** a visitor submits the configured password
- **THEN** they are logged in and redirected to the admin home page

#### Scenario: Too many wrong attempts
- **WHEN** a visitor has submitted enough wrong passwords within the lockout window
- **THEN** further attempts from them are rejected until the window passes, without re-checking
  the password

### Requirement: Browsing all challenges
Once logged in, the admin SHALL be able to see every challenge ever created, newest first, and
drill into any one of them to see its rounds and results.

#### Scenario: Admin home page
- **WHEN** a logged-in admin visits the admin home page
- **THEN** they see every challenge listed newest first, with its status and page through them
  in fixed-size pages

#### Scenario: Viewing one challenge's detail
- **WHEN** a logged-in admin opens a specific challenge
- **THEN** they see its status, players and points, and every round's leaderboard

### Requirement: Read-only
The admin area SHALL NOT let the admin change any challenge, round, or player data.

#### Scenario: No mutating actions available
- **WHEN** an admin is viewing any admin page
- **THEN** no action on that page can create, edit, or delete game data
