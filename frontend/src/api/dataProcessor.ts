/**
 * Data Processor API Client
 *
 * This module provides API functions for interacting with the data-processor
 * service through the reverse proxy (Caddy).
 */

import type {
  Document,
  Annotation,
  Template,
  LabelType,
  MatchedRegion,
} from '../types';

const DATA_PROCESSOR_BASE_URL =
  typeof window === 'undefined'
    ? import.meta.env.VITE_DATA_PROCESSOR_URL || import.meta.env.VITE_API_URL || 'http://backend:8002'
    : (() => {
        const origin = window.location.origin;
        const isLocalHost =
          window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        const normalizeLocalDataUrl = (value: string): string => {
          if (!isLocalHost) {
            return value;
          }
          if (value.includes(':8002') || value.includes(':4269')) {
            return 'http://localhost:8080';
          }
          return value;
        };
        const explicit = import.meta.env.VITE_PUBLIC_DATA_PROCESSOR_URL?.trim();
        if (explicit) {
          if (explicit.includes('localhost') && window.location.hostname !== 'localhost') {
            return origin;
          }
          return normalizeLocalDataUrl(explicit);
        }
        const fallback = import.meta.env.VITE_PUBLIC_API_URL?.trim();
        if (fallback) {
          if (fallback.includes('localhost') && window.location.hostname !== 'localhost') {
            return origin;
          }
          return normalizeLocalDataUrl(fallback);
        }
        if (isLocalHost) {
          return 'http://localhost:8080';
        }
        return origin;
      })();

export const DATA_PROCESSOR_URL = `${DATA_PROCESSOR_BASE_URL}/data-processor`;

// ============================================================================
// Document APIs
// ============================================================================

export type DocumentUploadResponse = {
  id: string;
  filename?: string;
  original_filename?: string;
  status?: string;
  message?: string;
};

export type DocumentListResponse = {
  documents: Document[];
  count: number;
};

/**
 * Upload a document to the data processor service.
 */
export const uploadDocument = async (
  file: File,
  channelId: string | number
): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('channel_id', String(channelId));

  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
};

/**
 * List documents, optionally filtered by channel.
 */
export const listDocuments = async (
  channelId?: string | number
): Promise<DocumentListResponse> => {
  const url = new URL(`${DATA_PROCESSOR_URL}/documents/`);
  if (channelId !== undefined && channelId !== null) {
    url.searchParams.set('channel_id', String(channelId));
  }

  const response = await fetch(url.toString(), {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list documents' }));
    throw new Error(error.detail || 'Failed to list documents');
  }

  return response.json();
};

/**
 * Get document details and OCR results.
 */
export const getDocument = async (documentId: string): Promise<Document> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/${documentId}/`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get document' }));
    throw new Error(error.detail || 'Failed to get document');
  }

  return response.json();
};

/**
 * Delete a document.
 */
export const deleteDocument = async (documentId: string): Promise<void> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/${documentId}/`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Delete failed' }));
    throw new Error(error.detail || 'Delete failed');
  }
};

/**
 * Trigger OCR processing for a document.
 */
export const processDocument = async (documentId: string): Promise<{ status: string; message: string }> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/${documentId}/process/`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Process failed' }));
    throw new Error(error.detail || 'Process failed');
  }

  return response.json();
};

/**
 * Extract text for all annotations in a document.
 */
export const extractText = async (documentId: string): Promise<Annotation[]> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/${documentId}/extract-text/`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Extraction failed' }));
    throw new Error(error.detail || 'Extraction failed');
  }

  return response.json();
};

// ============================================================================
// Annotation APIs
// ============================================================================

export type CreateAnnotationRequest = {
  label_type: LabelType;
  label_name: string;
  color?: string;
  bounding_box: {
    x: number;
    y: number;
    width: number;
    height: number;
    rotation?: number;
  };
};

export type UpdateAnnotationRequest = Partial<CreateAnnotationRequest>;

/**
 * Create an annotation on a document.
 */
export const createAnnotation = async (
  documentId: string,
  annotation: CreateAnnotationRequest
): Promise<Annotation> => {
  const payload = {
    ...annotation,
    bounding_box: {
      ...annotation.bounding_box,
      rotation: annotation.bounding_box.rotation ?? 0,
    },
  };

  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/${documentId}/annotations/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Create annotation failed' }));
    throw new Error(error.detail || 'Create annotation failed');
  }

  return response.json();
};

/**
 * Update an annotation on a document.
 */
export const updateAnnotation = async (
  documentId: string,
  annotationId: string,
  updates: UpdateAnnotationRequest
): Promise<Annotation> => {
  const payload = { ...updates };
  if (updates.bounding_box) {
    payload.bounding_box = {
      ...updates.bounding_box,
      rotation: updates.bounding_box.rotation ?? 0,
    };
  }

  const response = await fetch(
    `${DATA_PROCESSOR_URL}/documents/${documentId}/annotations/${annotationId}/`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Update annotation failed' }));
    throw new Error(error.detail || 'Update annotation failed');
  }

  return response.json();
};

/**
 * Delete an annotation from a document.
 */
export const deleteAnnotation = async (
  documentId: string,
  annotationId: string
): Promise<void> => {
  const response = await fetch(
    `${DATA_PROCESSOR_URL}/documents/${documentId}/annotations/${annotationId}/`,
    {
      method: 'DELETE',
      credentials: 'include',
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Delete annotation failed' }));
    throw new Error(error.detail || 'Delete annotation failed');
  }
};

// ============================================================================
// Template APIs
// ============================================================================

/**
 * List templates, optionally filtered by channel.
 */
export const listTemplates = async (channelId?: string | number): Promise<Template[]> => {
  const url = new URL(`${DATA_PROCESSOR_URL}/templates/`);
  if (channelId) {
    url.searchParams.set('channel_id', String(channelId));
  }

  const response = await fetch(url.toString(), {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list templates' }));
    throw new Error(error.detail || 'Failed to list templates');
  }

  const data = await response.json();
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.templates)) {
    return data.templates;
  }
  return [];
};

export type CreateTemplateRequest = {
  name: string;
  description?: string;
  channel_id: string | number;
  source_document_id?: string;
};

/**
 * Create a new template.
 */
export const createTemplate = async (template: CreateTemplateRequest): Promise<Template> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/templates/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
      ...template,
      channel_id: String(template.channel_id),
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Create template failed' }));
    throw new Error(error.detail || 'Create template failed');
  }

  return response.json();
};

/**
 * Get template details.
 */
export const getTemplate = async (templateId: string): Promise<Template> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/templates/${templateId}/`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get template' }));
    throw new Error(error.detail || 'Failed to get template');
  }

  return response.json();
};

/**
 * Delete a template.
 */
export const deleteTemplate = async (templateId: string): Promise<void> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/templates/${templateId}/`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Delete template failed' }));
    throw new Error(error.detail || 'Delete template failed');
  }
};

export type UpdateTemplateRequest = {
  name?: string;
  description?: string;
  is_active?: boolean;
};

/**
 * Update a template.
 */
export const updateTemplate = async (
  templateId: string,
  updates: UpdateTemplateRequest
): Promise<Template> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/templates/${templateId}/`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Update template failed' }));
    throw new Error(error.detail || 'Update template failed');
  }

  return response.json();
};

export type ApplyTemplateRequest = {
  template_id: string;
  use_feature_matching?: boolean;
  force_apply?: boolean;
  confidence_threshold?: number;
};

export type ApplyTemplateResponse = {
  success: boolean;
  template_id: string;
  matched_regions: MatchedRegion[];
  confidence: number;
  annotations_created: number;
};

/**
 * Apply a template to a document.
 */
export const applyTemplate = async (
  documentId: string,
  request: ApplyTemplateRequest
): Promise<ApplyTemplateResponse> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/${documentId}/apply-template/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Apply template failed' }));
    throw new Error(error.detail || 'Apply template failed');
  }

  return response.json();
};

// ============================================================================
// Export APIs
// ============================================================================

export type ExportFormat = 'json' | 'csv' | 'sql';

export type ExportResponse = {
  format: ExportFormat;
  content: string;
  filename: string;
};

/**
 * Export document data in specified format.
 */
export const exportDocument = async (
  documentId: string,
  format: ExportFormat
): Promise<ExportResponse> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/documents/${documentId}/export/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ format }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(error.detail || 'Export failed');
  }

  return response.json();
};

// ============================================================================
// Batch APIs
// ============================================================================

export type BatchJob = {
  id: string;
  channel_id: string;
  template_id?: string | null;
  created_by: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  document_ids: string[];
  processed_count: number;
  failed_count: number;
  created_at: string;
};

export type CreateBatchRequest = {
  template_id?: string;
  document_ids: string[];
};

/**
 * Create a batch processing job.
 */
export const createBatchJob = async (
  channelId: string | number,
  request: CreateBatchRequest
): Promise<BatchJob> => {
  const url = new URL(`${DATA_PROCESSOR_URL}/batch/`);
  url.searchParams.set('channel_id', String(channelId));

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Create batch job failed' }));
    throw new Error(error.detail || 'Create batch job failed');
  }

  return response.json();
};

/**
 * Get batch job status.
 */
export const getBatchJob = async (jobId: string): Promise<BatchJob> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/batch/${jobId}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get batch job' }));
    throw new Error(error.detail || 'Failed to get batch job');
  }

  return response.json();
};

/**
 * Start processing a batch job.
 */
export const processBatchJob = async (jobId: string): Promise<BatchJob> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/batch/${jobId}/process/`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Process batch job failed' }));
    throw new Error(error.detail || 'Process batch job failed');
  }

  return response.json();
};

// ============================================================================
// Health Check
// ============================================================================

/**
 * Check data processor service health.
 */
export const checkHealth = async (): Promise<{ status: string; service: string }> => {
  const response = await fetch(`${DATA_PROCESSOR_URL}/health`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Data processor service is not available');
  }

  return response.json();
};
