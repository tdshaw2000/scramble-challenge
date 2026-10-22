# theming

## Purpose

Covers the visual skin system: how a player picks a skin and how that choice is kept, entirely
separate from gameplay logic. Not part of the original v1 spec — added after launch.

## Requirements

### Requirement: Skin picker
Every screen SHALL offer a gear-menu control letting a player pick from a fixed list of skins.
The list SHALL be shown in a defined menu order, independent of the skin's internal folder name.

#### Scenario: Opening the skin menu
- **WHEN** a player opens the gear menu
- **THEN** they see the available skins by their display label, in menu order: Minimal, Dark,
  DOS, Mario, Monkey, VHS

#### Scenario: Picking a skin
- **WHEN** a player selects a skin from the menu
- **THEN** the chosen skin's styling applies immediately across the app, with no change to
  gameplay state or behavior

### Requirement: Skin persistence
A player's skin choice SHALL persist on their device across visits, independent of which
challenge they are viewing.

#### Scenario: Returning with a previously chosen skin
- **WHEN** a player who previously picked a skin opens the app again later
- **THEN** that skin is applied automatically, without needing to re-pick it

### Requirement: Default skin
A player who has never picked a skin SHALL see the configured default skin.

#### Scenario: First-time visitor
- **WHEN** a visitor with no skin preference recorded opens the app
- **THEN** they see the default skin
