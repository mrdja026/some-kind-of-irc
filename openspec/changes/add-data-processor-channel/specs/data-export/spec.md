## ADDED Requirements

### Requirement: JSON Export Format

The system SHALL export labeled regions and extracted text as normalized JSON optimized for AI/ML processing pipelines.

#### Scenario: User exports document as JSON

- **WHEN** a user clicks "Export JSON" for a processed document
- **THEN** the system generates a JSON file containing document ID, source filename, all field extractions with confidence scores, bounding boxes, and processing metadata

#### Scenario: JSON schema structure

- **WHEN** JSON export is generated
- **THEN** the output follows a consistent schema with `document_id`, `source_filename`, `processed_at`, `template_id`, `fields` array, `raw_ocr_text`, and `metadata` object

#### Scenario: Field data in JSON

- **WHEN** a field is included in JSON export
- **THEN** it contains `name`, `type`, `value`, `confidence`, `bounding_box`, and `validation_status`

### Requirement: CSV Export Format

The system SHALL export labeled data as flattened CSV format for spreadsheet and database import.

#### Scenario: User exports document as CSV

- **WHEN** a user clicks "Export CSV" for a processed document
- **THEN** the system generates a CSV file with one row per document and columns for each labeled field

#### Scenario: CSV column headers

- **WHEN** CSV export is generated
- **THEN** columns include `document_id`, `source_filename`, `processed_at`, and dynamic columns for each label name with `_value` and `_confidence` suffixes

#### Scenario: Multiple documents CSV

- **WHEN** batch export includes multiple documents
- **THEN** the CSV contains one row per document with consistent column ordering

### Requirement: SQL Insert Export Format

The system SHALL generate parameterized SQL INSERT statements for direct database import.

#### Scenario: User exports as SQL

- **WHEN** a user clicks "Export SQL" for a processed document
- **THEN** the system generates SQL INSERT statements compatible with common databases ( SQLite)

#### Scenario: SQL format selection

- **WHEN** generating SQL export
- **THEN** the user can select target database dialect for proper escaping and syntax

#### Scenario: Table schema generation

- **WHEN** SQL export is selected
- **THEN** the system optionally generates CREATE TABLE statements based on the current label schema

### Requirement: Validation Workflow

The system SHALL provide a validation interface for reviewing and confirming extracted data before final export.

#### Scenario: User enters validation mode

- **WHEN** a user clicks "Validate Before Export"
- **THEN** the system displays each labeled field with extracted text, confidence score, and edit capability

#### Scenario: Low confidence highlighting

- **WHEN** validation displays fields
- **THEN** fields with confidence < 80% are highlighted in yellow, fields < 50% in red

#### Scenario: User corrects extracted text

- **WHEN** a user edits the extracted text for a field during validation
- **THEN** the corrected value is used in export with `validation_status: "corrected"`

#### Scenario: User approves extraction

- **WHEN** a user clicks "Approve" for a field
- **THEN** the field receives `validation_status: "validated"` in export

#### Scenario: Required field enforcement

- **WHEN** a template has required fields
- **THEN** export is blocked until all required fields are validated or have acceptable values

### Requirement: Batch Processing

The system SHALL support processing multiple documents using a single template with batch export.

#### Scenario: User initiates batch job

- **WHEN** a user uploads multiple document images and selects a template
- **THEN** the system creates a batch job and processes documents sequentially (MVP: one at a time)

#### Scenario: Batch job status tracking

- **WHEN** a batch job is in progress
- **THEN** the user can view status showing total documents, processed count, and failed count

#### Scenario: Batch export completion

- **WHEN** all documents in a batch are processed
- **THEN** the user can export all results as a single combined JSON, CSV, or SQL file

#### Scenario: Batch job failure handling

- **WHEN** a document fails processing in a batch
- **THEN** the failure is logged and the batch continues with remaining documents

### Requirement: Export History

The system SHALL maintain a history of exports performed during the session.

#### Scenario: Export logged

- **WHEN** a user exports document data
- **THEN** the export is recorded with timestamp, format, document ID, and download link

#### Scenario: Re-download previous export

- **WHEN** a user views export history
- **THEN** they can re-download any previous export from the current session

### Requirement: Database-Ready Normalization

The system SHALL normalize extracted data for direct insertion into relational databases and ML training datasets.

#### Scenario: Data type inference

- **WHEN** exporting field values
- **THEN** the system infers appropriate data types (string, number, date) based on label type and content

#### Scenario: Date normalization

- **WHEN** a date-type field is extracted
- **THEN** the system normalizes to ISO 8601 format (YYYY-MM-DD) when possible

#### Scenario: Amount normalization

- **WHEN** an amount-type field is extracted
- **THEN** the system removes currency symbols and normalizes to decimal format

### Requirement: Export API Endpoints

The system SHALL expose export functionality via Django REST Framework endpoints.

#### Scenario: Export endpoint

- **WHEN** client sends POST /api/documents/{id}/export/ with format parameter
- **THEN** the service returns the exported data in the requested format (json, csv, sql)

#### Scenario: Batch export endpoint

- **WHEN** client sends GET /api/batch/{id}/export/ with format parameter
- **THEN** the service returns combined export for all successfully processed documents

#### Scenario: Validation endpoint

- **WHEN** client sends POST /api/documents/{id}/validate/ with field corrections
- **THEN** the service updates field values and validation statuses
