## ADDED Requirements

### Requirement: Template Creation

The system SHALL allow users to save annotation configurations (label positions, types, and names) as reusable templates for similar documents.

#### Scenario: User saves current annotations as template

- **WHEN** a user clicks "Save as Template" with annotations defined on a document
- **THEN** the system creates a template storing all label definitions with relative positions (0.0-1.0 normalized coordinates)

#### Scenario: Template naming

- **WHEN** a user saves a template
- **THEN** the system prompts for a template name and optional description

#### Scenario: Template thumbnail generation

- **WHEN** a template is saved
- **THEN** the system generates a thumbnail preview showing the template layout overlaid on a sample document

### Requirement: Template Storage (In-Memory MVP)

The system SHALL store templates in-memory within the data-processor microservice for MVP, scoped to the channel.

#### Scenario: Template persistence during session

- **WHEN** a template is saved
- **THEN** the template remains available for the duration of the server session

#### Scenario: Channel-scoped templates

- **WHEN** a user accesses templates
- **THEN** only templates created within the same channel are visible

#### Scenario: Template data cleared on restart

- **WHEN** the data-processor service restarts
- **THEN** all in-memory templates are cleared (MVP limitation)

### Requirement: Template Listing and Selection

The system SHALL display available templates for users to select when processing new documents.

#### Scenario: User views template list

- **WHEN** a user opens the template panel
- **THEN** all channel templates are displayed with name, thumbnail, and creation date

#### Scenario: User selects template

- **WHEN** a user clicks on a template in the list
- **THEN** the template details expand showing all defined labels and their expected positions

### Requirement: Template Application

The system SHALL apply selected template label configurations to new documents, positioning bounding boxes based on relative coordinates.

#### Scenario: Simple template application

- **WHEN** a user applies a template to a document of similar dimensions
- **THEN** template bounding boxes are placed at the corresponding relative positions on the new document

#### Scenario: Different aspect ratio handling

- **WHEN** a template is applied to a document with different aspect ratio
- **THEN** bounding boxes are scaled proportionally and users are notified of potential misalignment

#### Scenario: Template applied to all PDF pages

- **WHEN** multi-page PDF support is enabled and a template is applied to a PDF document
- **THEN** the same template labels apply to every page by default

### Requirement: Feature Matching for Template Alignment

The system SHALL use ORB feature matching with RANSAC homography to intelligently adjust template bounding boxes for minor layout variations.

#### Scenario: Template matching with layout variation

- **WHEN** a template is applied to a document with minor layout differences
- **THEN** the system uses ORB feature matching to detect corresponding regions and adjusts bounding box positions accordingly

#### Scenario: High confidence match

- **WHEN** feature matching confidence is >= 60%
- **THEN** the system automatically applies adjusted bounding boxes with a success indicator

#### Scenario: Low confidence match

- **WHEN** feature matching confidence is < 60%
- **THEN** the system falls back to relative coordinate placement and prompts user to verify positions

#### Scenario: Manual anchor point selection

- **WHEN** automatic matching fails or user requests manual alignment
- **THEN** the user can select 3+ anchor points on both template and target document for manual homography calculation

### Requirement: Template Version Control

The system SHALL maintain version history for templates, allowing users to track changes over time.

#### Scenario: Template update creates new version

- **WHEN** a user modifies and saves an existing template
- **THEN** a new version is created while preserving the previous version in history

#### Scenario: Version history display

- **WHEN** a user views template details
- **THEN** version history shows version number, change timestamp, and change reason

#### Scenario: Revert to previous version

- **WHEN** a user selects a previous version from history
- **THEN** that version becomes the active template configuration

### Requirement: Template Label Definitions

The system SHALL store template labels with validation patterns and required/optional status.

#### Scenario: Required field marking

- **WHEN** a user creates a template label
- **THEN** they can mark the field as required, triggering validation warnings if not filled during processing

#### Scenario: Expected format pattern

- **WHEN** a user defines a template label
- **THEN** they can specify a regex pattern for expected content format (e.g., date format, currency pattern)

#### Scenario: Format validation on extraction

- **WHEN** text is extracted for a label with expected format
- **THEN** the system validates against the pattern and flags mismatches for user review

### Requirement: Template API Endpoints

The system SHALL expose template management via Django REST Framework endpoints.

#### Scenario: Create template endpoint

- **WHEN** client sends POST /api/templates/ with template data
- **THEN** the service creates a new template and returns its ID

#### Scenario: List templates endpoint

- **WHEN** client sends GET /api/templates/?channel_id={id}
- **THEN** the service returns all templates for the specified channel

#### Scenario: Apply template endpoint

- **WHEN** client sends POST /api/documents/{id}/apply-template/ with template_id
- **THEN** the service applies the template and returns adjusted bounding boxes with confidence scores
