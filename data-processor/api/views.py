"""
API views for data-processor service.

Provides views for:
- Health check
- Document upload and processing
- Annotation management
- Template management
- Data export
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from storage.in_memory import (
    store,
    Document,
    Annotation,
    Template,
    TemplateLabel,
    BatchJob,
    OcrStatus,
    LabelType,
    BoundingBox,
)
from .serializers import (
    DocumentSerializer,
    DocumentUploadSerializer,
    AnnotationSerializer,
    TemplateSerializer,
    TemplateApplySerializer,
    BatchJobSerializer,
    ExportRequestSerializer,
)

# Import OCR services (will be available in Docker)
try:
    from services.ocr_pipeline import (
        process_document,
        extract_text_for_annotations,
        OcrConfig,
    )
    from services.preprocessor import load_image_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Import template matching service
try:
    from services.template_matcher import (
        TemplateMatcher,
        TemplateMatchConfig,
        MatchResult,
    )
    TEMPLATE_MATCHING_AVAILABLE = True
except ImportError:
    TEMPLATE_MATCHING_AVAILABLE = False

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health_check(request):
    """
    Health check endpoint.
    
    Returns service status for container orchestration health probes.
    """
    stats = store.get_stats()
    return Response(
        {
            "status": "healthy",
            "service": "data-processor",
            "version": "1.0.0",
            "storage": stats,
        },
        status=status.HTTP_200_OK,
    )


class DocumentListCreateView(APIView):
    """
    List all documents or create a new document.
    
    GET: List documents for a channel
    POST: Upload and process a new document
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        """List documents, optionally filtered by channel_id."""
        channel_id = request.query_params.get("channel_id")
        documents = store.list_documents(channel_id=channel_id)
        serializer = DocumentSerializer(documents, many=True)
        return Response(
            {"documents": serializer.data, "count": len(documents)},
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        """Upload and process a new document."""
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get image file
        image_file = data.get("image")
        if not image_file:
            return Response(
                {"error": "No image file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Read image data into memory
        image_data = image_file.read()
        
        # Create document
        document = Document(
            channel_id=data["channel_id"],
            uploaded_by=data.get("uploaded_by", ""),
            original_filename=image_file.name,
            image_data=image_data,
            ocr_status=OcrStatus.PENDING,
        )
        
        # Store document
        document = store.create_document(document)
        
        logger.info(f"Document uploaded: {document.id} ({document.original_filename})")
        
        # Return response
        response_serializer = DocumentSerializer(document)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class DocumentDetailView(APIView):
    """
    Retrieve, update, or delete a document.
    
    GET: Get document details with OCR results
    PUT: Update document annotations
    DELETE: Remove document
    """
    
    def get(self, request, document_id):
        """Get document details."""
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DocumentSerializer(document)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, document_id):
        """Update document (e.g., apply template, update status)."""
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update allowed fields
        updates = {}
        allowed_fields = ["template_id", "raw_ocr_text"]
        for field in allowed_fields:
            if field in request.data:
                updates[field] = request.data[field]
        
        if updates:
            document = store.update_document(document_id, updates)
        
        serializer = DocumentSerializer(document)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def delete(self, request, document_id):
        """Delete document."""
        deleted = store.delete_document(document_id)
        if not deleted:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(
            {"message": f"Document {document_id} deleted"},
            status=status.HTTP_200_OK
        )


class AnnotationListCreateView(APIView):
    """
    List or create annotations for a document.
    """
    
    def get(self, request, document_id):
        """List all annotations for a document."""
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AnnotationSerializer(document.annotations, many=True)
        return Response(
            {"annotations": serializer.data, "count": len(document.annotations)},
            status=status.HTTP_200_OK
        )
    
    def post(self, request, document_id):
        """Create a new annotation for a document."""
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AnnotationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        annotation = serializer.save()
        annotation = store.add_annotation(document_id, annotation)
        
        if not annotation:
            return Response(
                {"error": "Failed to add annotation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        response_serializer = AnnotationSerializer(annotation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AnnotationDetailView(APIView):
    """
    Retrieve, update, or delete a specific annotation.
    """
    
    def get(self, request, document_id, annotation_id):
        """Get annotation details."""
        annotation = store.get_annotation(document_id, annotation_id)
        if not annotation:
            return Response(
                {"error": "Annotation not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AnnotationSerializer(annotation)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, document_id, annotation_id):
        """Update an annotation."""
        annotation = store.get_annotation(document_id, annotation_id)
        if not annotation:
            return Response(
                {"error": "Annotation not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AnnotationSerializer(annotation, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Build updates dict
        updates = {}
        for key, value in serializer.validated_data.items():
            if key == "bounding_box" and value:
                updates["bounding_box"] = BoundingBox(**value)
            elif key == "label_type":
                updates["label_type"] = LabelType(value)
            else:
                updates[key] = value
        
        updated = store.update_annotation(document_id, annotation_id, updates)
        if not updated:
            return Response(
                {"error": "Failed to update annotation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        response_serializer = AnnotationSerializer(updated)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    def delete(self, request, document_id, annotation_id):
        """Delete an annotation."""
        deleted = store.delete_annotation(document_id, annotation_id)
        if not deleted:
            return Response(
                {"error": "Annotation not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(
            {"message": f"Annotation {annotation_id} deleted"},
            status=status.HTTP_200_OK
        )


class TemplateListCreateView(APIView):
    """
    List all templates or create a new template.
    
    GET: List templates for a channel
    POST: Create a new template from annotations
    """
    
    def get(self, request):
        """List templates."""
        channel_id = request.query_params.get("channel_id")
        active_only = request.query_params.get("active_only", "true").lower() == "true"
        
        templates = store.list_templates(channel_id=channel_id, active_only=active_only)
        serializer = TemplateSerializer(templates, many=True)
        return Response(
            {"templates": serializer.data, "count": len(templates)},
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        """Create a new template, optionally extracting ORB keypoints from source document."""
        serializer = TemplateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        template = serializer.save()
        
        # Extract ORB keypoints if source document is provided
        source_document_id = template.source_document_id
        keypoints_extracted = False
        
        if source_document_id and TEMPLATE_MATCHING_AVAILABLE and OCR_AVAILABLE:
            source_document = store.get_document(source_document_id)
            if source_document and source_document.image_data:
                try:
                    # Load image and extract keypoints
                    image = load_image_from_bytes(source_document.image_data)
                    matcher = TemplateMatcher()
                    keypoints_data = matcher.prepare_template_keypoints(image)
                    
                    if keypoints_data:
                        template.feature_keypoints = keypoints_data
                        keypoints_extracted = True
                        logger.info(f"Extracted ORB keypoints for template from document {source_document_id}")
                except Exception as e:
                    logger.warning(f"Failed to extract keypoints for template: {e}")
        
        template = store.create_template(template)
        
        logger.info(f"Template created: {template.id} ({template.name})")
        
        response_data = TemplateSerializer(template).data
        response_data["keypoints_extracted"] = keypoints_extracted
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class TemplateDetailView(APIView):
    """
    Retrieve, update, or delete a template.
    
    GET: Get template details with labels
    PUT: Update template
    DELETE: Remove template (soft delete - sets is_active=False)
    """
    
    def get(self, request, template_id):
        """Get template details."""
        template = store.get_template(template_id)
        if not template:
            return Response(
                {"error": "Template not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TemplateSerializer(template)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, template_id):
        """Update template."""
        template = store.get_template(template_id)
        if not template:
            return Response(
                {"error": "Template not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TemplateSerializer(template, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Build updates
        updates = {}
        for key, value in serializer.validated_data.items():
            if key == "labels":
                # Convert label dicts to TemplateLabel objects
                labels = []
                for label_data in value:
                    label_type = label_data.pop("label_type", "custom")
                    labels.append(TemplateLabel(
                        label_type=LabelType(label_type),
                        **label_data
                    ))
                updates["labels"] = labels
            else:
                updates[key] = value
        
        template = store.update_template(template_id, updates)
        
        response_serializer = TemplateSerializer(template)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    def delete(self, request, template_id):
        """Delete template (hard delete for MVP)."""
        deleted = store.delete_template(template_id)
        if not deleted:
            return Response(
                {"error": "Template not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(
            {"message": f"Template {template_id} deleted"},
            status=status.HTTP_200_OK
        )


class TemplateApplyView(APIView):
    """
    Apply a template to a document.
    
    Supports two modes:
    1. Feature-based matching (ORB + RANSAC) when template has stored keypoints
    2. Relative positioning fallback when keypoints unavailable or matching fails
    """
    
    def post(self, request, document_id):
        """Apply template to document using feature matching or relative positioning."""
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TemplateApplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        template_id = serializer.validated_data["template_id"]
        use_feature_matching = serializer.validated_data.get("use_feature_matching", True)
        force_apply = serializer.validated_data.get("force_apply", False)
        confidence_threshold = serializer.validated_data.get("confidence_threshold", 0.6)
        
        template = store.get_template(template_id)
        if not template:
            return Response(
                {"error": "Template not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Determine document dimensions
        doc_width = document.width if document.width else 1024
        doc_height = document.height if document.height else 1024
        
        # Try feature-based matching if available
        match_result = None
        used_feature_matching = False
        
        if (use_feature_matching and
            TEMPLATE_MATCHING_AVAILABLE and
            OCR_AVAILABLE and
            template.feature_keypoints and
            document.image_data):
            
            try:
                # Load document image
                image = load_image_from_bytes(document.image_data)
                
                # Configure matcher with confidence threshold
                config = TemplateMatchConfig(min_confidence=confidence_threshold)
                matcher = TemplateMatcher(config)
                
                # Run template matching
                match_result = matcher.match(
                    template,
                    image,
                    document_dimensions=(doc_width, doc_height)
                )
                
                logger.info(
                    f"Template matching: confidence={match_result.confidence:.2f}, "
                    f"matches={match_result.total_matches}, inliers={match_result.inlier_count}"
                )
                
                # Check if matching was successful
                if match_result.success or force_apply:
                    used_feature_matching = True
                elif match_result.requires_manual_anchors:
                    logger.info("Low confidence match - falling back to relative positioning")
                    
            except Exception as e:
                logger.warning(f"Feature matching failed, using relative positioning: {e}")
                match_result = None
        
        # Create annotations based on matching result or relative positioning
        created_annotations = []
        
        if used_feature_matching and match_result:
            # Use transformed bounding boxes from feature matching
            for transformed_box in match_result.transformed_boxes:
                if not transformed_box.is_valid and not force_apply:
                    logger.warning(
                        f"Skipping invalid box for {transformed_box.original_label.label_name}: "
                        f"{transformed_box.validation_error}"
                    )
                    continue
                
                annotation = Annotation(
                    label_type=transformed_box.original_label.label_type,
                    label_name=transformed_box.original_label.label_name,
                    color=transformed_box.original_label.color,
                    bounding_box=transformed_box.bounding_box,
                )
                annotation = store.add_annotation(document_id, annotation)
                if annotation:
                    created_annotations.append(annotation)
        else:
            # Fall back to relative positioning
            for label in template.labels:
                bbox = BoundingBox(
                    x=label.relative_x * doc_width,
                    y=label.relative_y * doc_height,
                    width=label.relative_width * doc_width,
                    height=label.relative_height * doc_height,
                )
                
                annotation = Annotation(
                    label_type=label.label_type,
                    label_name=label.label_name,
                    color=label.color,
                    bounding_box=bbox,
                )
                annotation = store.add_annotation(document_id, annotation)
                if annotation:
                    created_annotations.append(annotation)
        
        # Update document with template reference
        store.update_document(document_id, {"template_id": template_id})
        
        logger.info(f"Template {template_id} applied to document {document_id}")
        
        # Build response
        response_data = {
            "message": "Template applied successfully",
            "template_id": template_id,
            "annotations_created": len(created_annotations),
            "annotations": [a.to_dict() for a in created_annotations],
            "used_feature_matching": used_feature_matching,
        }
        
        # Include matching details if available
        if match_result:
            response_data["match_result"] = {
                "success": match_result.success,
                "confidence": match_result.confidence,
                "inlier_count": match_result.inlier_count,
                "total_matches": match_result.total_matches,
                "requires_manual_anchors": match_result.requires_manual_anchors,
                "error_message": match_result.error_message,
            }
        
        return Response(response_data, status=status.HTTP_200_OK)


class DocumentExportView(APIView):
    """
    Export document data in various formats.
    """
    
    def post(self, request, document_id):
        """Export document data."""
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ExportRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        export_format = serializer.validated_data["format"]
        include_metadata = serializer.validated_data.get("include_metadata", True)
        validated_only = serializer.validated_data.get("validated_only", False)
        
        # Filter annotations if needed
        annotations = document.annotations
        if validated_only:
            annotations = [a for a in annotations if a.validation_status == "valid"]
        
        # Build export data
        fields = []
        for annotation in annotations:
            field = {
                "name": annotation.label_name,
                "type": annotation.label_type.value,
                "value": annotation.extracted_text,
                "confidence": annotation.confidence,
                "bounding_box": annotation.bounding_box.to_dict() if annotation.bounding_box else None,
                "validation_status": annotation.validation_status,
            }
            fields.append(field)
        
        export_data = {
            "document_id": document.id,
            "source_filename": document.original_filename,
            "processed_at": document.updated_at.isoformat() if document.updated_at else None,
            "template_id": document.template_id,
            "fields": fields,
            "raw_ocr_text": document.raw_ocr_text,
        }
        
        if include_metadata:
            export_data["metadata"] = {
                "preprocessing_applied": document.preprocessing_applied,
                "deskew_angle": document.deskew_angle,
                "ocr_engine": "tesseract-5.x",
                "export_format": export_format,
            }
        
        if export_format == "json":
            return Response(export_data, status=status.HTTP_200_OK)
        
        elif export_format == "csv":
            # Build CSV content
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header row
            writer.writerow([
                "document_id", "source_filename", "field_name", "field_type",
                "value", "confidence", "validation_status"
            ])
            
            # Data rows
            for field in fields:
                writer.writerow([
                    document.id,
                    document.original_filename,
                    field["name"],
                    field["type"],
                    field["value"] or "",
                    field["confidence"] or "",
                    field["validation_status"],
                ])
            
            csv_content = output.getvalue()
            return Response(
                {"format": "csv", "content": csv_content},
                status=status.HTTP_200_OK
            )
        
        elif export_format == "sql":
            # Build SQLite INSERT statements
            sql_statements = []
            parameters = []
            
            # Create table statement
            sql_statements.append("""
CREATE TABLE IF NOT EXISTS extracted_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    source_filename TEXT,
    field_name TEXT NOT NULL,
    field_type TEXT,
    field_value TEXT,
    confidence REAL,
    validation_status TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
            """.strip())
            parameters.append(None)
            
            # Insert statements
            for field in fields:
                sql = """
INSERT INTO extracted_fields (document_id, source_filename, field_name, field_type, field_value, confidence, validation_status)
VALUES (?, ?, ?, ?, ?, ?, ?);
                """.strip()
                sql_statements.append(sql)
                parameters.append((
                    document.id,
                    document.original_filename,
                    field["name"],
                    field["type"],
                    field["value"] or "",
                    field["confidence"],
                    field["validation_status"]
                ))
            
            return Response(
                {
                    "format": "sql", 
                    "statements": sql_statements,
                    "parameters": parameters
                },
                status=status.HTTP_200_OK
            )
        
        return Response(
            {"error": f"Unsupported format: {export_format}"},
            status=status.HTTP_400_BAD_REQUEST
        )


class BatchJobListCreateView(APIView):
    """
    List or create batch processing jobs.
    """
    
    def get(self, request):
        """List batch jobs."""
        channel_id = request.query_params.get("channel_id")
        batch_jobs = store.list_batch_jobs(channel_id=channel_id)
        serializer = BatchJobSerializer(batch_jobs, many=True)
        return Response(
            {"batch_jobs": serializer.data, "count": len(batch_jobs)},
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        """Create a new batch job."""
        serializer = BatchJobSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        batch_job = serializer.save()
        batch_job = store.create_batch_job(batch_job)
        
        logger.info(f"Batch job created: {batch_job.id}")
        
        response_serializer = BatchJobSerializer(batch_job)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class BatchJobDetailView(APIView):
    """
    Get batch job details.
    """
    
    def get(self, request, batch_job_id):
        """Get batch job status."""
        batch_job = store.get_batch_job(batch_job_id)
        if not batch_job:
            return Response(
                {"error": "Batch job not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BatchJobSerializer(batch_job)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DocumentProcessView(APIView):
    """
    Trigger OCR processing on a document.
    """
    
    def post(self, request, document_id):
        """Run OCR processing on document."""
        if not OCR_AVAILABLE:
            return Response(
                {"error": "OCR services not available"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not document.image_data:
            return Response(
                {"error": "Document has no image data"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get preprocessing options from request
        preprocessing_options = request.data.get("preprocessing_options", {})
        
        try:
            # Update status to processing
            store.update_document(document_id, {"ocr_status": OcrStatus.PROCESSING})
            
            # Run OCR pipeline
            ocr_result, metadata = process_document(
                document.image_data,
                preprocessing_options=preprocessing_options
            )
            
            # Update document with results
            updates = {
                "ocr_status": OcrStatus.COMPLETED,
                "ocr_result": ocr_result.to_dict(),
                "raw_ocr_text": ocr_result.full_text,
                "width": metadata.get("original_size", (0, 0))[0],
                "height": metadata.get("original_size", (0, 0))[1],
                "preprocessing_applied": metadata.get("preprocessing_applied", []),
                "deskew_angle": metadata.get("deskew_angle"),
            }
            document = store.update_document(document_id, updates)
            
            logger.info(f"OCR completed for document {document_id}: {ocr_result.word_count} words")
            
            return Response(
                {
                    "document_id": document_id,
                    "status": "completed",
                    "word_count": ocr_result.word_count,
                    "average_confidence": ocr_result.average_confidence,
                    "text_preview": ocr_result.full_text[:500] if ocr_result.full_text else "",
                    "detected_regions": len(ocr_result.detected_regions),
                    "preprocessing_applied": metadata.get("preprocessing_applied", []),
                    "deskew_angle": metadata.get("deskew_angle"),
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"OCR processing failed for document {document_id}: {e}")
            store.update_document(document_id, {"ocr_status": OcrStatus.FAILED})
            return Response(
                {"error": f"OCR processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnnotationExtractTextView(APIView):
    """
    Extract text for annotations using OCR.
    """
    
    def post(self, request, document_id):
        """Extract text for all annotations on a document."""
        if not OCR_AVAILABLE:
            return Response(
                {"error": "OCR services not available"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        document = store.get_document(document_id)
        if not document:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not document.image_data:
            return Response(
                {"error": "Document has no image data"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not document.annotations:
            return Response(
                {"error": "Document has no annotations"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Load image
            image = load_image_from_bytes(document.image_data)
            
            # Extract text for each annotation
            updated_annotations = extract_text_for_annotations(
                image,
                document.annotations
            )
            
            # Update annotations in store
            for annotation in updated_annotations:
                store.update_annotation(
                    document_id,
                    annotation.id,
                    {
                        "extracted_text": annotation.extracted_text,
                        "confidence": annotation.confidence,
                    }
                )
            
            logger.info(f"Text extracted for {len(updated_annotations)} annotations on document {document_id}")
            
            return Response(
                {
                    "document_id": document_id,
                    "annotations_updated": len(updated_annotations),
                    "annotations": [a.to_dict() for a in updated_annotations],
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Text extraction failed for document {document_id}: {e}")
            return Response(
                {"error": f"Text extraction failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
