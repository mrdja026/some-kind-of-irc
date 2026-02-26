## ADDED Requirements

### Requirement: Proxied Document Preview URLs
The system SHALL return document preview URLs routed through the primary proxy host to avoid cross-origin restrictions in the annotation canvas.

#### Scenario: Document preview uses proxy base
- **WHEN** a document upload succeeds in a data-processor channel
- **THEN** the `image_url` uses the proxy base URL and is usable by the annotation canvas

### Requirement: Annotation Canvas Initialization
The system SHALL initialize the annotation canvas only after the rendering library is ready and keep it active when switching between tools.

#### Scenario: User switches to draw after image load
- **WHEN** the document preview has rendered and the user switches to Draw
- **THEN** the user can create a bounding box without reloading the image
