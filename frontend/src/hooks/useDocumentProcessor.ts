import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Document, OcrStatus } from '../types'
import {
  getDocument,
  uploadDocument,
  deleteDocument,
  processDocument,
  extractText,
  type DocumentUploadResponse,
} from '../api/dataProcessor'

export interface UseDocumentProcessorOptions {
  documentId?: string
  channelId?: number
  enabled?: boolean
}

/**
 * Hook for managing document processor state and operations
 */
export function useDocumentProcessor(options: UseDocumentProcessorOptions = {}) {
  const { documentId, channelId, enabled = true } = options
  const queryClient = useQueryClient()

  // Query for fetching document details
  const documentQuery = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => getDocument(documentId!),
    enabled: enabled && !!documentId,
    staleTime: 30000, // 30 seconds
  })

  // Upload document mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!channelId) throw new Error('Channel ID is required for upload')
      return uploadDocument(file, channelId)
    },
    onSuccess: (data) => {
      // Invalidate and refetch document queries
      queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
      // Optionally prefetch the new document
      queryClient.prefetchQuery({
        queryKey: ['document', data.id],
        queryFn: () => getDocument(data.id),
        staleTime: 30000,
      })
    },
  })

  // Delete document mutation
  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(docId),
    onSuccess: (_, docId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: ['document', docId] })
      // Invalidate document lists
      queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
    },
  })

  // Process document mutation (trigger OCR)
  const processMutation = useMutation({
    mutationFn: (docId: string) => processDocument(docId),
    onSuccess: (_, docId) => {
      // Invalidate document to get updated status
      queryClient.invalidateQueries({ queryKey: ['document', docId] })
    },
  })

  // Extract text mutation
  const extractTextMutation = useMutation({
    mutationFn: (docId: string) => extractText(docId),
    onSuccess: (annotations, docId) => {
      // Update document annotations in cache
      queryClient.setQueryData(['document', docId], (oldData: Document | undefined) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations,
        }
      })
    },
  })

  // Computed values
  const document = documentQuery.data
  const isLoading = documentQuery.isLoading
  const error = documentQuery.error
  const ocrStatus = document?.ocr_status || 'pending'
  const hasAnnotations = document?.annotations && document.annotations.length > 0
  const hasExtractedText = document?.ocr_result?.extracted_text

  // Helper functions
  const refetch = () => {
    documentQuery.refetch()
  }

  const invalidate = () => {
    if (documentId) {
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
    }
  }

  const updateDocumentStatus = (status: OcrStatus) => {
    if (documentId && document) {
      queryClient.setQueryData(['document', documentId], {
        ...document,
        ocr_status: status,
      })
    }
  }

  return {
    // Data
    document,
    isLoading,
    error,
    ocrStatus,
    hasAnnotations,
    hasExtractedText,

    // Queries
    documentQuery,

    // Mutations
    uploadMutation,
    deleteMutation,
    processMutation,
    extractTextMutation,

    // Actions
    refetch,
    invalidate,
    updateDocumentStatus,

    // Computed
    isProcessing: ocrStatus === 'processing',
    isCompleted: ocrStatus === 'completed',
    isFailed: ocrStatus === 'failed',
    canProcess: ocrStatus === 'pending' || ocrStatus === 'failed',
    canExport: ocrStatus === 'completed' && hasAnnotations,
  }
}

/**
 * Hook for managing multiple documents in a channel
 */
export function useDocuments(channelId?: number, enabled = true) {
  // Note: This would need a listDocuments API endpoint
  // For now, we'll return a placeholder structure
  const queryClient = useQueryClient()

  // Placeholder - would need API endpoint
  const documentsQuery = useQuery({
    queryKey: ['documents', channelId],
    queryFn: async () => {
      // This would call a listDocuments API
      return [] as Document[]
    },
    enabled: enabled && !!channelId,
  })

  const invalidateDocuments = () => {
    queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
  }

  return {
    documents: documentsQuery.data || [],
    isLoading: documentsQuery.isLoading,
    error: documentsQuery.error,
    refetch: documentsQuery.refetch,
    invalidate: invalidateDocuments,
  }
}