# Design: #data-processor Channel Architecture

## Context

The data-processor channel introduces document annotation and OCR extraction capabilities to the IRC application. This feature targets users who need to digitize paper documents, extract structured data from images, and prepare datasets for AI/ML pipelines. The design implements a **separate Django REST framework microservice** that handles all document processing operations, communicating with the main FastAPI backend via REST API calls and shared MinIO storage.

### Stakeholders

- End users uploading and annotating documents
- Teams sharing annotation templates
- Downstream systems consuming extracted data (AI/ML pipelines)
- DevOps managing compute resources for OCR processing

### Constraints

- Separate microservice architecture using Django REST framework
- Must communicate with main FastAPI backend for channel/user context
- In-memory storage for MVP (no persistent database in data-processor service)
- Frontend must remain responsive during backend OCR processing
- OpenCV and Tesseract must run in Docker container environment
- Template matching must handle minor document variations without manual adjustment
- Maximum image dimensions: 1024x1024 pixels
- PDF parsing limited to first page in MVP

## Goals / Non-Goals

### Goals

- Provide interactive document annotation with real-time visual feedback
- Execute OCR extraction concurrently without blocking UI interactions
- Enable template reuse with intelligent layout matching
- Export structured data in formats compatible with common ML frameworks
- Support batch processing for high-volume workflows

### Non-Goals

- Full multi-page PDF processing (MVP parses first page only)
- Training custom OCR models (use pre-trained Tesseract)
- Real-time collaborative annotation editing (single user per document session)
- Mobile-optimized annotation interface (desktop-first)

## Decisions

### D1: Frontend Annotation Architecture

**Decision**: Implement annotation layer using HTML5 Canvas with React state management.

**Rationale**: Canvas provides precise pixel-level control for bounding boxes while maintaining performance with large images. Fabric.js library adds object manipulation (resize, move, rotate) without custom implementation.

**Alternatives Considered**:

- SVG overlay: Cleaner DOM integration but performance degrades with many annotation objects
- WebGL: Overkill for 2D rectangles; adds complexity without benefit
- Pure DOM divs: Limited rotation/transformation capabilities

### D2: Microservice Architecture (Django REST Framework)

**Decision**: Implement data-processor as a standalone Django REST framework microservice with its own Docker container, communicating with the main FastAPI backend via HTTP REST calls.

**Rationale**: Separating document processing into its own service provides:

- Independent scaling for compute-intensive OCR operations
- Technology choice flexibility (Django's mature ORM and admin for future data management)
- Isolation of heavy dependencies (OpenCV, Tesseract) from main backend
- Simpler deployment and rollback strategies

**Architecture**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Frontend (React)                            │
│                                                                          │
│  ┌──────────────────┐    ┌───────────────────┐    ┌──────────────────┐  │
│  │ DataProcessor    │    │ Annotation Modal  │    │ Template Manager │  │
│  │ Channel.tsx      │    │                   │    │                  │  │
│  └────────┬─────────┘    └─────────┬─────────┘    └────────┬─────────┘  │
└───────────┼─────────────────────────┼──────────────────────┼────────────┘
            │                         │                      │
            ▼                         ▼                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                        API Gateway (Caddy/Nginx)                          │
└───────────┬─────────────────────────┬──────────────────────┬──────────────┘
            │                         │                      │
            ▼                         ▼                      ▼
┌───────────────────────┐   ┌──────────────────────────────────────────────┐
│  FastAPI Backend      │   │     Data-Processor Service (Django DRF)      │
│  ────────────────────│   │  ─────────────────────────────────────────── │
│  - Channel mgmt      │◀──│  - Document upload/process (POST /process/)   │
│  - User auth         │   │  - OCR pipeline (OpenCV + Tesseract)          │
│  - WebSocket proxy   │──▶│  - Template matching (ORB features)           │
│  - Message history   │   │  - Annotation management (in-memory)          │
└───────────┬───────────┘   │  - Export generation (JSON/CSV/SQL)          │
            │               └──────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
┌──────────────────────┐        ┌──────────────────────┐
│  SQLite (main DB)    │        │  MinIO (shared)      │
│  - channels          │        │  - uploaded images   │
│  - users             │        │  - processed images  │
│  - messages          │        │  - exports           │
└──────────────────────┘        └──────────────────────┘
```

**Service Structure**:

```
data-processor/
├── Dockerfile
├── requirements.txt
├── manage.py
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── api/
│   ├── __init__.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── services/
│   ├── __init__.py
│   ├── ocr_pipeline.py
│   ├── template_matcher.py
│   └── preprocessor.py
└── storage/
    ├── __init__.py
    └── in_memory.py
```

**Alternatives Considered**:

- Embedded in FastAPI: Tight coupling; hard to scale OCR independently
- Celery + Redis: Overkill for MVP; adds operational complexity
- Serverless functions: Cold start latency unacceptable for interactive use

### D3: PDF Ingestion and Text Layer Extraction

**Decision**: Use PDF text-layer extraction plus first-page rasterization before OCR.

**Rationale**: PDF files can contain selectable text that is more accurate than OCR. Extracting the text layer first improves quality, while rasterizing only the first page keeps MVP scope manageable and leaves room to extend to multi-page parsing later.

**Pipeline Stages**:

1. Read PDF metadata and total page count
2. Extract the text layer for page 1 (if present) and store it in the document metadata
3. Rasterize page 1 to an image within the 1024x1024 limit
4. Continue through the existing image preprocessing pipeline and OCR

### D4: Image Preprocessing Pipeline

**Decision**: Implement three-stage preprocessing with configurable parameters.

**Pipeline Stages**:

1. **Noise Reduction**: Gaussian blur (sigma=1.0) followed by bilateral filtering (d=9, sigmaColor=75, sigmaSpace=75)
2. **Binarization**: Adaptive thresholding (blockSize=11, C=2) with Otsu's method fallback
3. **Deskew**: Hough line detection to estimate rotation angle, affine transformation to correct

**Configuration Schema**:

```python
class PreprocessingConfig(BaseModel):
    noise_reduction: bool = True
    gaussian_sigma: float = 1.0
    bilateral_d: int = 9
    deskew_enabled: bool = True
    deskew_max_angle: float = 15.0  # degrees
```

### D5: Template Matching Algorithm

**Decision**: Use ORB (Oriented FAST and Rotated BRIEF) feature matching with RANSAC homography estimation.

**Rationale**: ORB is patent-free, fast, and rotation-invariant. RANSAC filters outliers for robust homography estimation even with partial document matches.

**Matching Process**:

1. Extract ORB keypoints from template and target images
2. Match descriptors using BFMatcher with Hamming distance
3. Apply ratio test (Lowe's ratio = 0.75) to filter ambiguous matches
4. Compute homography matrix using RANSAC
5. Transform template bounding boxes to target coordinates
6. Validate transformed boxes (area ratio, aspect ratio checks)

**PDF Page Scope**: Template application targets page 1 in MVP; when multi-page support is enabled, the same template applies to all pages by default.

**Fallback Strategy**: If feature matching confidence < 60%, prompt user for manual anchor point selection.

### D6: Data Model Design (In-Memory for MVP)

**Decision**: Use in-memory data structures for MVP with clear interfaces for future database migration.

**Rationale**: In-memory storage simplifies MVP deployment, eliminates database setup in the data-processor service, and provides fast access. Data structures mirror future database schema for easy migration.

**In-Memory Data Classes**:

```python
# data-processor/storage/in_memory.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import uuid

class OcrStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class LabelType(Enum):
    HEADER = "header"
    TABLE = "table"
    SIGNATURE = "signature"
    DATE = "date"
    AMOUNT = "amount"
    CUSTOM = "custom"

@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0

@dataclass
class Annotation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    label_type: LabelType = LabelType.CUSTOM
    label_name: str = ""
    color: str = "#FF0000"
    bounding_box: BoundingBox = None
    extracted_text: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Document:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str = ""
    uploaded_by: str = ""
    original_filename: str = ""
    file_type: str = "image"  # image or pdf
    page_count: int = 1
    pdf_text_layer: Optional[Dict] = None  # text layer for page 1 when available
    image_data: bytes = b""  # In-memory image storage (page 1 raster)
    preprocessed_data: Optional[bytes] = None
    ocr_status: OcrStatus = OcrStatus.PENDING
    ocr_result: Optional[Dict] = None
    annotations: List[Annotation] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class TemplateLabel:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label_type: LabelType = LabelType.CUSTOM
    label_name: str = ""
    color: str = "#FF0000"
    relative_x: float = 0.0  # 0.0-1.0 relative to image width
    relative_y: float = 0.0
    relative_width: float = 0.1
    relative_height: float = 0.1
    expected_format: Optional[str] = None  # regex pattern
    is_required: bool = False

@dataclass
class Template:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str = ""
    created_by: str = ""
    name: str = ""
    description: str = ""
    thumbnail_data: Optional[bytes] = None
    version: int = 1
    is_active: bool = True
    labels: List[TemplateLabel] = field(default_factory=list)
    feature_keypoints: Optional[bytes] = None  # Serialized ORB keypoints
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class BatchJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str = ""
    template_id: Optional[str] = None
    created_by: str = ""
    status: str = "pending"
    document_ids: List[str] = field(default_factory=list)
    processed_count: int = 0
    failed_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

# In-memory storage singleton
class DocumentStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.documents: Dict[str, Document] = {}
            cls._instance.templates: Dict[str, Template] = {}
            cls._instance.batch_jobs: Dict[str, BatchJob] = {}
        return cls._instance

    def clear(self):
        """Clear all data (useful for testing)"""
        self.documents.clear()
        self.templates.clear()
        self.batch_jobs.clear()
```

**Future Migration Path**: When moving to persistent storage, replace `DocumentStore` with Django models while keeping the same dataclass interfaces for serializers.

### D7: Export Format Specifications

**Decision**: Support three export formats with consistent field mapping.

**JSON Schema**:

```json
{
  "document_id": "uuid",
  "source_filename": "invoice_001.png",
  "processed_at": "2026-01-26T12:00:00Z",
  "template_id": "uuid or null",
  "page_count": 1,
  "fields": [
    {
      "name": "invoice_number",
      "type": "header",
      "value": "INV-2026-001",
      "confidence": 0.95,
      "bounding_box": { "x": 100, "y": 50, "width": 200, "height": 30 },
      "validation_status": "valid"
    }
  ],
  "raw_ocr_text": "Full document text...",
  "pdf_text_layer": [
    { "text": "Invoice 001", "page": 1 }
  ],
  "metadata": {
    "preprocessing_applied": ["noise_reduction", "deskew"],
    "deskew_angle": 2.3,
    "ocr_engine": "tesseract-5.3.0"
  }
}
```

**CSV Format**: Flattened fields with document reference columns.

**SQL Insert Format**: Parameterized INSERT statements for common databases.

### D8: WebSocket Event Protocol

**Decision**: Extend existing WebSocket protocol with document processing events.

**Event Types**:

```typescript
// Server -> Client events
interface DocumentUploadedEvent {
  type: "document_uploaded";
  document_id: string;
  channel_id: string;
  uploaded_by: string;
  filename: string;
  thumbnail_url: string;
}

interface OcrProgressEvent {
  type: "ocr_progress";
  document_id: string;
  stage: "preprocessing" | "detection" | "extraction" | "mapping";
  progress: number; // 0-100
  message: string;
}

interface OcrCompleteEvent {
  type: "ocr_complete";
  document_id: string;
  detected_regions: DetectedRegion[];
  extracted_text: string;
}

interface TemplateAppliedEvent {
  type: "template_applied";
  document_id: string;
  template_id: string;
  matched_regions: MatchedRegion[];
  confidence: number;
}

// Client -> Server events
interface AnnotationUpdatedEvent {
  type: "annotation_updated";
  document_id: string;
  annotation: Annotation;
}

interface ExportRequestedEvent {
  type: "export_requested";
  document_id: string;
  format: "json" | "csv" | "sql";
}
```

## Risks / Trade-offs

### R1: OCR Accuracy Variability

- **Risk**: Low-quality scans or unusual fonts may yield poor extraction accuracy
- **Mitigation**: Display confidence scores prominently; require human validation for low-confidence fields; provide manual text editing
- **Trade-off**: Accuracy vs. throughput - more validation steps slow batch processing

### R2: Template Matching Failures

- **Risk**: Documents with significant layout variations may not match templates
- **Mitigation**: Fallback to manual anchor points; store multiple template variants; use relative positioning instead of absolute coordinates
- **Trade-off**: Flexibility vs. precision - looser matching may misalign labels

### R3: Processing Time for Large Images

- **Risk**: High-resolution scans may take >10 seconds to process
- **Mitigation**: Progressive loading; background processing with status updates; offer resolution reduction option
- **Trade-off**: Quality vs. speed - downsampling improves speed but may reduce OCR accuracy

### R4: Database Growth with Image Storage

- **Risk**: SQLite may struggle with many large document records
- **Mitigation**: Store images in MinIO (existing media storage); keep only metadata and paths in SQLite; implement retention policies
- **Trade-off**: Simplicity vs. scalability - eventual migration to PostgreSQL may be needed

## Migration Plan

### Phase 1: Data-Processor Service Setup

1. Create `data-processor/` directory with Django project structure
2. Create `data-processor/Dockerfile` with Python, OpenCV, and Tesseract
3. Add `data-processor` service to `docker-compose.yml`
4. Configure inter-service networking
5. Rollback: Remove service from docker-compose

### Phase 2: API Integration

1. Create Django REST framework endpoints for document processing
2. Add proxy routes in FastAPI backend to forward requests
3. Configure CORS for cross-service communication
4. Rollback: Remove proxy routes

### Phase 3: Frontend Deployment

1. Add DataProcessorChannel component
2. Wire annotation route navigation to upload flow (`/data-processing/{channelId}/{documentId}`)
3. Add channel type checkbox in channel creation
4. Rollback: Hide channel type in UI

### Feature Flag

FastAPI backend:

```python
FEATURE_DATA_PROCESSOR_CHANNEL = os.getenv("FEATURE_DATA_PROCESSOR", "false") == "true"
```

Django data-processor service:

```python
# config/settings.py
DATA_PROCESSOR_ENABLED = os.getenv("DATA_PROCESSOR_ENABLED", "true") == "true"
```

### Docker Compose Addition

```yaml
# docker-compose.yml (addition)
data-processor:
  build:
    context: ./data-processor
    dockerfile: Dockerfile
  environment:
    - DEBUG=false
    - ALLOWED_HOSTS=*
    - MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://minio:9000}
    - MINIO_PUBLIC_ENDPOINT=${MINIO_PUBLIC_ENDPOINT:-http://localhost:9000}
    - MINIO_BUCKET=${MINIO_BUCKET:-media}
    - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-minioadmin}
    - MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-minioadmin}
    - BACKEND_URL=${BACKEND_URL:-http://backend:8002}
  depends_on:
    - backend
    - minio
```

### Caddyfile Addition

```caddyfile
# Add to Caddyfile
handle /data-processor/* {
    uri strip_prefix /data-processor
    reverse_proxy data-processor:8003
}
```

### deploy-local.sh Updates

```bash
# Add environment variable
export DATA_PROCESSOR_URL="${DATA_PROCESSOR_URL:-http://data-processor:8003}"

# Add health check after backend health check
echo "Waiting for data-processor to become healthy..."
for i in {1..20}; do
  if "${COMPOSE_CMD[@]}" exec -T data-processor python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health', timeout=1)" >/dev/null 2>&1; then
    echo "Data-processor is up."
    break
  fi
  sleep 2
done

# Update deploy summary
cat <<'EOF'
------------------------------------------------------------
Deploy summary
------------------------------------------------------------
- Frontend/API:        http://localhost/
- Data Processor:      http://localhost/data-processor/
- Media proxy:         http://localhost/media/...
- MinIO console:       http://localhost:9001
- MinIO bucket:        media (public GET)
EOF
```

## Open Questions

1. **Q**: Should templates be shareable across channels or channel-scoped only
   - **Leaning**: Channel-scoped for MVP; add sharing in future iteration - okay, so when adding a channel it should have a checkbox data-processing channel

2. **Q**: Maximum image dimensions supported
   - **Leaning**: 1024x1024 pixels; larger images auto-resized with warning

3. **Q**: Retention policy for processed documents
   - **Leaning**: in memory for mvp

4. **Q**: Should batch jobs support mixed templates?
   - **Leaning**: Single template per batch for MVP; reduces complexity - yes
