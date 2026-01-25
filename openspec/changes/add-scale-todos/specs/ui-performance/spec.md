## ADDED Requirements
### Requirement: Message pagination and virtualization
The system SHALL paginate message history and the UI SHALL virtualize long message lists to maintain responsiveness.

#### Scenario: Channel with large history
- **WHEN** a channel contains more messages than a single page
- **THEN** the API returns a paginated response and the UI renders messages using virtualization.
