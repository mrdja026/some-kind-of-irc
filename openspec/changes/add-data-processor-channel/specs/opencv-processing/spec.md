## ADDED Requirements

### Requirement: Image Preprocessing Pipeline

The system SHALL preprocess uploaded document images using OpenCV to improve OCR accuracy, including noise reduction and image enhancement.

#### Scenario: System applies noise reduction

- **WHEN** a document image is uploaded for processing
- **THEN** the system applies Gaussian blur (sigma=1.0) followed by bilateral filtering to reduce noise while preserving edges

#### Scenario: System applies adaptive thresholding

- **WHEN** preprocessing a document image
- **THEN** the system applies adaptive thresholding with Otsu's method fallback to create optimal binarization for OCR

#### Scenario: Preprocessing configuration

- **WHEN** the preprocessing pipeline runs
- **THEN** each step can be enabled/disabled via configuration (noise_reduction, binarization, deskew)

### Requirement: Document Deskewing

The system SHALL automatically detect and correct document rotation using Hough transform line detection.

#### Scenario: System detects skewed document

- **WHEN** a document image is uploaded with rotation angle between -15° and +15°
- **THEN** the system detects the skew angle using Hough line detection and applies affine transformation to correct it

#### Scenario: Severely skewed document

- **WHEN** a document has rotation greater than ±15°
- **THEN** the system returns the original image with a warning that manual rotation may be required

#### Scenario: Deskew angle reported

- **WHEN** deskewing is applied
- **THEN** the detected rotation angle is included in the processing metadata

### Requirement: Image Size Constraints

The system SHALL enforce maximum image dimensions of 1024x1024 pixels, automatically resizing larger images.

#### Scenario: Large image uploaded

- **WHEN** a user uploads an image larger than 1024x1024 pixels
- **THEN** the system resizes the image to fit within 1024x1024 while maintaining aspect ratio

#### Scenario: Image resize notification

- **WHEN** an image is automatically resized
- **THEN** the system includes original and new dimensions in the response metadata

### Requirement: PDF Ingestion and Text Layer Extraction

The system SHALL accept PDF uploads, extract the first page for processing, and capture the PDF text layer when available.

#### Scenario: PDF first-page rasterization

- **WHEN** a user uploads a PDF document
- **THEN** the system reads the PDF page count and rasterizes page 1 to an image within the 1024x1024 size limit

#### Scenario: PDF text layer extraction

- **WHEN** the uploaded PDF contains selectable text on page 1
- **THEN** the system extracts the text layer and stores it in the document metadata for downstream export

#### Scenario: PDF without text layer

- **WHEN** the uploaded PDF has no selectable text on page 1
- **THEN** the system records an empty text layer and proceeds with OCR on the rasterized image

### Requirement: Optical Character Recognition

The system SHALL perform OCR text extraction using Tesseract on preprocessed document images.

#### Scenario: Full document OCR

- **WHEN** document preprocessing completes
- **THEN** Tesseract OCR extracts all text from the preprocessed image with confidence scores

#### Scenario: Region-specific OCR

- **WHEN** a user creates an annotation bounding box
- **THEN** the system performs OCR on the specific region and associates extracted text with the annotation

#### Scenario: OCR confidence reporting

- **WHEN** OCR extraction completes
- **THEN** each extracted text segment includes a confidence score (0.0-1.0)

### Requirement: Automatic Region Detection

The system SHALL automatically detect common document elements (text blocks, tables, images) using contour analysis.

#### Scenario: Text block detection

- **WHEN** a document is processed
- **THEN** the system identifies rectangular text block regions and suggests them as potential annotation areas

#### Scenario: Table detection

- **WHEN** a document contains tabular data with visible grid lines
- **THEN** the system detects table boundaries and suggests table-type annotation

#### Scenario: Detection suggestions

- **WHEN** automatic detection completes
- **THEN** detected regions are presented as suggestions that users can accept, modify, or dismiss

### Requirement: Coordinate Mapping

The system SHALL map coordinates between visual annotations and extracted text content for precise alignment.

#### Scenario: Annotation to text mapping

- **WHEN** a user creates an annotation bounding box
- **THEN** the system maps the visual coordinates to the corresponding OCR text extraction area

#### Scenario: Text position reporting

- **WHEN** OCR extracts text from a region
- **THEN** character-level bounding boxes are available for highlighting matched text in the viewer

### Requirement: Concurrent Processing

The system SHALL process documents one at the time for the mvp, and only one is allowed to upload and work on, label it with for example Shiping data label tied to a box that we drawed while users interact with the annotation interface.

#### Scenario: Background OCR processing

- **WHEN** a document is uploaded
- **THEN** OCR processing begins immediately in the background while the user can start annotating

#### Scenario: Processing progress updates

- **WHEN** OCR processing is in progress
- **THEN** the frontend receives progress updates (preprocessing, detection, extraction, mapping stages) via API polling or WebSocket

#### Scenario: Processing completion notification

- **WHEN** OCR processing completes
- **THEN** the frontend receives an event with detected regions and extracted text

### Requirement: Django REST Framework API

The system SHALL expose OCR processing capabilities via Django REST Framework endpoints in the data-processor microservice.

#### Scenario: Document upload endpoint

- **WHEN** a client sends POST /api/documents/ with image or PDF data
- **THEN** the service stores the first-page image in-memory (rasterized if PDF) and begins preprocessing/OCR pipeline

#### Scenario: Processing status endpoint

- **WHEN** a client sends GET /api/documents/{id}/
- **THEN** the service returns document status (pending, processing, completed, failed) and results if available

#### Scenario: Service health check

- **WHEN** a client sends GET /health
- **THEN** the service returns 200 OK with OCR engine version information
