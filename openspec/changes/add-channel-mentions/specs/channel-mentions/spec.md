## ADDED Requirements

### Requirement: Channel Member Mentions

The system SHALL provide an autocomplete dropdown when users type "@" in a channel message input, listing all members in that channel.

#### Scenario: Autocomplete appears on "@" character

- **WHEN** a user types "@" in a channel message input
- **THEN** an autocomplete dropdown appears below the input
- **AND** the dropdown displays all members of the current channel
- **AND** members are sorted by display_name ascending (nulls last), then by username

#### Scenario: Search filtering by id, username, or display_name

- **WHEN** a user types "@" followed by characters (e.g., "@john")
- **THEN** the dropdown filters members matching the search query
- **AND** matching is performed against user id (exact), username (case-insensitive contains), or display_name (case-insensitive contains)

#### Scenario: Keyboard navigation

- **WHEN** the autocomplete dropdown is visible
- **THEN** users can navigate with Arrow Up/Down keys
- **AND** pressing Enter or Tab selects the highlighted member
- **AND** pressing Escape closes the dropdown

#### Scenario: Mouse selection

- **WHEN** the autocomplete dropdown is visible
- **THEN** users can click on a member to select them
- **AND** hovering over a member highlights it

#### Scenario: Member insertion

- **WHEN** a user selects a member from the autocomplete dropdown
- **THEN** the member's display_name (or username if no display_name) is inserted into the input
- **AND** the insertion includes "@" prefix and a trailing space
- **AND** the cursor is positioned after the inserted mention

#### Scenario: Channel change resets state

- **WHEN** a user switches to a different channel
- **THEN** any open autocomplete dropdown is closed
- **AND** the member list is reset for the new channel

#### Scenario: Multiple "@" characters

- **WHEN** a message contains multiple "@" characters
- **THEN** only the last "@" before the cursor position triggers autocomplete
- **AND** autocomplete is disabled if there's a space after the "@" (mention complete)

### Requirement: Channel Members API

The system SHALL provide an endpoint to retrieve channel members with optional search filtering.

#### Scenario: Get all channel members

- **WHEN** a user requests channel members via GET /channels/{channel_id}/members
- **THEN** the system returns all members of that channel
- **AND** members are sorted by display_name ascending (nulls last), then by username
- **AND** the response includes user id, username, and display_name

#### Scenario: Search channel members

- **WHEN** a user requests channel members with a search query parameter
- **THEN** the system filters members matching the search
- **AND** matching is performed against user id (exact match), username (case-insensitive contains), or display_name (case-insensitive contains)

#### Scenario: Membership verification

- **WHEN** a user requests channel members for a channel they are not a member of
- **THEN** the system returns a 403 Forbidden error

### Requirement: Real-Time Member List Updates

The system SHALL update the channel member list when users join or leave channels.

#### Scenario: User joins channel

- **WHEN** a user joins a channel via WebSocket
- **THEN** the channel members query is invalidated
- **AND** the autocomplete dropdown refreshes with the updated member list

#### Scenario: User leaves channel

- **WHEN** a user leaves a channel via WebSocket
- **THEN** the channel members query is invalidated
- **AND** if the autocomplete dropdown is open, it closes
- **AND** the member list is updated to remove the departed user
