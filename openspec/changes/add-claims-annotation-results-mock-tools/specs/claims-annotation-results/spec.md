## ADDED Requirements

### Requirement: Fetch annotation results by session+document
The system SHALL return claim annotation results when provided session_id and document_id.

#### Scenario: Results found
- **WHEN** a client requests results for a session_id + document_id with labels
- **THEN** the API returns a primary damage_type and the full FINDINGS payload

#### Scenario: No results
- **WHEN** no labels exist for that session_id + document_id
- **THEN** the API returns "no results" with an empty findings payload

### Requirement: Emit claims_annotation_results event
The system SHALL emit an AI session stream event with kind=claims_annotation_results.

#### Scenario: Export results logged
- **WHEN** results are returned
- **THEN** an AI session stream event is written with the findings payload

### Requirement: Post #ai message
The system SHALL post a #ai message with "ok that is {damage_type} damage".

#### Scenario: Message posted
- **WHEN** results are returned
- **THEN** a #ai message is posted with the primary damage_type and FINDINGS JSON

### Requirement: ADK mock tool
The system SHALL provide an ADK tool named claims_annotation_results.

#### Scenario: Tool usage
- **WHEN** the claims agent has session_id + document_id
- **THEN** it calls the tool and includes the result in the tool_history
