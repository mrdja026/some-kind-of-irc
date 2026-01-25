"""
URL routing for the data-processor API.

Provides endpoints for:
- Health check
- Document upload and processing
- Annotation management
- Template management
- Data export
- Batch processing
"""

from django.urls import path
from . import views

urlpatterns = [
    # Health check endpoint
    path("health", views.health_check, name="health-check"),
    
    # Document endpoints
    path("documents/", views.DocumentListCreateView.as_view(), name="document-list-create"),
    path("documents/<str:document_id>/", views.DocumentDetailView.as_view(), name="document-detail"),
    
    # Annotation endpoints
    path(
        "documents/<str:document_id>/annotations/",
        views.AnnotationListCreateView.as_view(),
        name="annotation-list-create"
    ),
    path(
        "documents/<str:document_id>/annotations/<str:annotation_id>/",
        views.AnnotationDetailView.as_view(),
        name="annotation-detail"
    ),
    
    # Template application
    path(
        "documents/<str:document_id>/apply-template/",
        views.TemplateApplyView.as_view(),
        name="template-apply"
    ),
    
    # Export endpoint
    path(
        "documents/<str:document_id>/export/",
        views.DocumentExportView.as_view(),
        name="document-export"
    ),
    
    # OCR processing endpoint
    path(
        "documents/<str:document_id>/process/",
        views.DocumentProcessView.as_view(),
        name="document-process"
    ),
    
    # Extract text for annotations
    path(
        "documents/<str:document_id>/extract-text/",
        views.AnnotationExtractTextView.as_view(),
        name="annotation-extract-text"
    ),
    
    # Template endpoints
    path("templates/", views.TemplateListCreateView.as_view(), name="template-list-create"),
    path("templates/<str:template_id>/", views.TemplateDetailView.as_view(), name="template-detail"),
    
    # Batch processing endpoints
    path("batch/", views.BatchJobListCreateView.as_view(), name="batch-job-list-create"),
    path("batch/<str:batch_job_id>/", views.BatchJobDetailView.as_view(), name="batch-job-detail"),
]
