## ADDED Requirements
### Requirement: Asynchronous upload processing
The media storage service SHALL emit upload events to Redis and respond before any non-essential processing completes.

#### Scenario: Upload accepted
- **WHEN** a client uploads a supported file
- **THEN** the service stores the object, emits an upload event to Redis, and returns a response without waiting for background processing.
