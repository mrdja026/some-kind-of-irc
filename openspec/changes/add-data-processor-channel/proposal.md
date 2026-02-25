# Change: Add #data-processor channel for document annotation and OCR extraction

## Why

The IRC application needs a specialized channel type for document processing workflows. Users frequently need to upload PDF images, annotate regions of interest (headers, tables, signatures, amounts), extract text via OCR, and export structured data for downstream AI/ML pipelines. This capability transforms the chat application into a collaborative document processing hub, enabling teams to standardize data extraction workflows and share reusable templates.

## What Changes

### New Channel Type

- Add `#data-processor` as a specialized channel type with document processing capabilities
- Automatic popup modal triggered when users upload image files (PNG, JPG) or PDFs (first page preview)
- Interactive document viewer with pan, zoom, and annotation tools
- Extract and store the PDF text layer when available

### Document Annotation System

- Color-coded bounding box annotation tools for defining regions of interest
- Built-in label types: header, table, signature, date, amount, custom
- Region grouping and hierarchical labeling support
- Real-time annotation synchronization across channel members

### Backend OCR Pipeline (OpenCV)

- PDF ingestion: rasterize first page to image and capture text layer metadata
- Image preprocessing: noise reduction (Gaussian blur, bilateral filtering)
- Deskew correction using Hough transform line detection
- Automatic region detection for common document elements
- Tesseract OCR integration for text extraction
- Coordinate mapping between visual annotations and extracted text
- Concurrent processing while user interacts with document

### Template Management

- Save user-created label configurations as reusable templates
- Template versioning with change history
- Feature matching algorithms (ORB, SIFT) for intelligent template application
- Automatic bounding box adjustment for minor layout variations
- Template sharing across channel members

### Data Export Layer

- JSON export with normalized structure for AI/ML consumption
- Database-ready format generation (CSV, SQL inserts)
- Field validation workflow before final submission
- Batch processing for multiple documents
- Export history and audit trail

## Impact

- Affected specs:
  - `document-annotation` (new capability)
  - `opencv-processing` (new capability)
  - `template-management` (new capability)
  - `data-export` (new capability)
- Affected code:
  - `data-processor/` (new Django REST framework microservice)
  - `data-processor/Dockerfile` (new)
  - `data-processor/requirements.txt` (django, djangorestframework, opencv-python, pytesseract, numpy, scikit-image, pdf2image, pdfplumber)
  - `data-processor/api/views.py` (new)
  - `data-processor/services/ocr_pipeline.py` (new)
  - `data-processor/services/pdf_extractor.py` (new)
  - `data-processor/services/template_matcher.py` (new)
  - `data-processor/models/document.py` (new)
  - `data-processor/models/template.py` (new)
  - `docker-compose.yml` (add data-processor service)
  - `frontend/src/components/DataProcessorChannel.tsx` (new)
  - `frontend/src/components/DocumentAnnotationModal.tsx` (new)
  - `frontend/src/components/AnnotationToolbar.tsx` (new)
  - `frontend/src/hooks/useDocumentProcessor.ts` (new)
