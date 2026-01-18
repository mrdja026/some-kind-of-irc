## ADDED Requirements

### Requirement: Sidebar for Channel/User List

The system SHALL display a sidebar with a list of channels and users.

#### Scenario: Channel list display

- **WHEN** a user is logged in
- **THEN** the sidebar shows a list of available channels
- **AND** the user's current channel is highlighted

#### Scenario: User list display

- **WHEN** a user is in a channel
- **THEN** the sidebar shows a list of users in that channel

### Requirement: Main Chat Area

The system SHALL display a main chat area for viewing and sending messages.

#### Scenario: Message rendering

- **WHEN** a message is received
- **THEN** the message is displayed in the chat area with the sender's username and timestamp

#### Scenario: Big number of messages -

- **WHEN** there will be a pool system that if you are in the last 20 % of view get more if there is more, but not virtualized just add to list for mvp
- **THEN** efficiantly display the messages with add to list, for mvp to measure

#### Scenario: Virtualized message list - low prio - out of scope for mvp

- **WHEN** there are a large number of messages in the chat history
- **THEN** the system uses virtualization to efficiently render the message list

### Requirement: Infinite Scroll

The system SHALL support infinite scroll for loading older messages.

#### Scenario: Load more messages

- **WHEN** a user scrolls to the top of the message list
- **THEN** the system fetches and displays older messages

#### Scenario: No more messages

- **WHEN** a user scrolls to the very beginning of the message history
- **THEN** the system indicates that there are no more messages to load

### Requirement: Responsive Design

The system SHALL be responsive and work well on different screen sizes.

#### Scenario: Desktop view

- **WHEN** the app is viewed on a desktop browser (width > 768px)
- **THEN** the sidebar and chat area are displayed side by side

#### Scenario: Mobile view

- **WHEN** the app is viewed on a mobile device (width ≤ 768px)
- **THEN** the sidebar is hidden by default and can be toggled

### Requirement: IRC-style UI Vibe

The system SHALL have a user interface that mimics the IRC "vibe".

#### Scenario: Minimalist design

- **WHEN** the app is rendered
- **THEN** the UI has a clean, minimalist design with simple colors and fonts

#### Scenario: Text-based interface

- **WHEN** messages are displayed
- **THEN** they are primarily text-based with minimal formatting
