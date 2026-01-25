# media-storage Specification

## Purpose
TBD - created by archiving change add-media-storage. Update Purpose after archive.
## Requirements
### Requirement: Authenticated Image Upload Proxy
The system SHALL accept image uploads through a storage service and verify the user session with the backend before accepting the upload.

#### Scenario: Authenticated upload succeeds
- **WHEN** an authenticated user uploads a jpeg, png, or webp file under 10 MB
- **THEN** the storage service stores the file in MinIO
- **AND** returns the media key and public URL

#### Scenario: Upload rejected without authentication
- **WHEN** a request is made without a valid session
- **THEN** the storage service rejects the upload with an unauthorized response

#### Scenario: Upload rejected for invalid file type
- **WHEN** a file is uploaded with a non-image content type
- **THEN** the storage service rejects the upload with a validation error

#### Scenario: Upload rejected for size limit
- **WHEN** a file exceeds 10 MB
- **THEN** the storage service rejects the upload with a payload-too-large response

### Requirement: Public Media Access via Redirect
The system SHALL expose a public media URL that redirects to the underlying MinIO object URL.

#### Scenario: Media access redirects
- **WHEN** a client requests the public media URL
- **THEN** the service responds with an HTTP 302 redirect to the MinIO object

### Requirement: Media Metadata Response
The system SHALL return media metadata after a successful upload.

#### Scenario: Metadata included
- **WHEN** an upload is accepted
- **THEN** the response includes key, url, contentType, and size

