## ADDED Requirements

### Requirement: Global Channels

The system SHALL support global public channels that users can join.

#### Scenario: Join existing channel

- **WHEN** a user sends the /join #channel command
- **AND** the channel exists
- **THEN** the user is added to the channel
- **AND** the user can send/receive messages in the channel
- **AND** welcomed to that channel with the message welcome to #channel

#### Scenario: Create new channel

- **WHEN** a user sends the /join #newchannel command
- **AND** the channel does not exist
- **THEN** the system creates a new public channel
- **AND** the user is added to the channel

### Requirement: Direct Messages

The system SHALL support private 1:1 messaging between users.

#### Scenario: Start direct message

- **WHEN** a user sends a message to another user
- **AND** the recipient is online
- **AND** sound is heard
- **THEN** the message is delivered to the recipient's direct message interface

#### Scenario: Direct message history

- **WHEN** a user opens a direct message with another user
- **THEN** the system displays the message history for that conversation

### Requirement: Slash Commands

The system SHALL support basic IRC-style slash commands.

#### Scenario: /join command

- **WHEN** a user types /join #channel
- **THEN** the user joins the specified channel

#### Scenario: /nick command

- **WHEN** a user types /nick newusername
- **AND** the new username is unique
- **THEN** the user's username is updated
- **AND** all connected clients see the new username

#### Scenario: /me command

- **WHEN** a user types /me does something
- **THEN** the message is displayed as an action in the chat

### Requirement: Channel Membership

The system SHALL track which users are in each channel.

#### Scenario: Channel user list

- **WHEN** a user views a channel
- **THEN** the system displays a list of users currently in that channel

#### Scenario: User joins channel

- **WHEN** a user joins a channel
- **THEN** all other users in the channel see the user join notification

#### Scenario: User leaves channel

- **WHEN** a user leaves a channel
- **THEN** all other users in the channel see the user leave notification
