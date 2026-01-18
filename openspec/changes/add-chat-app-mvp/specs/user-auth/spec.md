## ADDED Requirements

### Requirement: User Registration

The system SHALL allow users to register with a unique username and password.

#### Scenario: Successful registration

- **WHEN** a user provides a unique username and valid password
- **THEN** the system creates a new user account
- **AND** stores the password as a bcrypt hash
- **AND** returns a success response

#### Scenario: Duplicate username

- **WHEN** a user tries to register with an existing username
- **THEN** the system returns an error indicating the username is already taken

### Requirement: User Login

The system SHALL allow registered users to log in using their username and password.

#### Scenario: Successful login

- **WHEN** a user provides valid login credentials
- **THEN** the system returns a JWT token
- **AND** stores the token in an HttpOnly cookie

#### Scenario: Invalid credentials

- **WHEN** a user provides invalid login credentials
- **THEN** the system returns an error indicating the credentials are invalid

### Requirement: JWT Authentication

The system SHALL use JWT tokens stored in HttpOnly cookies for authentication.

#### Scenario: Protected API access

- **WHEN** a user makes a request to a protected endpoint
- **AND** includes a valid JWT token in the HttpOnly cookie
- **THEN** the system allows access to the endpoint

#### Scenario: Missing or invalid token

- **WHEN** a user makes a request to a protected endpoint without a valid JWT token
- **THEN** the system returns an unauthorized error

### Requirement: User Status

The system SHALL track user status (online/idle).

#### Scenario: User goes online

- **WHEN** a user logs in or connects to the WebSocket
- **THEN** the system sets the user's status to online

#### Scenario: User goes idle

- **WHEN** a user is inactive for a specified period
- **THEN** the system sets the user's status to idle
