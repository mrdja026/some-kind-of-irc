import { useEffect, useRef, useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type {
  DataProcessorEvent,
  DocumentUploadedEvent,
  OcrProgressEvent,
  OcrCompleteEvent,
  TemplateAppliedEvent,
  OcrStatus,
} from '../types'

export interface OcrProgressState {
  documentId: string
  stage: 'preprocessing' | 'detection' | 'extraction' | 'mapping' | 'complete'
  progress: number
  message: string
  isActive: boolean
  error?: string
}

export interface UseOcrProgressOptions {
  documentId?: string
  onProgress?: (state: OcrProgressState) => void
  onComplete?: (documentId: string, result: OcrCompleteEvent) => void
  onError?: (documentId: string, error: string) => void
}

/**
 * Hook for handling OCR progress events via WebSocket
 */
export function useOcrProgress(options: UseOcrProgressOptions = {}) {
  const { documentId, onProgress, onComplete, onError } = options
  const queryClient = useQueryClient()
  const [progressStates, setProgressStates] = useState<Map<string, OcrProgressState>>(new Map())
  const [isSubscribed, setIsSubscribed] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Get current progress state for a document
  const getProgressState = useCallback((docId: string): OcrProgressState | null => {
    return progressStates.get(docId) || null
  }, [progressStates])

  // Update progress state
  const updateProgressState = useCallback((documentId: string, updates: Partial<OcrProgressState>) => {
    setProgressStates((prev) => {
      const current = prev.get(documentId) || {
        documentId,
        stage: 'preprocessing',
        progress: 0,
        message: '',
        isActive: false,
      }

      const updated = { ...current, ...updates }
      const next = new Map(prev)
      next.set(documentId, updated)

      // Call progress callback
      onProgress?.(updated)

      return next
    })
  }, [onProgress])

  // Clear progress state
  const clearProgressState = useCallback((documentId: string) => {
    setProgressStates((prev) => {
      const next = new Map(prev)
      next.delete(documentId)
      return next
    })
  }, [])

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    try {
      const data: DataProcessorEvent = JSON.parse(event.data)

      switch (data.type) {
        case 'document_uploaded':
          handleDocumentUploaded(data)
          break
        case 'ocr_progress':
          handleOcrProgress(data)
          break
        case 'ocr_complete':
          handleOcrComplete(data)
          break
        case 'template_applied':
          handleTemplateApplied(data)
          break
        default:
          console.warn('Unknown data processor event type:', (data as any).type)
      }
    } catch (error) {
      console.error('Error parsing data processor WebSocket message:', error)
    }
  }, [])

  // Event handlers
  const handleDocumentUploaded = useCallback((event: DocumentUploadedEvent) => {
    // Update document status in cache
    queryClient.setQueryData(['document', event.document_id], (oldData: any) => {
      if (!oldData) return oldData
      return {
        ...oldData,
        ocr_status: 'pending' as OcrStatus,
      }
    })

    // Initialize progress state
    updateProgressState(event.document_id, {
      stage: 'preprocessing',
      progress: 0,
      message: 'Document uploaded, ready for processing',
      isActive: false,
    })
  }, [queryClient, updateProgressState])

  const handleOcrProgress = useCallback((event: OcrProgressEvent) => {
    updateProgressState(event.document_id, {
      stage: event.stage,
      progress: event.progress,
      message: event.message,
      isActive: true,
    })

    // Update document status based on progress
    if (event.progress >= 100) {
      queryClient.setQueryData(['document', event.document_id], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          ocr_status: 'completed' as OcrStatus,
        }
      })
    } else {
      queryClient.setQueryData(['document', event.document_id], (oldData: any) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          ocr_status: 'processing' as OcrStatus,
        }
      })
    }
  }, [updateProgressState, queryClient])

  const handleOcrComplete = useCallback((event: OcrCompleteEvent) => {
    // Update progress state
    updateProgressState(event.document_id, {
      stage: 'complete',
      progress: 100,
      message: 'OCR processing completed',
      isActive: false,
    })

    // Update document in cache with OCR results
    queryClient.setQueryData(['document', event.document_id], (oldData: any) => {
      if (!oldData) return oldData
      return {
        ...oldData,
        ocr_status: 'completed' as OcrStatus,
        ocr_result: {
          detected_regions: event.detected_regions,
          extracted_text: event.extracted_text,
        },
      }
    })

    // Call completion callback
    onComplete?.(event.document_id, event)

    // Clear progress state after a delay
    setTimeout(() => {
      clearProgressState(event.document_id)
    }, 3000)
  }, [updateProgressState, queryClient, onComplete, clearProgressState])

  const handleTemplateApplied = useCallback((event: TemplateAppliedEvent) => {
    // Update document with template-matched annotations
    queryClient.setQueryData(['document', event.document_id], (oldData: any) => {
      if (!oldData) return oldData

      // Add template-matched annotations
      const newAnnotations = event.matched_regions.map((region) => ({
        id: `template-${region.label_id}-${Date.now()}`,
        document_id: event.document_id,
        label_type: region.label_type,
        label_name: region.label_name,
        color: '#3B82F6', // Default blue for template matches
        bounding_box: {
          x: region.x,
          y: region.y,
          width: region.width,
          height: region.height,
          rotation: 0,
        },
        extracted_text: region.matched_text || null,
        confidence: region.confidence,
        created_at: new Date().toISOString(),
      }))

      return {
        ...oldData,
        annotations: [...(oldData.annotations || []), ...newAnnotations],
      }
    })

    // Show template application message
    updateProgressState(event.document_id, {
      stage: 'mapping',
      progress: 100,
      message: `Template "${event.template_id}" applied with ${event.confidence * 100}% confidence`,
      isActive: false,
    })

    // Clear after delay
    setTimeout(() => {
      clearProgressState(event.document_id)
    }, 3000)
  }, [queryClient, updateProgressState, clearProgressState])

  // WebSocket connection management
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    // Use the same WebSocket URL pattern as the main chat socket
    const wsUrl = typeof window === 'undefined'
      ? (import.meta.env.VITE_WS_URL || 'ws://backend:8002')
      : (() => {
          const isSecure = window.location.protocol === 'https:'
          const proto = isSecure ? 'wss:' : 'ws:'
          const host = window.location.host
          return `${proto}//${host}`
        })()

    const socket = new WebSocket(`${wsUrl}/ws/data-processor`)
    wsRef.current = socket

    socket.onopen = () => {
      console.log('Data processor WebSocket connected')
      setIsSubscribed(true)
    }

    socket.onclose = () => {
      console.log('Data processor WebSocket disconnected')
      setIsSubscribed(false)

      // Attempt to reconnect after delay
      reconnectTimeoutRef.current = setTimeout(() => {
        connectWebSocket()
      }, 5000)
    }

    socket.onerror = (error) => {
      console.error('Data processor WebSocket error:', error)
      onError?.(documentId || '', 'WebSocket connection error')
    }

    socket.onmessage = handleWebSocketMessage
  }, [handleWebSocketMessage, onError, documentId])

  const disconnectWebSocket = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsSubscribed(false)
  }, [])

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connectWebSocket()
    return () => {
      disconnectWebSocket()
    }
  }, [connectWebSocket, disconnectWebSocket])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [])

  return {
    // State
    progressStates,
    isSubscribed,

    // Getters
    getProgressState,

    // Actions
    updateProgressState,
    clearProgressState,

    // WebSocket
    connectWebSocket,
    disconnectWebSocket,

    // Computed
    activeProgressStates: Array.from(progressStates.values()).filter(state => state.isActive),
    hasActiveProgress: Array.from(progressStates.values()).some(state => state.isActive),
  }
}

/**
 * Hook for tracking OCR progress for a specific document
 */
export function useDocumentOcrProgress(documentId: string) {
  const [progress, setProgress] = useState<OcrProgressState | null>(null)

  const { getProgressState, updateProgressState } = useOcrProgress({
    documentId,
    onProgress: setProgress,
  })

  useEffect(() => {
    const currentProgress = getProgressState(documentId)
    if (currentProgress) {
      setProgress(currentProgress)
    }
  }, [documentId, getProgressState])

  return {
    progress,
    isProcessing: progress?.isActive ?? false,
    stage: progress?.stage ?? 'preprocessing',
    progressPercent: progress?.progress ?? 0,
    message: progress?.message ?? '',
  }
}