## ADDED Requirements

### Requirement: Interactive Document Annotation Modal

The system SHALL display an interactive popup modal when a user uploads an image file (PNG, JPG, or PDF image) in a data-processor channel, presenting the uploaded document alongside annotation tools.

#### Scenario: User uploads image to data-processor channel

- **WHEN** a user uploads an image file to a channel marked as data-processor type
- **THEN** the system displays a fullscreen modal with the document image and annotation toolbar

#### Scenario: User uploads non-image file to data-processor channel

- **WHEN** a user uploads a non-image file (e.g., .txt, .doc) to a data-processor channel
- **THEN** the system handles the upload as a regular file without triggering the annotation modal

#### Scenario: Modal closes without saving

- **WHEN** a user closes the annotation modal without explicitly saving
- **THEN** the system prompts for confirmation and discards unsaved annotations if confirmed

### Requirement: Document Viewer Controls

The system SHALL provide pan and zoom controls for navigating large document images within the annotation modal.

#### Scenario: User zooms document

- **WHEN** a user scrolls the mouse wheel or uses pinch gesture over the document
- **THEN** the document zooms in or out centered on the cursor position

#### Scenario: User pans document

- **WHEN** a user clicks and drags on the document canvas (outside annotation boxes)
- **THEN** the document view pans in the drag direction

#### Scenario: User resets view

- **WHEN** a user clicks the "Fit to Window" button
- **THEN** the document scales to fit the available viewport while maintaining aspect ratio

### Requirement: Bounding Box Drawing

The system SHALL allow users to draw rectangular bounding boxes on the document to define regions of interest.

#### Scenario: User draws new bounding box

- **WHEN** a user clicks and drags on the document canvas
- **THEN** a new rectangular bounding box appears following the drag area with the currently selected label type and color

#### Scenario: User resizes existing bounding box

- **WHEN** a user clicks and drags a corner or edge handle of an existing bounding box
- **THEN** the bounding box resizes proportionally from the opposite anchor point

#### Scenario: User moves bounding box

- **WHEN** a user clicks and drags the interior of an existing bounding box
- **THEN** the bounding box moves to follow the cursor while maintaining its dimensions

#### Scenario: User deletes bounding box

- **WHEN** a user selects a bounding box and presses Delete key or clicks the delete button
- **THEN** the bounding box is removed from the document annotations

### Requirement: Label Type Selection

The system SHALL provide predefined label types with color coding: header (blue), table (green), signature (purple), date (orange), amount (red), and custom (user-selectable color).

#### Scenario: User selects label type before drawing

- **WHEN** a user clicks a label type button in the toolbar before drawing
- **THEN** newly drawn bounding boxes use the selected type and its associated color

#### Scenario: User changes label type of existing box

- **WHEN** a user selects an existing bounding box and chooses a different label type
- **THEN** the bounding box color updates to match the new label type

#### Scenario: User creates custom label

- **WHEN** a user selects "Custom" label type and enters a custom name
- **THEN** the system saves the custom label with a user-selected color and makes it available for future annotations

### Requirement: Label Name Assignment

The system SHALL allow users to assign meaningful names to each annotated region beyond the label type.

#### Scenario: User assigns label name

- **WHEN** a user creates or selects a bounding box
- **THEN** a text input allows entering a descriptive name (e.g., "Invoice Number", "Total Amount")

#### Scenario: User views annotation list

- **WHEN** a user opens the annotation panel
- **THEN** all annotations are listed with their label type, name, and extracted text preview

### Requirement: Annotation Persistence

The system SHALL persist annotations in-memory during the document session and allow export before closing.

#### Scenario: User saves annotations

- **WHEN** a user clicks "Save" in the annotation modal
- **THEN** all annotations are saved to the data-processor service's in-memory storage

#### Scenario: User reopens saved document

- **WHEN** a user reopens a previously annotated document within the same session
- **THEN** all saved annotations appear on the document with their original positions and labels

### Requirement: Channel Type Configuration

The system SHALL allow channel creators to designate a channel as a data-processor channel via a checkbox during channel creation.

#### Scenario: User creates data-processor channel

- **WHEN** a user creates a new channel and checks the "Data Processing Channel" checkbox
- **THEN** the channel is created with `channel_type: data_processor` and displays a specialized icon in the sidebar

#### Scenario: User uploads to regular channel

- **WHEN** a user uploads an image to a regular (non-data-processor) channel
- **THEN** the image is uploaded as a standard media attachment without triggering the annotation modal
