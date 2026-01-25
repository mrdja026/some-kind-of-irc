## ADDED Requirements
### Requirement: Redis-backed WebSocket fanout
The system SHALL publish chat events to Redis so multiple backend instances can deliver messages to connected clients.

#### Scenario: Message broadcast across replicas
- **WHEN** a message is persisted for a channel
- **THEN** the backend publishes the channel event to Redis and each WebSocket server forwards it to connected clients.
