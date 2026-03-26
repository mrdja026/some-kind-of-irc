## MODIFIED Requirements
### Requirement: Authenticated Image Upload Proxy
The system SHALL accept image uploads at `POST /media/upload` on the media-storage service and verify the user session with the backend before accepting the upload.

#### Scenario: Authenticated upload succeeds
- **WHEN** an authenticated user uploads a jpeg, png, or webp file under 10 MB to `POST /media/upload`
- **THEN** the storage service stores the file in MinIO
- **AND** returns the media key and public URL

#### Scenario: Upload rejected without authentication
- **WHEN** a request is made without a valid session to `POST /media/upload`
- **THEN** the storage service rejects the upload with an unauthorized response

#### Scenario: Upload rejected for invalid file type
- **WHEN** a file is uploaded with a non-image content type to `POST /media/upload`
- **THEN** the storage service rejects the upload with a validation error

#### Scenario: Upload rejected for size limit
- **WHEN** a file exceeds 10 MB at `POST /media/upload`
- **THEN** the storage service rejects the upload with a payload-too-large response
