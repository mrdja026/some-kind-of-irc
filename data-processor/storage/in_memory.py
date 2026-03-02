"""Persistent storage facade used by API views.

This module keeps the existing dataclass interfaces while persisting all state
through Django ORM models in Postgres.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import uuid

from django.db import transaction
from django.utils import timezone

from api.models import (
    AnnotationRecord,
    BatchJobRecord,
    DocumentRecord,
    TemplateLabelRecord,
    TemplateRecord,
)

logger = logging.getLogger(__name__)


class OcrStatus(Enum):
    """Status of OCR processing for a document."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LabelType(Enum):
    """Predefined label types for annotations."""

    HEADER = "header"
    TABLE = "table"
    SIGNATURE = "signature"
    DATE = "date"
    AMOUNT = "amount"
    CUSTOM = "custom"


@dataclass
class BoundingBox:
    """Represents a rectangular region on a document."""

    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundingBox":
        return cls(
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
            rotation=float(data.get("rotation", 0)),
        )


@dataclass
class Annotation:
    """Represents an annotation on a document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    label_type: LabelType = LabelType.CUSTOM
    label_name: str = ""
    color: str = "#FF0000"
    bounding_box: Optional[BoundingBox] = None
    extracted_text: Optional[str] = None
    confidence: Optional[float] = None
    validation_status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "label_type": self.label_type.value,
            "label_name": self.label_name,
            "color": self.color,
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
            "extracted_text": self.extracted_text,
            "confidence": self.confidence,
            "validation_status": self.validation_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Annotation":
        bbox_data = data.get("bounding_box")
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            document_id=data.get("document_id", ""),
            label_type=LabelType(data.get("label_type", "custom")),
            label_name=data.get("label_name", ""),
            color=data.get("color", "#FF0000"),
            bounding_box=BoundingBox.from_dict(bbox_data) if bbox_data else None,
            extracted_text=data.get("extracted_text"),
            confidence=data.get("confidence"),
            validation_status=data.get("validation_status", "pending"),
        )


@dataclass
class Document:
    """Represents an uploaded document with OCR results."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str = ""
    uploaded_by: str = ""
    original_filename: str = ""
    file_type: str = "image"
    page_count: int = 1
    pdf_text_layer: Optional[List[Dict[str, Any]]] = None
    image_url: Optional[str] = None
    image_data: Optional[bytes] = None
    preprocessed_data: Optional[bytes] = None
    thumbnail_url: Optional[str] = None
    width: int = 0
    height: int = 0
    ocr_status: OcrStatus = OcrStatus.PENDING
    ocr_result: Optional[Dict[str, Any]] = None
    raw_ocr_text: Optional[str] = None
    annotations: List[Annotation] = field(default_factory=list)
    template_id: Optional[str] = None
    preprocessing_applied: List[str] = field(default_factory=list)
    deskew_angle: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self, include_image_data: bool = False) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "channel_id": self.channel_id,
            "uploaded_by": self.uploaded_by,
            "original_filename": self.original_filename,
            "filename": self.original_filename,
            "file_type": self.file_type,
            "page_count": self.page_count,
            "pdf_text_layer": self.pdf_text_layer,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "width": self.width,
            "height": self.height,
            "ocr_status": self.ocr_status.value,
            "ocr_result": self.ocr_result,
            "raw_ocr_text": self.raw_ocr_text,
            "annotations": [a.to_dict() for a in self.annotations],
            "template_id": self.template_id,
            "preprocessing_applied": self.preprocessing_applied,
            "deskew_angle": self.deskew_angle,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_image_data:
            result["has_image_data"] = self.image_data is not None
            result["has_preprocessed_data"] = self.preprocessed_data is not None
        return result


@dataclass
class TemplateLabel:
    """Represents a label configuration within a template."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label_type: LabelType = LabelType.CUSTOM
    label_name: str = ""
    color: str = "#FF0000"
    relative_x: float = 0.0
    relative_y: float = 0.0
    relative_width: float = 0.1
    relative_height: float = 0.1
    expected_format: Optional[str] = None
    is_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label_type": self.label_type.value,
            "label_name": self.label_name,
            "color": self.color,
            "relative_x": self.relative_x,
            "relative_y": self.relative_y,
            "relative_width": self.relative_width,
            "relative_height": self.relative_height,
            "expected_format": self.expected_format,
            "is_required": self.is_required,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateLabel":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            label_type=LabelType(data.get("label_type", "custom")),
            label_name=data.get("label_name", ""),
            color=data.get("color", "#FF0000"),
            relative_x=float(data.get("relative_x", 0)),
            relative_y=float(data.get("relative_y", 0)),
            relative_width=float(data.get("relative_width", 0.1)),
            relative_height=float(data.get("relative_height", 0.1)),
            expected_format=data.get("expected_format"),
            is_required=data.get("is_required", False),
        )


@dataclass
class Template:
    """Represents a reusable annotation template."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str = ""
    created_by: str = ""
    name: str = ""
    description: str = ""
    thumbnail_url: Optional[str] = None
    thumbnail_data: Optional[bytes] = None
    version: int = 1
    is_active: bool = True
    labels: List[TemplateLabel] = field(default_factory=list)
    feature_keypoints: Optional[bytes] = None
    source_document_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self, include_keypoints: bool = False) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "channel_id": self.channel_id,
            "created_by": self.created_by,
            "name": self.name,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "version": self.version,
            "is_active": self.is_active,
            "labels": [label.to_dict() for label in self.labels],
            "source_document_id": self.source_document_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_keypoints:
            result["has_keypoints"] = self.feature_keypoints is not None
        return result


@dataclass
class BatchJob:
    """Represents a batch processing job."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str = ""
    template_id: Optional[str] = None
    created_by: str = ""
    status: str = "pending"
    document_ids: List[str] = field(default_factory=list)
    processed_count: int = 0
    failed_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "template_id": self.template_id,
            "created_by": self.created_by,
            "status": self.status,
            "document_ids": self.document_ids,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "total_count": len(self.document_ids),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def _as_label_type(value: str) -> LabelType:
    try:
        return LabelType(value)
    except ValueError:
        return LabelType.CUSTOM


def _as_ocr_status(value: str) -> OcrStatus:
    try:
        return OcrStatus(value)
    except ValueError:
        return OcrStatus.PENDING


def _as_bytes(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    return bytes(value)


def _annotation_from_record(record: AnnotationRecord) -> Annotation:
    bbox = BoundingBox.from_dict(record.bounding_box) if record.bounding_box else None
    return Annotation(
        id=record.id,
        document_id=record.document_id,
        label_type=_as_label_type(record.label_type),
        label_name=record.label_name,
        color=record.color,
        bounding_box=bbox,
        extracted_text=record.extracted_text,
        confidence=record.confidence,
        validation_status=record.validation_status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _document_from_record(record: DocumentRecord, include_annotations: bool = True) -> Document:
    annotations: list[Annotation] = []
    if include_annotations:
        annotations = [_annotation_from_record(item) for item in record.annotations.all()]
    return Document(
        id=record.id,
        channel_id=record.channel_id,
        uploaded_by=record.uploaded_by,
        original_filename=record.original_filename,
        file_type=record.file_type,
        page_count=record.page_count,
        pdf_text_layer=record.pdf_text_layer,
        image_url=record.image_url,
        image_data=_as_bytes(record.image_data),
        preprocessed_data=_as_bytes(record.preprocessed_data),
        thumbnail_url=record.thumbnail_url,
        width=record.width,
        height=record.height,
        ocr_status=_as_ocr_status(record.ocr_status),
        ocr_result=record.ocr_result,
        raw_ocr_text=record.raw_ocr_text,
        annotations=annotations,
        template_id=record.template_id,
        preprocessing_applied=list(record.preprocessing_applied or []),
        deskew_angle=record.deskew_angle,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _template_label_from_record(record: TemplateLabelRecord) -> TemplateLabel:
    return TemplateLabel(
        id=record.id,
        label_type=_as_label_type(record.label_type),
        label_name=record.label_name,
        color=record.color,
        relative_x=record.relative_x,
        relative_y=record.relative_y,
        relative_width=record.relative_width,
        relative_height=record.relative_height,
        expected_format=record.expected_format,
        is_required=record.is_required,
    )


def _template_from_record(record: TemplateRecord) -> Template:
    labels = [_template_label_from_record(item) for item in record.labels.all()]
    return Template(
        id=record.id,
        channel_id=record.channel_id,
        created_by=record.created_by,
        name=record.name,
        description=record.description,
        thumbnail_url=record.thumbnail_url,
        thumbnail_data=_as_bytes(record.thumbnail_data),
        version=record.version,
        is_active=record.is_active,
        labels=labels,
        feature_keypoints=_as_bytes(record.feature_keypoints),
        source_document_id=record.source_document_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _batch_job_from_record(record: BatchJobRecord) -> BatchJob:
    return BatchJob(
        id=record.id,
        channel_id=record.channel_id,
        template_id=record.template_id,
        created_by=record.created_by,
        status=record.status,
        document_ids=list(record.document_ids or []),
        processed_count=record.processed_count,
        failed_count=record.failed_count,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )


class DocumentStore:
    """DB-backed store keeping the original API contract used by views."""

    def __init__(self):
        logger.info("DocumentStore initialized (postgres-backed storage)")

    def clear(self):
        AnnotationRecord.objects.all().delete()
        BatchJobRecord.objects.all().delete()
        TemplateLabelRecord.objects.all().delete()
        TemplateRecord.objects.all().delete()
        DocumentRecord.objects.all().delete()
        logger.info("DocumentStore cleared")

    # ==================== Document Operations ====================

    def create_document(self, document: Document) -> Document:
        now = timezone.now()
        record = DocumentRecord.objects.create(
            id=document.id or str(uuid.uuid4()),
            channel_id=document.channel_id,
            uploaded_by=document.uploaded_by,
            original_filename=document.original_filename,
            file_type=document.file_type,
            page_count=document.page_count,
            pdf_text_layer=document.pdf_text_layer,
            image_url=document.image_url,
            image_data=document.image_data,
            preprocessed_data=document.preprocessed_data,
            thumbnail_url=document.thumbnail_url,
            width=document.width,
            height=document.height,
            ocr_status=document.ocr_status.value,
            ocr_result=document.ocr_result,
            raw_ocr_text=document.raw_ocr_text,
            template_id=document.template_id,
            preprocessing_applied=document.preprocessing_applied,
            deskew_angle=document.deskew_angle,
            created_at=now,
            updated_at=now,
        )
        logger.info("Document created: %s", record.id)
        return _document_from_record(record, include_annotations=False)

    def get_document(self, document_id: str) -> Optional[Document]:
        record = (
            DocumentRecord.objects.filter(pk=document_id)
            .prefetch_related("annotations")
            .first()
        )
        if not record:
            return None
        return _document_from_record(record)

    def update_document(self, document_id: str, updates: Dict[str, Any]) -> Optional[Document]:
        record = (
            DocumentRecord.objects.filter(pk=document_id)
            .prefetch_related("annotations")
            .first()
        )
        if not record:
            return None

        for key, value in updates.items():
            if key == "ocr_status" and isinstance(value, OcrStatus):
                setattr(record, key, value.value)
            elif hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = timezone.now()
        record.save()
        logger.info("Document updated: %s", document_id)
        return _document_from_record(record)

    def delete_document(self, document_id: str) -> bool:
        deleted_count, _ = DocumentRecord.objects.filter(pk=document_id).delete()
        if deleted_count:
            logger.info("Document deleted: %s", document_id)
            return True
        return False

    def list_documents(self, channel_id: Optional[str] = None) -> List[Document]:
        queryset = DocumentRecord.objects.all().prefetch_related("annotations")
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        return [_document_from_record(record) for record in queryset]

    # ==================== Annotation Operations ====================

    def add_annotation(self, document_id: str, annotation: Annotation) -> Optional[Annotation]:
        document = DocumentRecord.objects.filter(pk=document_id).first()
        if not document:
            return None

        now = timezone.now()
        record = AnnotationRecord.objects.create(
            id=annotation.id or str(uuid.uuid4()),
            document=document,
            label_type=annotation.label_type.value,
            label_name=annotation.label_name,
            color=annotation.color,
            bounding_box=annotation.bounding_box.to_dict() if annotation.bounding_box else None,
            extracted_text=annotation.extracted_text,
            confidence=annotation.confidence,
            validation_status=annotation.validation_status,
            created_at=now,
            updated_at=now,
        )
        DocumentRecord.objects.filter(pk=document_id).update(updated_at=now)
        logger.info("Annotation added to document %s: %s", document_id, record.id)
        return _annotation_from_record(record)

    def update_annotation(
        self,
        document_id: str,
        annotation_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Annotation]:
        record = AnnotationRecord.objects.filter(
            pk=annotation_id,
            document_id=document_id,
        ).first()
        if not record:
            return None

        for key, value in updates.items():
            if key == "label_type" and isinstance(value, LabelType):
                setattr(record, key, value.value)
            elif key == "bounding_box" and isinstance(value, BoundingBox):
                record.bounding_box = value.to_dict()
            elif hasattr(record, key):
                setattr(record, key, value)

        now = timezone.now()
        record.updated_at = now
        record.save()
        DocumentRecord.objects.filter(pk=document_id).update(updated_at=now)
        logger.info("Annotation updated: %s", annotation_id)
        return _annotation_from_record(record)

    def delete_annotation(self, document_id: str, annotation_id: str) -> bool:
        deleted_count, _ = AnnotationRecord.objects.filter(
            pk=annotation_id,
            document_id=document_id,
        ).delete()
        if deleted_count:
            DocumentRecord.objects.filter(pk=document_id).update(updated_at=timezone.now())
            logger.info("Annotation deleted: %s", annotation_id)
            return True
        return False

    def get_annotation(self, document_id: str, annotation_id: str) -> Optional[Annotation]:
        record = AnnotationRecord.objects.filter(
            pk=annotation_id,
            document_id=document_id,
        ).first()
        if not record:
            return None
        return _annotation_from_record(record)

    # ==================== Template Operations ====================

    def create_template(self, template: Template) -> Template:
        now = timezone.now()
        with transaction.atomic():
            template_record = TemplateRecord.objects.create(
                id=template.id or str(uuid.uuid4()),
                channel_id=template.channel_id,
                created_by=template.created_by,
                name=template.name,
                description=template.description,
                thumbnail_url=template.thumbnail_url,
                thumbnail_data=template.thumbnail_data,
                version=template.version,
                is_active=template.is_active,
                feature_keypoints=template.feature_keypoints,
                source_document_id=template.source_document_id,
                created_at=now,
                updated_at=now,
            )

            for label in template.labels:
                TemplateLabelRecord.objects.create(
                    id=label.id or str(uuid.uuid4()),
                    template=template_record,
                    label_type=label.label_type.value,
                    label_name=label.label_name,
                    color=label.color,
                    relative_x=label.relative_x,
                    relative_y=label.relative_y,
                    relative_width=label.relative_width,
                    relative_height=label.relative_height,
                    expected_format=label.expected_format,
                    is_required=label.is_required,
                )

        logger.info("Template created: %s", template_record.id)
        return _template_from_record(
            TemplateRecord.objects.prefetch_related("labels").get(pk=template_record.id)
        )

    def get_template(self, template_id: str) -> Optional[Template]:
        record = TemplateRecord.objects.filter(pk=template_id).prefetch_related("labels").first()
        if not record:
            return None
        return _template_from_record(record)

    def update_template(self, template_id: str, updates: Dict[str, Any]) -> Optional[Template]:
        record = TemplateRecord.objects.filter(pk=template_id).prefetch_related("labels").first()
        if not record:
            return None

        labels = updates.pop("labels", None)
        record.version += 1

        for key, value in updates.items():
            if hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = timezone.now()

        with transaction.atomic():
            record.save()
            if labels is not None:
                record.labels.all().delete()
                for label in labels:
                    TemplateLabelRecord.objects.create(
                        id=label.id or str(uuid.uuid4()),
                        template=record,
                        label_type=label.label_type.value,
                        label_name=label.label_name,
                        color=label.color,
                        relative_x=label.relative_x,
                        relative_y=label.relative_y,
                        relative_width=label.relative_width,
                        relative_height=label.relative_height,
                        expected_format=label.expected_format,
                        is_required=label.is_required,
                    )

        logger.info("Template updated: %s (version %s)", template_id, record.version)
        return _template_from_record(
            TemplateRecord.objects.prefetch_related("labels").get(pk=record.id)
        )

    def delete_template(self, template_id: str) -> bool:
        deleted_count, _ = TemplateRecord.objects.filter(pk=template_id).delete()
        if deleted_count:
            logger.info("Template deleted: %s", template_id)
            return True
        return False

    def list_templates(self, channel_id: Optional[str] = None, active_only: bool = True) -> List[Template]:
        queryset = TemplateRecord.objects.all().prefetch_related("labels")
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return [_template_from_record(record) for record in queryset]

    # ==================== Batch Job Operations ====================

    def create_batch_job(self, batch_job: BatchJob) -> BatchJob:
        template = None
        if batch_job.template_id:
            template = TemplateRecord.objects.filter(pk=batch_job.template_id).first()

        now = timezone.now()
        record = BatchJobRecord.objects.create(
            id=batch_job.id or str(uuid.uuid4()),
            channel_id=batch_job.channel_id,
            template=template,
            created_by=batch_job.created_by,
            status=batch_job.status,
            document_ids=batch_job.document_ids,
            processed_count=batch_job.processed_count,
            failed_count=batch_job.failed_count,
            error_message=batch_job.error_message,
            created_at=now,
            updated_at=now,
            completed_at=batch_job.completed_at,
        )
        logger.info("Batch job created: %s", record.id)
        return _batch_job_from_record(record)

    def get_batch_job(self, batch_job_id: str) -> Optional[BatchJob]:
        record = BatchJobRecord.objects.filter(pk=batch_job_id).first()
        if not record:
            return None
        return _batch_job_from_record(record)

    def update_batch_job(self, batch_job_id: str, updates: Dict[str, Any]) -> Optional[BatchJob]:
        record = BatchJobRecord.objects.filter(pk=batch_job_id).first()
        if not record:
            return None

        for key, value in updates.items():
            if key == "template_id":
                record.template = TemplateRecord.objects.filter(pk=value).first() if value else None
            elif hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = timezone.now()
        if record.status in ("completed", "failed") and not record.completed_at:
            record.completed_at = timezone.now()

        record.save()
        logger.info("Batch job updated: %s (status: %s)", batch_job_id, record.status)
        return _batch_job_from_record(record)

    def list_batch_jobs(self, channel_id: Optional[str] = None) -> List[BatchJob]:
        queryset = BatchJobRecord.objects.all()
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        return [_batch_job_from_record(record) for record in queryset]

    # ==================== Utility Methods ====================

    def get_stats(self) -> Dict[str, Any]:
        documents_qs = DocumentRecord.objects.all()
        return {
            "documents_count": documents_qs.count(),
            "templates_count": TemplateRecord.objects.count(),
            "batch_jobs_count": BatchJobRecord.objects.count(),
            "total_annotations": AnnotationRecord.objects.count(),
            "documents_by_status": {
                status.value: documents_qs.filter(ocr_status=status.value).count()
                for status in OcrStatus
            },
        }


store = DocumentStore()
