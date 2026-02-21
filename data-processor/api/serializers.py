"""
Django REST Framework serializers for data-processor API.

These serializers handle validation and serialization of Document, Annotation,
Template, and related data structures.
"""

import mimetypes

from rest_framework import serializers
from storage.in_memory import (
    LabelType,
    OcrStatus,
    BoundingBox,
    Annotation,
    Document,
    TemplateLabel,
    Template,
    BatchJob,
)


class BoundingBoxSerializer(serializers.Serializer):
    """Serializer for bounding box coordinates."""
    x = serializers.FloatField(min_value=0)
    y = serializers.FloatField(min_value=0)
    width = serializers.FloatField(min_value=0)
    height = serializers.FloatField(min_value=0)
    rotation = serializers.FloatField(default=0.0, min_value=-360, max_value=360)
    
    def create(self, validated_data):
        return BoundingBox(**validated_data)
    
    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        return instance


class AnnotationSerializer(serializers.Serializer):
    """Serializer for document annotations."""
    id = serializers.CharField(read_only=True)
    document_id = serializers.CharField(read_only=True)
    label_type = serializers.ChoiceField(
        choices=[(t.value, t.value) for t in LabelType],
        default=LabelType.CUSTOM.value
    )
    label_name = serializers.CharField(max_length=255, allow_blank=True)
    color = serializers.CharField(max_length=20, default="#FF0000")
    bounding_box = BoundingBoxSerializer(required=True)
    extracted_text = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    confidence = serializers.FloatField(
        allow_null=True, required=False, min_value=0, max_value=1
    )
    validation_status = serializers.ChoiceField(
        choices=["pending", "valid", "invalid"],
        default="pending"
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    def create(self, validated_data):
        bbox_data = validated_data.pop("bounding_box", None)
        label_type_str = validated_data.pop("label_type", "custom")
        
        annotation = Annotation(
            label_type=LabelType(label_type_str),
            **validated_data
        )
        if bbox_data:
            annotation.bounding_box = BoundingBox(**bbox_data)
        return annotation
    
    def update(self, instance, validated_data):
        bbox_data = validated_data.pop("bounding_box", None)
        
        if "label_type" in validated_data:
            instance.label_type = LabelType(validated_data.pop("label_type"))
        
        for key, value in validated_data.items():
            setattr(instance, key, value)
        
        if bbox_data:
            instance.bounding_box = BoundingBox(**bbox_data)
        
        return instance
    
    def to_representation(self, instance):
        """Convert Annotation dataclass to dict."""
        if isinstance(instance, dict):
            return instance
        return instance.to_dict()


class DocumentSerializer(serializers.Serializer):
    """Serializer for uploaded documents."""
    id = serializers.CharField(read_only=True)
    channel_id = serializers.CharField(max_length=255, required=True)
    uploaded_by = serializers.CharField(max_length=255, required=False, allow_blank=True)
    original_filename = serializers.CharField(max_length=500, required=True)
    image_url = serializers.URLField(read_only=True, allow_null=True)
    thumbnail_url = serializers.URLField(read_only=True, allow_null=True)
    width = serializers.IntegerField(read_only=True, min_value=0)
    height = serializers.IntegerField(read_only=True, min_value=0)
    ocr_status = serializers.ChoiceField(
        choices=[(s.value, s.value) for s in OcrStatus],
        read_only=True
    )
    ocr_result = serializers.DictField(read_only=True, allow_null=True)
    raw_ocr_text = serializers.CharField(read_only=True, allow_null=True)
    annotations = AnnotationSerializer(many=True, read_only=True)
    template_id = serializers.CharField(read_only=True, allow_null=True)
    preprocessing_applied = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    deskew_angle = serializers.FloatField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    def create(self, validated_data):
        return Document(**validated_data)
    
    def to_representation(self, instance):
        """Convert Document dataclass to dict."""
        if isinstance(instance, dict):
            return instance
        return instance.to_dict()


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for document upload requests."""
    channel_id = serializers.CharField(max_length=255, required=True)
    uploaded_by = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    image = serializers.ImageField(required=True)
    apply_template_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    preprocessing_options = serializers.DictField(required=False, default=dict)

    def validate_image(self, value):
        content_type = (
            getattr(value, "content_type", None)
            or mimetypes.guess_type(getattr(value, "name", ""))[0]
        )
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise serializers.ValidationError(
                "Unsupported file type. Use JPEG, PNG, or WebP."
            )
        return value


class TemplateLabelSerializer(serializers.Serializer):
    """Serializer for template labels."""
    id = serializers.CharField(read_only=True)
    label_type = serializers.ChoiceField(
        choices=[(t.value, t.value) for t in LabelType],
        default=LabelType.CUSTOM.value
    )
    label_name = serializers.CharField(max_length=255)
    color = serializers.CharField(max_length=20, default="#FF0000")
    relative_x = serializers.FloatField(min_value=0, max_value=1)
    relative_y = serializers.FloatField(min_value=0, max_value=1)
    relative_width = serializers.FloatField(min_value=0, max_value=1)
    relative_height = serializers.FloatField(min_value=0, max_value=1)
    expected_format = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
        help_text="Regex pattern for field validation"
    )
    is_required = serializers.BooleanField(default=False)
    
    def create(self, validated_data):
        label_type_str = validated_data.pop("label_type", "custom")
        return TemplateLabel(
            label_type=LabelType(label_type_str),
            **validated_data
        )
    
    def to_representation(self, instance):
        """Convert TemplateLabel dataclass to dict."""
        if isinstance(instance, dict):
            return instance
        return instance.to_dict()


class TemplateSerializer(serializers.Serializer):
    """Serializer for annotation templates."""
    id = serializers.CharField(read_only=True)
    channel_id = serializers.CharField(max_length=255, required=True)
    created_by = serializers.CharField(max_length=255, required=False, allow_blank=True)
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default=""
    )
    thumbnail_url = serializers.URLField(read_only=True, allow_null=True)
    version = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(default=True)
    labels = TemplateLabelSerializer(many=True, required=True)
    source_document_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    def create(self, validated_data):
        labels_data = validated_data.pop("labels", [])
        
        template = Template(**validated_data)
        
        for label_data in labels_data:
            label_serializer = TemplateLabelSerializer(data=label_data)
            if label_serializer.is_valid():
                template.labels.append(label_serializer.save())
        
        return template
    
    def update(self, instance, validated_data):
        labels_data = validated_data.pop("labels", None)
        
        for key, value in validated_data.items():
            setattr(instance, key, value)
        
        if labels_data is not None:
            instance.labels = []
            for label_data in labels_data:
                label_serializer = TemplateLabelSerializer(data=label_data)
                if label_serializer.is_valid():
                    instance.labels.append(label_serializer.save())
        
        return instance
    
    def to_representation(self, instance):
        """Convert Template dataclass to dict."""
        if isinstance(instance, dict):
            return instance
        return instance.to_dict()


class TemplateApplySerializer(serializers.Serializer):
    """Serializer for template application requests."""
    template_id = serializers.CharField(required=True)
    confidence_threshold = serializers.FloatField(
        default=0.6, min_value=0, max_value=1,
        help_text="Minimum confidence for automatic template matching"
    )
    use_feature_matching = serializers.BooleanField(
        default=True,
        help_text="Whether to use ORB feature matching (if available)"
    )
    force_apply = serializers.BooleanField(
        default=False,
        help_text="Apply template even if confidence is below threshold"
    )


class TemplateMatchResultSerializer(serializers.Serializer):
    """Serializer for template matching results."""
    success = serializers.BooleanField()
    confidence = serializers.FloatField()
    inlier_count = serializers.IntegerField()
    total_matches = serializers.IntegerField()
    requires_manual_anchors = serializers.BooleanField()
    error_message = serializers.CharField(allow_null=True)
    transformed_boxes = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class TransformedBoxSerializer(serializers.Serializer):
    """Serializer for a transformed bounding box from template matching."""
    label_name = serializers.CharField()
    label_type = serializers.ChoiceField(
        choices=[(t.value, t.value) for t in LabelType]
    )
    bounding_box = BoundingBoxSerializer()
    is_valid = serializers.BooleanField()
    validation_error = serializers.CharField(allow_null=True)


class BatchJobSerializer(serializers.Serializer):
    """Serializer for batch processing jobs."""
    id = serializers.CharField(read_only=True)
    channel_id = serializers.CharField(max_length=255, required=True)
    template_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    created_by = serializers.CharField(max_length=255, required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=["pending", "processing", "completed", "failed"],
        read_only=True
    )
    document_ids = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )
    processed_count = serializers.IntegerField(read_only=True)
    failed_count = serializers.IntegerField(read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    error_message = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    
    def create(self, validated_data):
        return BatchJob(**validated_data)
    
    def to_representation(self, instance):
        """Convert BatchJob dataclass to dict."""
        if isinstance(instance, dict):
            return instance
        return instance.to_dict()


class ExportRequestSerializer(serializers.Serializer):
    """Serializer for data export requests."""
    format = serializers.ChoiceField(
        choices=["json", "csv", "sql"],
        required=True
    )
    include_metadata = serializers.BooleanField(default=True)
    validated_only = serializers.BooleanField(
        default=False,
        help_text="Only export fields with validation_status='valid'"
    )


class ExportResponseSerializer(serializers.Serializer):
    """Serializer for export response data."""
    document_id = serializers.CharField()
    source_filename = serializers.CharField()
    processed_at = serializers.DateTimeField()
    template_id = serializers.CharField(allow_null=True)
    fields = serializers.ListField()
    raw_ocr_text = serializers.CharField(allow_null=True)
    metadata = serializers.DictField()
