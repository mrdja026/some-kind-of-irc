"""Database models for persistent document processing state."""

import uuid

from django.db import models
from django.utils import timezone


def _uuid_str() -> str:
    return str(uuid.uuid4())


class DocumentRecord(models.Model):
    OCR_PENDING = "pending"
    OCR_PROCESSING = "processing"
    OCR_COMPLETED = "completed"
    OCR_FAILED = "failed"

    OCR_STATUS_CHOICES = [
        (OCR_PENDING, OCR_PENDING),
        (OCR_PROCESSING, OCR_PROCESSING),
        (OCR_COMPLETED, OCR_COMPLETED),
        (OCR_FAILED, OCR_FAILED),
    ]

    id = models.CharField(primary_key=True, max_length=36, default=_uuid_str, editable=False)
    channel_id = models.CharField(max_length=255, db_index=True)
    uploaded_by = models.CharField(max_length=255, blank=True, default="")
    original_filename = models.CharField(max_length=500)
    file_type = models.CharField(max_length=32, default="image")
    page_count = models.PositiveIntegerField(default=1)
    pdf_text_layer = models.JSONField(null=True, blank=True)
    image_url = models.TextField(null=True, blank=True)
    image_data = models.BinaryField(null=True, blank=True)
    preprocessed_data = models.BinaryField(null=True, blank=True)
    thumbnail_url = models.TextField(null=True, blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    ocr_status = models.CharField(
        max_length=32,
        choices=OCR_STATUS_CHOICES,
        default=OCR_PENDING,
    )
    ocr_result = models.JSONField(null=True, blank=True)
    raw_ocr_text = models.TextField(null=True, blank=True)
    template_id = models.CharField(max_length=36, null=True, blank=True)
    preprocessing_applied = models.JSONField(default=list, blank=True)
    deskew_angle = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["channel_id", "created_at"],
                name="api_documen_channel_4292cc_idx",
            )
        ]


class AnnotationRecord(models.Model):
    VALIDATION_CHOICES = [
        ("pending", "pending"),
        ("valid", "valid"),
        ("invalid", "invalid"),
    ]

    id = models.CharField(primary_key=True, max_length=36, default=_uuid_str, editable=False)
    document = models.ForeignKey(
        DocumentRecord,
        on_delete=models.CASCADE,
        related_name="annotations",
    )
    label_type = models.CharField(max_length=32, default="custom")
    label_name = models.CharField(max_length=255, blank=True, default="")
    color = models.CharField(max_length=20, default="#FF0000")
    bounding_box = models.JSONField(null=True, blank=True)
    extracted_text = models.TextField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    validation_status = models.CharField(
        max_length=16,
        choices=VALIDATION_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]


class TemplateRecord(models.Model):
    id = models.CharField(primary_key=True, max_length=36, default=_uuid_str, editable=False)
    channel_id = models.CharField(max_length=255, db_index=True)
    created_by = models.CharField(max_length=255, blank=True, default="")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    thumbnail_url = models.TextField(null=True, blank=True)
    thumbnail_data = models.BinaryField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    feature_keypoints = models.BinaryField(null=True, blank=True)
    source_document_id = models.CharField(max_length=36, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["channel_id", "created_at"],
                name="api_templat_channel_6204ea_idx",
            )
        ]


class TemplateLabelRecord(models.Model):
    id = models.CharField(primary_key=True, max_length=36, default=_uuid_str, editable=False)
    template = models.ForeignKey(
        TemplateRecord,
        on_delete=models.CASCADE,
        related_name="labels",
    )
    label_type = models.CharField(max_length=32, default="custom")
    label_name = models.CharField(max_length=255)
    color = models.CharField(max_length=20, default="#FF0000")
    relative_x = models.FloatField(default=0.0)
    relative_y = models.FloatField(default=0.0)
    relative_width = models.FloatField(default=0.1)
    relative_height = models.FloatField(default=0.1)
    expected_format = models.CharField(max_length=255, null=True, blank=True)
    is_required = models.BooleanField(default=False)


class BatchJobRecord(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("processing", "processing"),
        ("completed", "completed"),
        ("failed", "failed"),
    ]

    id = models.CharField(primary_key=True, max_length=36, default=_uuid_str, editable=False)
    channel_id = models.CharField(max_length=255, db_index=True)
    template = models.ForeignKey(
        TemplateRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_jobs",
    )
    created_by = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    document_ids = models.JSONField(default=list, blank=True)
    processed_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["channel_id", "created_at"],
                name="api_batchjo_channel_5a0091_idx",
            )
        ]
