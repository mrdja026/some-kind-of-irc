# Data-Processor Extensions for Deep Claims Image Analysis

## Current State

### data-processor IS NOT PDF-only — it fully supports JPEG/PNG

Verified through tests and code audit:

| Capability | Image Support | Evidence |
|------------|:------------:|---------|
| Upload JPEG/PNG | ✅ | `api/views.py:169` — `file_type = "image"` branch |
| OCR text extraction | ✅ | `ocr_pipeline.py:554` — `process_document(image_data: bytes)` |
| Preprocessing (denoise, deskew, binarize) | ✅ | `preprocessor.py:380` — all ops on numpy arrays |
| Region detection (contours) | ✅ | `ocr_pipeline.py:393` — `detect_document_regions()` |
| Table detection | ✅ | `ocr_pipeline.py:467` — morphological line detection |
| Bounding box annotations | ✅ | `api/views.py:323` — create/update/extract-text |
| Template matching (ORB+RANSAC) | ✅ | `template_matcher.py:502` — works on cv2 arrays |
| Test coverage | ✅ | 4 test files: preprocessor, integration, e2e, template_matcher — all test images |
| Frontend integration | ✅ | 9 components, API client, hooks, WebSocket OCR progress — **already built** |
| Caddy routing | ✅ | `/data-processor/*` → `data-processor:8003` |
| Docker deployment | ✅ | Port 8003, Tesseract + OpenCV installed in Dockerfile |

### The Gap: Document Processing ≠ Damage Photo Analysis

The data-processor is designed for **structured documents** (invoices, forms, receipts). Running it on a fire damage photo produces:

- **OCR**: garbage text or empty — no readable text in burn marks
- **Region detection**: random contours classified as "text"/"header"/"table"/"signature" — meaningless categories for damage
- **Template matching**: useless — damage photos have no standard document layout

The annotation system and bounding box storage **ARE suitable infrastructure** for storing damage analysis results. The gap is what produces those results.

---

## Step 0: Human Annotation First (Before Any AI)

Before any vision model or CV pipeline, the user manually annotates claim images. They open a photo, draw a bounding box around damage, label it (fire_damage, water_damage, etc.), and it's saved as `human_verified` with `confidence: 1.0`. This is 100% accurate ground truth.

### Why This Is the Right First Step

- **Zero external dependencies** — no API keys, no vision model costs
- **Produces training data** — human labels become ground truth to validate any future AI
- **90% of the UI already exists** — `BoundingBoxCanvas.tsx`, `AnnotationToolbar.tsx`, `DocumentAnnotationModal.tsx`, `useAnnotations.ts`, `useDataProcessorMutations.ts` are all built
- **ADK agent can read it immediately** — a new tool queries data-processor for `human_verified` annotations and gets structured damage data

### Existing Components We Reuse (already built)

| Component | What It Does | File |
|-----------|-------------|------|
| `BoundingBoxCanvas.tsx` | Fabric.js canvas — user draws boxes on image, click+drag, resize, select | `frontend/src/components/` |
| `AnnotationToolbar.tsx` | Label type selector (header/table/signature/date/amount), color picker, draw/select toggle | `frontend/src/components/` |
| `DocumentAnnotationModal.tsx` | Orchestrates canvas + toolbar + save/export | `frontend/src/components/` |
| `useAnnotations.ts` | CRUD state management, bulk update, confidence tracking | `frontend/src/hooks/` |
| `useDataProcessorMutations.ts` | React Query mutations for create/update/delete annotations | `frontend/src/hooks/` |
| `dataProcessor.ts` | API client: `createAnnotation(docId, data)`, `updateAnnotation()`, etc. | `frontend/src/api/` |
| `ExportPanel.tsx` | Export annotations as JSON/CSV/SQL | `frontend/src/components/` |

### What Needs to Change

**Backend (data-processor):**
- Add `LabelType` choices: `fire_damage`, `water_damage`, `smoke_damage`, `structural_damage`, `glass_damage`, `debris`
- Add `AnnotationRecord.validation_status` choices: `human_verified`, `ai_suggested`, `pending`, `rejected`
- Add `AnnotationRecord.damage_category` (CharField, nullable) — free-text damage descriptor
- New endpoint: `POST /api/documents/from-minio/` — create document from MinIO key (so we don't re-upload images already in MinIO)
- Django migration for new fields

**Frontend:**
- Extend `LabelType` union with damage types
- Add damage label buttons to `AnnotationToolbar.tsx` (6 new buttons with icons: Flame, Droplets, Wind, etc.)
- Extend `CreateAnnotationRequest` with `validation_status` field
- When user draws a box in claims context → auto-set `validation_status: 'human_verified'`, `confidence: 1.0`
- Wire `DocumentAnnotationModal` into deep claim review flow (click image → opens annotation mode)

**ADK agent:**
- New `FunctionTool`: `damage_annotations(claim_id)` → queries data-processor for all `human_verified` annotations → returns structured damage summary
- Claims agent prompt updated: "When damage annotations are available, reference them in your assessment"

### User Flow

```
1. User clicks "Deep Claim Review" in #ai channel
2. Claim loads with images (thumbnails)
3. User clicks an image → ClaimImagePopup opens (existing lightbox)
4. User clicks "Annotate" button in popup
5. DocumentAnnotationModal opens with image on Fabric.js canvas
6. User selects damage type (e.g., "Fire Damage" 🔥)
7. User draws bounding box around damage area
8. Annotation auto-saved as:
   {
     label_type: "fire_damage",
     label_name: "Fire Damage - Kitchen Area",
     bounding_box: { x: 120, y: 80, width: 340, height: 210 },
     validation_status: "human_verified",
     confidence: 1.0,
     color: "#EF5350"
   }
9. User can draw multiple boxes, different damage types
10. Close modal → annotations visible as colored overlays on thumbnail
11. ADK agent's damage_annotations tool now returns this data
```

### Estimated Effort: ~1 day

| Task | Time |
|------|------|
| Backend: new fields + migration + from-minio endpoint | 2-3 hours |
| Frontend: extend types + toolbar labels + wire modal | 2-3 hours |
| ADK: new damage_annotations FunctionTool | 1-2 hours |
| Testing + deploy | 1 hour |

---

## Three Options (After Step 0)

### Option A: Vision Model via ADK Tool (Recommended for MVP)

A new ADK `FunctionTool` calls a multimodal LLM (Claude/Gemini/GPT-4V) with the image URL. The model returns structured JSON describing damage type, severity, affected areas. Results stored as annotations in data-processor DB.

```
claim image (MinIO) → ADK tool → vision API → structured JSON → data-processor annotation DB
```

**Changes needed:**
- `ai-service-adk/claims_agent.py`: new `image_evidence_analysis` FunctionTool
- `data-processor/api/views.py`: new `POST /api/documents/from-minio/` endpoint (create doc from MinIO key without re-upload)
- `data-processor/api/models.py`: add `severity` field, new `LabelType` choices (fire_damage, water_damage, etc.)
- `data-processor/api/migrations/`: new migration for schema changes
- Frontend: damage annotation overlay on images (bounding boxes with damage labels)

| Pro | Con |
|-----|-----|
| 90%+ accuracy | $0.01-0.05 per image |
| Ships in 2-3 days | Requires external API key |
| Understands context | 2-5s latency per image |
| Low maintenance | Not offline-capable |

### Option B: Custom CV Damage Detection Pipeline

Extend `data-processor/services/` with a new `damage_detector.py`:
- Color histogram analysis (burn marks → brown/black clusters)
- Texture analysis (smoke → haze patterns)
- Edge detection (glass → sharp fragment patterns)
- Contour analysis (water damage → irregular stain boundaries)

```
claim image (MinIO) → data-processor upload → damage_detector.py → annotations with damage labels
```

**Changes needed:**
- `data-processor/services/damage_detector.py`: new service (~500-800 lines)
- `data-processor/api/views.py`: new `POST /api/documents/{id}/analyze-damage/` endpoint
- Same DB migration as Option A
- Same frontend changes as Option A
- Extensive CV tuning and test image collection

| Pro | Con |
|-----|-----|
| Free (no API costs) | 40-60% accuracy |
| Fast inference (<500ms) | 2-3 weeks to build |
| Fully offline | Brittle to image variation |
| Uses existing OpenCV | High maintenance (tuning) |

### Option C: Hybrid (Best Long-Term)

- **Document images** (receipts, invoices, reports) → existing data-processor OCR + annotations
- **Damage photos** (fire, water, smoke) → Vision model for classification + severity → store in data-processor annotation DB

Both paths feed into ADK tools, which provide structured data to the claims agent.

| Pro | Con |
|-----|-----|
| Best of both worlds | Two code paths to maintain |
| 90%+ for photos, 95%+ for docs | More complex routing logic |
| Leverages existing infra | Slightly longer to ship (1 week) |

---

## Full Change Inventory (Any Option)

### 1. data-processor service
- [ ] `POST /api/documents/from-minio/` — create document record from MinIO object key (skip file upload)
- [ ] New `LabelType` values: `fire_damage`, `water_damage`, `smoke_damage`, `structural_damage`, `debris`
- [ ] New `AnnotationRecord` fields: `severity` (FloatField, 0-1), `damage_category` (CharField)
- [ ] Django migration for new fields + label types
- [ ] Damage analysis endpoint (vision model call or CV pipeline depending on option)

### 2. ai-service-adk
- [ ] New `FunctionTool`: `image_evidence_analysis(claim_id: str)` → calls data-processor → returns structured damage assessment
- [ ] Update claims agent system prompt to reference image evidence when available
- [ ] Optionally update `documents_summary` tool to include damage annotation summaries

### 3. backend
- [ ] Proxy endpoint for data-processor's new from-minio and analyze-damage endpoints
- [ ] Or: direct ADK → data-processor communication (skip backend proxy)

### 4. frontend
- [ ] Auto-upload deep claim images to data-processor on deep review load
- [ ] Damage annotation overlay on claim images (reuse `BoundingBoxCanvas.tsx`)
- [ ] Damage summary panel in deep claim review
- [ ] Connect existing `DataProcessorChannel` components to claims flow

### 5. database
- [ ] Migration: `ALTER TABLE api_annotationrecord ADD COLUMN severity FLOAT NULL`
- [ ] Migration: `ALTER TABLE api_annotationrecord ADD COLUMN damage_category VARCHAR(32) NULL`
- [ ] Update `LabelType` choices in model

### 6. infrastructure
- [ ] Vision model API key in docker-compose environment (Option A/C)
- [ ] No new system deps needed (OpenCV + Tesseract already installed)

---

## Open Questions

1. **Which vision model?** Claude (existing Anthropic key), Gemini (free tier via ADK), or GPT-4V?
2. **Pre-compute at seed time or on-demand?** Pre-compute is faster UX but stale; on-demand is always fresh but slower.
3. **UI priority:** Do we need visual damage overlays (bounding boxes on photos) for MVP, or is structured text in the agent chat sufficient?
4. **Scope:** Only synthetic images for now, or also user-uploaded claim photos?

---

## Recommendation

**Step 0 first** (human annotation) — ship in ~1 day using existing UI components. This gives:
- Immediate value: users can annotate damage photos
- Ground truth data for validating any future AI
- ADK agent can reference `human_verified` damage annotations immediately

**Then Option A** (vision model) — use human labels as validation baseline. The model suggests annotations with `validation_status: 'ai_suggested'`, user confirms or rejects → evolves to human-in-the-loop.

**Then Option C** (hybrid) — optimize costs by routing simple documents through OCR, complex photos through vision model.

---

###Codex fidings

#### Constructive criticism
- Changing `validation_status` to `human_verified/ai_suggested` will break existing export logic/tests that expect `valid/invalid/pending`; consider adding a new field or mapping to existing values (`data-processor/api/models.py`, `data-processor/api/serializers.py`, `data-processor/api/views.py`, `data-processor/tests/test_e2e_annotation_workflow.py`).
- New damage label types must be added across the shared enum + serializers + frontend type union, or they will be coerced to `custom` (`data-processor/storage/in_memory.py`, `data-processor/api/serializers.py`, `frontend/src/types/index.ts`).
- The annotation UI currently disables label buttons in draw mode and forces `custom` on draw, which blocks a damage-type workflow until fixed (`frontend/src/components/DocumentAnnotationModal.tsx`, `frontend/src/components/AnnotationToolbar.tsx`).
- Claims image annotation is not wired to the existing modal: `DocumentAnnotationModal` is only reachable via data-processor routes and is gated to `is_data_processor` channels (`frontend/src/routes/data-processing.$channelId.$documentId.tsx`, `frontend/src/components/AIChannel.tsx`).
- Frontend request types do not support `validation_status`/`confidence` on create yet (`frontend/src/api/dataProcessor.ts`, `frontend/src/types/index.ts`).

#### Potential blockers
- data-processor endpoints are admin-gated via JWT cookies; ADK/backend calls without a user session will 404 unless a service auth path is added (`data-processor/middleware/jwt_auth.py`).
- Claims images live in a different MinIO bucket than data-processor; a `/from-minio` endpoint must decide how to access `MINIO_CLAIMS_BUCKET` and whether to copy or proxy image data (`media-storage/app.py`, `data-processor/config/settings.py`).
- ADK claims stack has no tool plumbing for external services; adding `damage_annotations` needs client/auth wiring, not just a function stub (`ai-service-adk/main.py`, `ai-service-adk/claims_agent.py`).
- Canvas/CORS risks if `image_url` points at public MinIO instead of `/media/...` (Fabric will taint without CORS headers), which can break annotation UI (`frontend/src/components/BoundingBoxCanvas.tsx`, `data-processor/api/serializers.py`).
