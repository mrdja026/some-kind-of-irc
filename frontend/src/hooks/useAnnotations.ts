import { useState, useCallback, useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Annotation, LabelType, BoundingBox } from '../types'
import {
  createAnnotation,
  updateAnnotation,
  deleteAnnotation,
  type CreateAnnotationRequest,
  type UpdateAnnotationRequest,
} from '../api/dataProcessor'

export interface UseAnnotationsOptions {
  documentId: string
  initialAnnotations?: Annotation[]
}

/**
 * Hook for managing annotations on a document
 */
export function useAnnotations({ documentId, initialAnnotations = [] }: UseAnnotationsOptions) {
  const [annotations, setAnnotations] = useState<Annotation[]>(initialAnnotations)
  const queryClient = useQueryClient()

  // Create annotation mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateAnnotationRequest) => createAnnotation(documentId, data),
    onSuccess: (newAnnotation) => {
      setAnnotations((prev) => [...prev, newAnnotation])
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

  // Update annotation mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, ...updates }: { id: string } & UpdateAnnotationRequest) =>
      updateAnnotation(documentId, id, updates),
    onSuccess: (updatedAnnotation) => {
      setAnnotations((prev) =>
        prev.map((a) => (a.id === updatedAnnotation.id ? updatedAnnotation : a)),
      )
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

  // Delete annotation mutation
  const deleteMutation = useMutation({
    mutationFn: (annotationId: string) => deleteAnnotation(documentId, annotationId),
    onSuccess: (_, annotationId) => {
      setAnnotations((prev) => prev.filter((a) => a.id !== annotationId))
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

  // Bulk update annotations
  const bulkUpdateMutation = useMutation({
    mutationFn: async (updates: Array<{ id: string } & UpdateAnnotationRequest>) => {
      const promises = updates.map(({ id, ...updateData }) =>
        updateAnnotation(documentId, id, updateData),
      )
      return Promise.all(promises)
    },
    onSuccess: (updatedAnnotations) => {
      setAnnotations((prev) =>
        prev.map((existing) => {
          const updated = updatedAnnotations.find((u) => u.id === existing.id)
          return updated || existing
        }),
      )
      // Update document cache
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations: oldData.annotations?.map((existing: Annotation) => {
            const updated = updatedAnnotations.find((u) => u.id === existing.id)
            return updated || existing
          }) || [],
        }
      })
    },
  })

  // Helper functions
  const addAnnotation = useCallback(
    (data: Omit<CreateAnnotationRequest, 'label_type' | 'label_name'> & {
      label_type: LabelType
      label_name: string
    }) => {
      createMutation.mutate(data)
    },
    [createMutation],
  )

  const updateAnnotationById = useCallback(
    (id: string, updates: UpdateAnnotationRequest) => {
      updateMutation.mutate({ id, ...updates })
    },
    [updateMutation],
  )

  const removeAnnotation = useCallback(
    (id: string) => {
      deleteMutation.mutate(id)
    },
    [deleteMutation],
  )

  const updateBoundingBox = useCallback(
    (id: string, boundingBox: BoundingBox) => {
      updateMutation.mutate({
        id,
        x: boundingBox.x,
        y: boundingBox.y,
        width: boundingBox.width,
        height: boundingBox.height,
        rotation: boundingBox.rotation,
      })
    },
    [updateMutation],
  )

  const updateExtractedText = useCallback(
    (id: string, extractedText: string) => {
      updateMutation.mutate({ id, extracted_text: extractedText } as any)
    },
    [updateMutation],
  )

  // Computed values
  const annotationsByType = useMemo(() => {
    return annotations.reduce((acc, annotation) => {
      if (!acc[annotation.label_type]) {
        acc[annotation.label_type] = []
      }
      acc[annotation.label_type].push(annotation)
      return acc
    }, {} as Record<LabelType, Annotation[]>)
  }, [annotations])

  const annotationsById = useMemo(() => {
    return annotations.reduce((acc, annotation) => {
      acc[annotation.id] = annotation
      return acc
    }, {} as Record<string, Annotation>)
  }, [annotations])

  const hasAnnotations = annotations.length > 0
  const annotationCount = annotations.length

  // Validation helpers
  const getAnnotationsWithLowConfidence = useCallback((threshold = 0.7) => {
    return annotations.filter(
      (a) => a.confidence !== null && a.confidence !== undefined && a.confidence < threshold,
    )
  }, [annotations])

  const getAnnotationsWithoutText = useCallback(() => {
    return annotations.filter((a) => !a.extracted_text || a.extracted_text.trim() === '')
  }, [annotations])

  return {
    // State
    annotations,
    setAnnotations,

    // Mutations
    createMutation,
    updateMutation,
    deleteMutation,
    bulkUpdateMutation,

    // Actions
    addAnnotation,
    updateAnnotationById,
    removeAnnotation,
    updateBoundingBox,
    updateExtractedText,

    // Computed
    annotationsByType,
    annotationsById,
    hasAnnotations,
    annotationCount,

    // Validation helpers
    getAnnotationsWithLowConfidence,
    getAnnotationsWithoutText,

    // Loading states
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
    isBulkUpdating: bulkUpdateMutation.isPending,

    // Error states
    createError: createMutation.error,
    updateError: updateMutation.error,
    deleteError: deleteMutation.error,
    bulkUpdateError: bulkUpdateMutation.error,
  }
}

/**
 * Hook for managing a single annotation's state
 */
export function useAnnotation(annotationId: string, documentId: string) {
  const queryClient = useQueryClient()

  const updateMutation = useMutation({
    mutationFn: (updates: UpdateAnnotationRequest) =>
      updateAnnotation(documentId, annotationId, updates),
    onSuccess: (updatedAnnotation) => {
      // Update in document cache
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations: oldData.annotations?.map((a: Annotation) =>
            a.id === annotationId ? updatedAnnotation : a,
          ) || [],
        }
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteAnnotation(documentId, annotationId),
    onSuccess: () => {
      // Remove from document cache
      queryClient.setQueryData(['document', documentId], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          annotations: oldData.annotations?.filter((a: Annotation) => a.id !== annotationId) || [],
        }
      })
    },
  })

  return {
    updateAnnotation: updateMutation.mutate,
    deleteAnnotation: deleteMutation.mutate,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
    updateError: updateMutation.error,
    deleteError: deleteMutation.error,
  }
}