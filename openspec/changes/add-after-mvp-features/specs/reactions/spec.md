## ADDED Requirements

### Requirement: Emoji reactions
The system SHALL allow users to add and remove emoji reactions on messages.

#### Scenario: Add reaction
- **WHEN** a user selects an emoji reaction for a message
- **THEN** the reaction is recorded and displayed on the message

#### Scenario: Remove reaction
- **WHEN** a user removes their emoji reaction
- **THEN** the reaction count is decremented and the UI updates
