## MODIFIED Requirements
### Requirement: Authenticated Image Upload Proxy
The system SHALL accept image uploads through a storage service and verify the user session with the backend before accepting the upload. The storage service SHALL store an original variant capped at 3840x2160 and a display variant capped at 1920x1080 while preserving aspect ratio and avoiding upscaling. The response SHALL return the display variant key and public URL.

#### Scenario: Authenticated upload succeeds
- **WHEN** an authenticated user uploads a jpeg, png, or webp file under 10 MB
- **THEN** the storage service stores both original and display variants in MinIO using the configured size caps
- **AND** returns the display media key and public URL

#### Scenario: Upload smaller than display cap
- **WHEN** an uploaded image is already within the 1920x1080 bounds
- **THEN** the display variant matches the original without upscaling

#### Scenario: Upload rejected without authentication
- **WHEN** a request is made without a valid session
- **THEN** the storage service rejects the upload with an unauthorized response

#### Scenario: Upload rejected for invalid file type
- **WHEN** a file is uploaded with a non-image content type
- **THEN** the storage service rejects the upload with a validation error

#### Scenario: Upload rejected for size limit
- **WHEN** a file exceeds 10 MB
- **THEN** the storage service rejects the upload with a payload-too-large response

### Requirement: Media Metadata Response
The system SHALL return media metadata after a successful upload and the metadata SHALL refer to the display variant.

#### Scenario: Metadata included
- **WHEN** an upload is accepted
- **THEN** the response includes key, url, contentType, and size for the display variant
