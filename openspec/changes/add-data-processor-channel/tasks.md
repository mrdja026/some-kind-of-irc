# Tasks: #data-processor Channel Implementation

## 1. Django Microservice Setup ✅ COMPLETE

- [x] 1.1 Create `data-processor/` directory with Django project structure
- [x] 1.2 Create `data-processor/requirements.txt` with Django, DRF, OpenCV, pytesseract, numpy, scikit-image
- [x] 1.3 Create `data-processor/Dockerfile` with Python 3.11, Tesseract OCR, and OpenCV dependencies
- [x] 1.4 Create `data-processor/config/settings.py` with DRF configuration
- [x] 1.5 Create `data-processor/config/urls.py` with API routing
- [x] 1.6 Add `data-processor` service to `docker-compose.yml` (following existing service patterns)
- [x] 1.7 Configure inter-service networking and CORS
- [x] 1.8 Add `DATA_PROCESSOR_URL` environment variable to deploy-local.sh

## 2. In-Memory Storage Layer ✅ COMPLETE

- [x] 2.1 Create `data-processor/storage/in_memory.py` with Document, Annotation, Template dataclasses
- [x] 2.2 Implement DocumentStore singleton for in-memory data management
- [x] 2.3 Add helper methods for CRUD operations on documents and templates
- [x] 2.4 Implement data serialization for API responses

## 3. OCR Pipeline Service ✅ COMPLETE

- [x] 3.1 Create `data-processor/services/preprocessor.py` with noise reduction functions
- [x] 3.2 Implement Gaussian blur and bilateral filtering for image denoising
- [x] 3.3 Implement adaptive thresholding with Otsu's method fallback
- [x] 3.4 Implement deskew correction using Hough transform line detection
- [x] 3.5 Create `data-processor/services/ocr_pipeline.py` with Tesseract integration
- [x] 3.6 Implement automatic region detection for common document elements
- [x] 3.7 Create coordinate mapping utility for annotation-to-text alignment
- [x] 3.8 Add image resizing to enforce 1024x1024 max dimensions

## 4. Template Matching Service ✅ COMPLETE

- [x] 4.1 Create `data-processor/services/template_matcher.py` with ORB feature extraction
- [x] 4.2 Implement BFMatcher with Hamming distance for descriptor matching
- [x] 4.3 Implement RANSAC homography estimation for transformation
- [x] 4.4 Create bounding box transformation utility
- [x] 4.5 Add confidence scoring and validation for template matches
- [x] 4.6 Implement fallback strategy for low-confidence matches

## 5. Django REST API Endpoints ✅ COMPLETE

- [x] 5.1 Create `data-processor/api/serializers.py` for Document, Annotation, Template
- [x] 5.2 Create `data-processor/api/views.py` with DocumentViewSet
- [x] 5.3 Add `POST /api/documents/` endpoint for document upload and processing
- [x] 5.4 Add `GET /api/documents/{id}/` endpoint for document status and OCR results
- [x] 5.5 Add `POST /api/documents/{id}/annotations/` endpoint for creating annotations
- [x] 5.6 Add `PUT /api/documents/{id}/annotations/{annotation_id}/` endpoint for updating annotations
- [x] 5.7 Add `POST /api/templates/` endpoint for creating templates
- [x] 5.8 Add `GET /api/templates/` endpoint for listing channel templates
- [x] 5.9 Add `POST /api/documents/{id}/apply-template/` endpoint for template application
- [x] 5.10 Add `POST /api/documents/{id}/export/` endpoint for data export (JSON, CSV, SQL)
- [x] 5.11 Add `POST /api/batch/` endpoint for batch job creation
- [x] 5.12 Add `GET /api/batch/{id}/` endpoint for batch job status

## 6. FastAPI Backend Integration ✅ COMPLETE

- [x] 6.1 Add `is_data_processor` boolean field to channel model
- [x] 6.2 Add `is_data_processor` field to ChannelCreate and ChannelResponse Pydantic models
- [x] 6.3 Create proxy endpoints in `backend/src/api/endpoints/data_processor.py`
- [x] 6.4 Implement feature flag `FEATURE_DATA_PROCESSOR` in `backend/src/core/config.py`
- [x] 6.5 Add `DATA_PROCESSOR_URL` environment variable to config
- [x] 6.6 Add database migration for `is_data_processor` column
- [x] 6.7 Register `data_processor_router` in `main.py`

## 7. WebSocket Events (FastAPI Backend) ✅ COMPLETE

- [x] 7.1 Add `document_uploaded` event type to WebSocket manager
- [x] 7.2 Add `ocr_progress` event for real-time processing updates
- [x] 7.3 Add `ocr_complete` event with detected regions and text
- [x] 7.4 Add `template_applied` event for template matching results
- [x] 7.5 Add webhook endpoint for data-processor to notify progress

## 8. Frontend Components ✅ COMPLETE

- [x] 8.1 Create `frontend/src/components/DataProcessorChannel.tsx` main channel component
- [x] 8.2 Create `frontend/src/components/DocumentAnnotationModal.tsx` annotation workspace UI
- [x] 8.3 Create `frontend/src/components/AnnotationToolbar.tsx` with label type buttons
- [x] 8.4 Create `frontend/src/components/BoundingBoxCanvas.tsx` using Fabric.js
- [x] 8.5 Implement pan/zoom controls for document viewing
- [x] 8.6 Implement color-coded bounding box drawing and manipulation
- [x] 8.7 Create label panel with type selection (header, table, signature, date, amount, custom)
- [x] 8.8 Add automatic redirect to annotation route on image/PDF upload in data processor channels
- [x] 8.9 Update Channel type to include `is_data_processor` flag
- [x] 8.10 Create `frontend/src/api/dataProcessor.ts` API client
- [x] 8.11 Integrate DataProcessorChannel into `chat.tsx` and add `/data-processing/$channelId/$documentId` route

## 9. Template Management UI ✅ COMPLETE

- [x] 9.1 Create `frontend/src/components/TemplateManager.tsx` for template list/selection
- [x] 9.2 Create `frontend/src/components/TemplateSaveModal.tsx` for saving configurations
- [x] 9.3 Implement template preview thumbnails (in TemplateManager as TemplateCard)
- [x] 9.4 Implement one-click template application with visual feedback
- [x] 9.5 Add `updateTemplate` API function to `dataProcessor.ts`
- [x] 9.6 Integrate TemplateManager with DataProcessorChannel

## 10. Data Export UI ✅ COMPLETE

- [x] 10.1 Create `frontend/src/components/ExportPanel.tsx` with format selection
- [x] 10.2 Create `frontend/src/components/ValidationWorkflow.tsx` for field review
- [x] 10.3 Implement JSON preview with field highlighting
- [x] 10.4 Add batch processing status dashboard

## 11. Hooks & State Management ✅ COMPLETE

- [x] 11.1 Create `frontend/src/hooks/useDocumentProcessor.ts` for document state
- [x] 11.2 Create `frontend/src/hooks/useAnnotations.ts` for annotation state
- [x] 11.3 Create `frontend/src/hooks/useTemplates.ts` for template operations
- [x] 11.4 Create `frontend/src/hooks/useOcrProgress.ts` for WebSocket progress events
- [x] 11.5 Add TanStack Query mutations for data-processor API calls
- [x] 11.6 Create `frontend/src/api/dataProcessor.ts` API client

## 12. Channel Type Integration ✅ COMPLETE

- [x] 12.1 Update channel creation form with data-processor checkbox
- [x] 12.2 Update channel sidebar to show data processor icon for data-processor channels
- [x] 12.3 Route data-processor channels to DataProcessorChannel component

## 13. Testing ✅ COMPLETE

- [x] 13.1 Write unit tests for OCR preprocessing functions (Django)
- [x] 13.2 Write unit tests for template matching algorithm (Django)
- [x] 13.3 Write integration tests for document upload flow
- [x] 13.4 Write integration tests for export formats
- [x] 13.5 Write end-to-end tests for annotation workflows

## 14. Deployment Integration ✅ COMPLETE

- [x] 14.1 Update `docker-compose.yml` with data-processor service configuration
- [x] 14.2 Add data-processor route to `Caddyfile` for reverse proxy
- [x] 14.3 Update `deploy-local.sh` with data-processor health check
- [x] 14.4 Add data-processor to deployment summary output
- [x] 14.5 Configure shared MinIO access for data-processor service
- [x] 14.6 Add `DATA_PROCESSOR_URL` environment variable (default: http://data-processor:8003)
- [x] 14.7 Update caddy depends_on to include data-processor

## 15. Documentation ✅ COMPLETE

- [x] 15.1 Create `data-processor/README.md` with setup and API documentation
- [x] 15.2 Update main project README with data-processor service info
- [x] 15.3 Add user guide for annotation tools
- [x] 15.4 Document template creation best practices

## 16. PDF Parsing Support

- [x] 16.1 Add PDF dependencies (pdf2image, pdfplumber, poppler) to data-processor build
- [x] 16.2 Create PDF extraction service for first-page rasterization and text-layer capture
- [x] 16.3 Extend document storage model with file type, page count, and pdf text layer
- [x] 16.4 Update document upload endpoint to accept PDFs and store page 1 metadata
- [x] 16.5 Update annotation workspace to render PDF page 1 with page-count indicator
- [x] 16.6 Include pdf text layer + page count in export payloads
- [x] 16.7 Add tests for PDF ingestion and text-layer extraction

## Notes

- **Known Issue (Local Setup)**: The #data-processor channel does not appear because the feature flag defaults to disabled; set `FEATURE_DATA_PROCESSOR=true` to create it on startup.
