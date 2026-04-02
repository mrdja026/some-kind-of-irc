## ADDED Requirements

### Requirement: Claim image documents from MinIO references
The system SHALL allow creation and retrieval of data-processor documents using MinIO claim references without re-uploading files.

#### Scenario: Create document from claim image reference
- **WHEN** the backend submits source_bucket, source_key, source_parent_key, image_url, channel_id, and uploaded_by
- **THEN** the data-processor stores the reference fields and returns a document id.

#### Scenario: Idempotent create by source key
- **WHEN** the backend submits the same source_bucket and source_key again for the same channel
- **THEN** the data-processor returns the existing document id.

### Requirement: Damage annotation review fields
The system SHALL store per-annotation review fields for damage analysis, including verification_status, review_value (boolean or string), and certainty (0.0-1.0).

#### Scenario: Human verified annotation
- **WHEN** a reviewer creates an annotation with verification_status=human_verified and certainty=1.0
- **THEN** the API response includes those fields and persists them for export.

### Requirement: Deep claim review annotation workflow
The system SHALL let reviewers annotate claim images from #ai and bind annotations to the claim root key CLM-2026-0001-data.

#### Scenario: Annotate claim image in deep review
- **WHEN** a reviewer clicks Annotate on a claim image
- **THEN** the annotation modal opens with damage labels and creates annotations bound to the claim root key.

### Requirement: Backend API for AI consumption
The system SHALL expose a backend API to fetch damage annotations by claim id and the AI service SHALL use it.

#### Scenario: ADK tool fetch with logging
- **WHEN** the ADK tool requests damage annotations for a claim id
- **THEN** the backend returns annotations and logs the tool call to the AI session stream.
