"""
In-memory storage for documents, annotations, and templates.

This module provides data classes and a singleton store for MVP implementation.
Data is not persisted across service restarts.

Future migration path: Replace DocumentStore with Django models while keeping
the same dataclass interfaces for serializers.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid
import logging
import threading

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
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundingBox":
        """Create from dictionary."""
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
    validation_status: str = "pending"  # pending, valid, invalid
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
        """Create from dictionary."""
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
    file_type: str = "image"  # image or pdf
    page_count: int = 1
    pdf_text_layer: Optional[List[Dict[str, Any]]] = None
    image_url: Optional[str] = None  # MinIO URL
    image_data: Optional[bytes] = None  # In-memory image storage
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
        """Convert to dictionary for JSON serialization."""
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
    relative_x: float = 0.0  # 0.0-1.0 relative to image width
    relative_y: float = 0.0
    relative_width: float = 0.1
    relative_height: float = 0.1
    expected_format: Optional[str] = None  # regex pattern for validation
    is_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
        """Create from dictionary."""
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
    thumbnail_data: Optional[bytes] = None  # In-memory thumbnail
    version: int = 1
    is_active: bool = True
    labels: List[TemplateLabel] = field(default_factory=list)
    feature_keypoints: Optional[bytes] = None  # Serialized ORB keypoints
    source_document_id: Optional[str] = None  # Document used to create template
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self, include_keypoints: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
    status: str = "pending"  # pending, processing, completed, failed
    document_ids: List[str] = field(default_factory=list)
    processed_count: int = 0
    failed_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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


class DocumentStore:
    """
    Singleton store for in-memory document and template management.
    
    Thread-safe implementation using locks for concurrent access.
    All data is lost on service restart (MVP behavior).
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._data_lock = threading.RLock()
        self.documents: Dict[str, Document] = {}
        self.templates: Dict[str, Template] = {}
        self.batch_jobs: Dict[str, BatchJob] = {}
        self._initialized = True
        logger.info("DocumentStore initialized (in-memory storage)")
    
    def clear(self):
        """Clear all data (useful for testing)."""
        with self._data_lock:
            self.documents.clear()
            self.templates.clear()
            self.batch_jobs.clear()
            logger.info("DocumentStore cleared")
    
    # ==================== Document Operations ====================
    
    def create_document(self, document: Document) -> Document:
        """Create a new document."""
        with self._data_lock:
            if not document.id:
                document.id = str(uuid.uuid4())
            document.created_at = datetime.utcnow()
            document.updated_at = datetime.utcnow()
            self.documents[document.id] = document
            logger.info(f"Document created: {document.id}")
            return document
    
    def get_document(self, document_id: str) -> Optional[Document]:
        """Get a document by ID."""
        with self._data_lock:
            return self.documents.get(document_id)
    
    def update_document(self, document_id: str, updates: Dict[str, Any]) -> Optional[Document]:
        """Update a document."""
        with self._data_lock:
            document = self.documents.get(document_id)
            if not document:
                return None
            
            for key, value in updates.items():
                if hasattr(document, key):
                    setattr(document, key, value)
            
            document.updated_at = datetime.utcnow()
            logger.info(f"Document updated: {document_id}")
            return document
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document."""
        with self._data_lock:
            if document_id in self.documents:
                del self.documents[document_id]
                logger.info(f"Document deleted: {document_id}")
                return True
            return False
    
    def list_documents(self, channel_id: Optional[str] = None) -> List[Document]:
        """List all documents, optionally filtered by channel."""
        with self._data_lock:
            documents = list(self.documents.values())
            if channel_id:
                documents = [d for d in documents if d.channel_id == channel_id]
            return sorted(documents, key=lambda x: x.created_at, reverse=True)
    
    # ==================== Annotation Operations ====================
    
    def add_annotation(self, document_id: str, annotation: Annotation) -> Optional[Annotation]:
        """Add an annotation to a document."""
        with self._data_lock:
            document = self.documents.get(document_id)
            if not document:
                return None
            
            if not annotation.id:
                annotation.id = str(uuid.uuid4())
            annotation.document_id = document_id
            annotation.created_at = datetime.utcnow()
            annotation.updated_at = datetime.utcnow()
            
            document.annotations.append(annotation)
            document.updated_at = datetime.utcnow()
            logger.info(f"Annotation added to document {document_id}: {annotation.id}")
            return annotation
    
    def update_annotation(
        self, document_id: str, annotation_id: str, updates: Dict[str, Any]
    ) -> Optional[Annotation]:
        """Update an annotation."""
        with self._data_lock:
            document = self.documents.get(document_id)
            if not document:
                return None
            
            for annotation in document.annotations:
                if annotation.id == annotation_id:
                    for key, value in updates.items():
                        if hasattr(annotation, key):
                            setattr(annotation, key, value)
                    annotation.updated_at = datetime.utcnow()
                    document.updated_at = datetime.utcnow()
                    logger.info(f"Annotation updated: {annotation_id}")
                    return annotation
            return None
    
    def delete_annotation(self, document_id: str, annotation_id: str) -> bool:
        """Delete an annotation from a document."""
        with self._data_lock:
            document = self.documents.get(document_id)
            if not document:
                return False
            
            original_count = len(document.annotations)
            document.annotations = [a for a in document.annotations if a.id != annotation_id]
            
            if len(document.annotations) < original_count:
                document.updated_at = datetime.utcnow()
                logger.info(f"Annotation deleted: {annotation_id}")
                return True
            return False
    
    def get_annotation(self, document_id: str, annotation_id: str) -> Optional[Annotation]:
        """Get a specific annotation from a document."""
        with self._data_lock:
            document = self.documents.get(document_id)
            if not document:
                return None
            
            for annotation in document.annotations:
                if annotation.id == annotation_id:
                    return annotation
            return None
    
    # ==================== Template Operations ====================
    
    def create_template(self, template: Template) -> Template:
        """Create a new template."""
        with self._data_lock:
            if not template.id:
                template.id = str(uuid.uuid4())
            template.created_at = datetime.utcnow()
            template.updated_at = datetime.utcnow()
            self.templates[template.id] = template
            logger.info(f"Template created: {template.id}")
            return template
    
    def get_template(self, template_id: str) -> Optional[Template]:
        """Get a template by ID."""
        with self._data_lock:
            return self.templates.get(template_id)
    
    def update_template(self, template_id: str, updates: Dict[str, Any]) -> Optional[Template]:
        """Update a template."""
        with self._data_lock:
            template = self.templates.get(template_id)
            if not template:
                return None
            
            # Increment version on update
            template.version += 1
            
            for key, value in updates.items():
                if hasattr(template, key):
                    setattr(template, key, value)
            
            template.updated_at = datetime.utcnow()
            logger.info(f"Template updated: {template_id} (version {template.version})")
            return template
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template."""
        with self._data_lock:
            if template_id in self.templates:
                del self.templates[template_id]
                logger.info(f"Template deleted: {template_id}")
                return True
            return False
    
    def list_templates(self, channel_id: Optional[str] = None, active_only: bool = True) -> List[Template]:
        """List all templates, optionally filtered by channel."""
        with self._data_lock:
            templates = list(self.templates.values())
            if channel_id:
                templates = [t for t in templates if t.channel_id == channel_id]
            if active_only:
                templates = [t for t in templates if t.is_active]
            return sorted(templates, key=lambda x: x.created_at, reverse=True)
    
    # ==================== Batch Job Operations ====================
    
    def create_batch_job(self, batch_job: BatchJob) -> BatchJob:
        """Create a new batch job."""
        with self._data_lock:
            if not batch_job.id:
                batch_job.id = str(uuid.uuid4())
            batch_job.created_at = datetime.utcnow()
            batch_job.updated_at = datetime.utcnow()
            self.batch_jobs[batch_job.id] = batch_job
            logger.info(f"Batch job created: {batch_job.id}")
            return batch_job
    
    def get_batch_job(self, batch_job_id: str) -> Optional[BatchJob]:
        """Get a batch job by ID."""
        with self._data_lock:
            return self.batch_jobs.get(batch_job_id)
    
    def update_batch_job(self, batch_job_id: str, updates: Dict[str, Any]) -> Optional[BatchJob]:
        """Update a batch job."""
        with self._data_lock:
            batch_job = self.batch_jobs.get(batch_job_id)
            if not batch_job:
                return None
            
            for key, value in updates.items():
                if hasattr(batch_job, key):
                    setattr(batch_job, key, value)
            
            batch_job.updated_at = datetime.utcnow()
            
            # Auto-set completed_at when status is terminal
            if batch_job.status in ("completed", "failed") and not batch_job.completed_at:
                batch_job.completed_at = datetime.utcnow()
            
            logger.info(f"Batch job updated: {batch_job_id} (status: {batch_job.status})")
            return batch_job
    
    def list_batch_jobs(self, channel_id: Optional[str] = None) -> List[BatchJob]:
        """List all batch jobs, optionally filtered by channel."""
        with self._data_lock:
            batch_jobs = list(self.batch_jobs.values())
            if channel_id:
                batch_jobs = [b for b in batch_jobs if b.channel_id == channel_id]
            return sorted(batch_jobs, key=lambda x: x.created_at, reverse=True)
    
    # ==================== Utility Methods ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._data_lock:
            total_annotations = sum(len(d.annotations) for d in self.documents.values())
            return {
                "documents_count": len(self.documents),
                "templates_count": len(self.templates),
                "batch_jobs_count": len(self.batch_jobs),
                "total_annotations": total_annotations,
                "documents_by_status": {
                    status.value: len([d for d in self.documents.values() if d.ocr_status == status])
                    for status in OcrStatus
                },
            }


# Global store instance
store = DocumentStore()
