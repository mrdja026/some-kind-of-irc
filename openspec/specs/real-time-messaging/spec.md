# real-time-messaging Specification

## Purpose
TBD - created by archiving change add-media-storage. Update Purpose after archive.
## Requirements
### Requirement: Message Image Reference
The system SHALL allow messages to include an optional image_url field referencing uploaded media.

#### Scenario: Message sent with image URL
- **WHEN** a user sends a message with an image_url
- **THEN** the message is persisted with the image_url
- **AND** the image_url is included in message broadcasts

#### Scenario: Message retrieved without image URL
- **WHEN** a message has no image_url
- **THEN** the message response omits the field or returns it as null

