## ADDED Requirements

### Requirement: WebSocket Connection

The system SHALL provide a WebSocket endpoint for real-time communication.

#### Scenario: Successful connection

- **WHEN** a user connects to the WebSocket endpoint at /ws/{client_id}
- **THEN** the system accepts the connection
- **AND** registers the client for message broadcasting

#### Scenario: Connection failure

- **WHEN** a user attempts to connect with an invalid client_id or token
- **THEN** the system rejects the connection

### Requirement: Real-Time Message Broadcasting

The system SHALL broadcast messages to all connected clients in the same channel.

#### Scenario: Message sent to channel

- **WHEN** a user sends a message to a specific channel
- **THEN** the system broadcasts the message to all connected clients in that channel
- **AND** the message appears in the chat UI of all recipients

#### Scenario: Direct message

- **WHEN** a user sends a direct message to another user
- **THEN** the system sends the message only to the intended recipient

### Requirement: Optimistic UI Updates

The system SHALL display messages immediately on the sender's UI before confirmation.

#### Scenario: Optimistic message display

- **WHEN** a user sends a message
- **THEN** the message appears in the chat UI immediately (optimistically)
- **AND** the system sends the message to the server
- **AND** updates the UI with the confirmed message data

#### Scenario: Message sending failure

- **WHEN** a message fails to send
- **THEN** the system removes the optimistic message from the UI
- **AND** displays an error to the user

### Requirement: Typing Indicators

The system SHALL display typing indicators when a user is typing.

#### Scenario: User starts typing

- **WHEN** a user starts typing in a channel
- **THEN** the system sends a typing indicator to all other connected clients in that channel
- **AND** the indicator is displayed in the chat UI

#### Scenario: User stops typing

- **WHEN** a user stops typing for a specified period
- **THEN** the system removes the typing indicator from the chat UI
