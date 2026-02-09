import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Annotation, Template } from '../types'
import {
  // Document operations
  uploadDocument,
  deleteDocument,
  processDocument,
  extractText,
  type DocumentUploadResponse,

  // Annotation operations
  createAnnotation,
  updateAnnotation,
  deleteAnnotation,
  type CreateAnnotationRequest,
  type UpdateAnnotationRequest,

  // Template operations
  createTemplate,
  updateTemplate,
  deleteTemplate,
  applyTemplate,
  type CreateTemplateRequest,
  type UpdateTemplateRequest,
  type ApplyTemplateRequest,
  type ApplyTemplateResponse,

  // Export operations
  exportDocument,
  type ExportFormat,
  type ExportResponse,

  // Batch operations
  createBatchJob,
  processBatchJob,
  getBatchJob,
  type CreateBatchRequest,
  type BatchJob,
} from '../api/dataProcessor'

/**
 * Hook providing all data-processor mutations with proper cache invalidation
 */
export function useDataProcessorMutations() {
  const queryClient = useQueryClient()

  // ============================================================================
  // Document Mutations
  // ============================================================================

  const uploadDocumentMutation = useMutation({
    mutationFn: ({ file, channelId }: { file: File; channelId: number }) =>
      uploadDocument(file, channelId),
    onSuccess: (data, { channelId }) => {
      // Invalidate documents list for the channel
      queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
      // Prefetch the new document
      queryClient.prefetchQuery({
        queryKey: ['document', data.id],
        queryFn: () => import('../api/dataProcessor').then(m => m.getDocument(data.id)),
        staleTime: 30000,
      })
    },
  })

  const deleteDocumentMutation = useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: (_, documentId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: ['document', documentId] })
      // Invalidate any documents lists
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })

  const processDocumentMutation = useMutation({
    mutationFn: (documentId: string) => processDocument(documentId),
    onSuccess: (_, documentId) => {
      // Invalidate document to get updated status
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
    },
  })

  const extractTextMutation = useMutation({
    mutationFn: (documentId: string) => extractText(documentId),
    onSuccess: (annotations, documentId) => {
      // Update document annotations in cache
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations,
        }
      })
    },
  })

  // ============================================================================
  // Annotation Mutations
  // ============================================================================

  const createAnnotationMutation = useMutation({
    mutationFn: ({ documentId, data }: { documentId: string; data: CreateAnnotationRequest }) =>
      createAnnotation(documentId, data),
    onSuccess: (newAnnotation, { documentId }) => {
      // Update document cache
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations: [...(oldData.annotations || []), newAnnotation],
        }
      })
    },
  })

  const updateAnnotationMutation = useMutation({
    mutationFn: ({
      documentId,
      annotationId,
      updates
    }: {
      documentId: string
      annotationId: string
      updates: UpdateAnnotationRequest
    }) =>
      updateAnnotation(documentId, annotationId, updates),
    onSuccess: (updatedAnnotation, { documentId }) => {
      // Update document cache
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations: oldData.annotations?.map((a: Annotation) =>
            a.id === updatedAnnotation.id ? updatedAnnotation : a,
          ) || [],
        }
      })
    },
  })

  const deleteAnnotationMutation = useMutation({
    mutationFn: ({ documentId, annotationId }: { documentId: string; annotationId: string }) =>
      deleteAnnotation(documentId, annotationId),
    onSuccess: (_, { documentId, annotationId }) => {
      // Update document cache
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations: oldData.annotations?.filter((a: Annotation) => a.id !== annotationId) || [],
        }
      })
    },
  })

  // ============================================================================
  // Template Mutations
  // ============================================================================

  const createTemplateMutation = useMutation({
    mutationFn: (templateData: CreateTemplateRequest) => createTemplate(templateData),
    onSuccess: (newTemplate, templateData) => {
      // Add to templates cache
      queryClient.setQueryData(['templates', templateData.channel_id], (oldData: Template[] | undefined) => {
        return oldData ? [...oldData, newTemplate] : [newTemplate]
      })
      // Cache individual template
      queryClient.setQueryData(['template', newTemplate.id], newTemplate)
    },
  })

  const updateTemplateMutation = useMutation({
    mutationFn: ({ templateId, updates }: { templateId: string; updates: UpdateTemplateRequest }) =>
      updateTemplate(templateId, updates),
    onSuccess: (updatedTemplate, { templateId }) => {
      // Update in templates list cache
      queryClient.invalidateQueries({ queryKey: ['templates'], exact: false })
      // Update individual template cache
      queryClient.setQueryData(['template', templateId], updatedTemplate)
    },
  })

  const deleteTemplateMutation = useMutation({
    mutationFn: (templateId: string) => deleteTemplate(templateId),
    onSuccess: (_, templateId) => {
      // Remove from templates list cache
      queryClient.invalidateQueries({ queryKey: ['templates'], exact: false })
      // Remove individual template cache
      queryClient.removeQueries({ queryKey: ['template', templateId] })
    },
  })

  const applyTemplateMutation = useMutation({
    mutationFn: ({ documentId, request }: { documentId: string; request: ApplyTemplateRequest }) =>
      applyTemplate(documentId, request),
    onSuccess: (_, { documentId }) => {
      // Invalidate document to get updated annotations
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
    },
  })

  // ============================================================================
  // Export Mutations
  // ============================================================================

  const exportDocumentMutation = useMutation({
    mutationFn: ({ documentId, format }: { documentId: string; format: ExportFormat }) =>
      exportDocument(documentId, format),
    // Note: No cache updates needed for export as it triggers download
  })

  // ============================================================================
  // Batch Mutations
  // ============================================================================

  const createBatchJobMutation = useMutation({
    mutationFn: ({ channelId, request }: { channelId: number; request: CreateBatchRequest }) =>
      createBatchJob(channelId, request),
    onSuccess: (batchJob) => {
      // Cache the batch job
      queryClient.setQueryData(['batchJob', batchJob.id], batchJob)
    },
  })

  const processBatchJobMutation = useMutation({
    mutationFn: (jobId: string) => processBatchJob(jobId),
    onSuccess: (_, jobId) => {
      // Invalidate batch job to get updated status
      queryClient.invalidateQueries({ queryKey: ['batchJob', jobId] })
    },
  })

  const getBatchJobMutation = useMutation({
    mutationFn: (jobId: string) => getBatchJob(jobId),
    onSuccess: (batchJob) => {
      // Update batch job cache
      queryClient.setQueryData(['batchJob', batchJob.id], batchJob)
    },
  })

  return {
    // Document mutations
    uploadDocument: uploadDocumentMutation,
    deleteDocument: deleteDocumentMutation,
    processDocument: processDocumentMutation,
    extractText: extractTextMutation,

    // Annotation mutations
    createAnnotation: createAnnotationMutation,
    updateAnnotation: updateAnnotationMutation,
    deleteAnnotation: deleteAnnotationMutation,

    // Template mutations
    createTemplate: createTemplateMutation,
    updateTemplate: updateTemplateMutation,
    deleteTemplate: deleteTemplateMutation,
    applyTemplate: applyTemplateMutation,

    // Export mutations
    exportDocument: exportDocumentMutation,

    // Batch mutations
    createBatchJob: createBatchJobMutation,
    processBatchJob: processBatchJobMutation,
    getBatchJob: getBatchJobMutation,

    // Loading states
    isUploading: uploadDocumentMutation.isPending,
    isProcessing: processDocumentMutation.isPending,
    isCreatingAnnotation: createAnnotationMutation.isPending,
    isUpdatingAnnotation: updateAnnotationMutation.isPending,
    isDeletingAnnotation: deleteAnnotationMutation.isPending,
    isCreatingTemplate: createTemplateMutation.isPending,
    isUpdatingTemplate: updateTemplateMutation.isPending,
    isDeletingTemplate: deleteTemplateMutation.isPending,
    isApplyingTemplate: applyTemplateMutation.isPending,
    isExporting: exportDocumentMutation.isPending,
    isCreatingBatch: createBatchJobMutation.isPending,
    isProcessingBatch: processBatchJobMutation.isPending,

    // Error states
    uploadError: uploadDocumentMutation.error,
    processError: processDocumentMutation.error,
    createAnnotationError: createAnnotationMutation.error,
    updateAnnotationError: updateAnnotationMutation.error,
    deleteAnnotationError: deleteAnnotationMutation.error,
    createTemplateError: createTemplateMutation.error,
    updateTemplateError: updateTemplateMutation.error,
    deleteTemplateError: deleteTemplateMutation.error,
    applyTemplateError: applyTemplateMutation.error,
    exportError: exportDocumentMutation.error,
    createBatchError: createBatchJobMutation.error,
    processBatchError: processBatchJobMutation.error,
  }
}

/**
 * Hook for optimistic updates on common operations
 */
export function useOptimisticDataProcessorMutations() {
  const queryClient = useQueryClient()

  const optimisticAnnotationUpdate = useMutation({
    mutationFn: async ({
      documentId,
      annotationId,
      updates
    }: {
      documentId: string
      annotationId: string
      updates: UpdateAnnotationRequest
    }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['document', documentId] })

      // Snapshot previous value
      const previousDocument = queryClient.getQueryData(['document', documentId]) as any

      // Optimistically update
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations: oldData.annotations?.map((a: Annotation) =>
            a.id === annotationId ? { ...a, ...updates } : a,
          ) || [],
        }
      })

      try {
        return await updateAnnotation(documentId, annotationId, updates)
      } catch (error) {
        // Revert on error
        queryClient.setQueryData(['document', documentId], previousDocument)
        throw error
      }
    },
  })

  const optimisticTemplateToggle = useMutation({
    mutationFn: async (templateId: string) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['template', templateId] })
      await queryClient.cancelQueries({ queryKey: ['templates'], exact: false })

      // Snapshot previous values
      const previousTemplate = queryClient.getQueryData(['template', templateId]) as Template
      const previousTemplates = queryClient.getQueryData(['templates']) as Template[]

      // Optimistically update
      const newActiveState = !previousTemplate?.is_active
      const updatedTemplate = { ...previousTemplate, is_active: newActiveState }
      const updatedTemplates = previousTemplates?.map((t) =>
        t.id === templateId ? updatedTemplate : t,
      )

      queryClient.setQueryData(['template', templateId], updatedTemplate)
      queryClient.setQueryData(['templates'], updatedTemplates)

      try {
        return await updateTemplate(templateId, { is_active: newActiveState })
      } catch (error) {
        // Revert on error
        queryClient.setQueryData(['template', templateId], previousTemplate)
        queryClient.setQueryData(['templates'], previousTemplates)
        throw error
      }
    },
  })

  return {
    optimisticAnnotationUpdate,
    optimisticTemplateToggle,
  }
}