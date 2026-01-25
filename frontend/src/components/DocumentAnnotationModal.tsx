import { useState, useEffect, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  X,
  Download,
  Play,
  Save,
  Loader2,
  ZoomIn,
  ZoomOut,
  Move,
  CheckSquare,
} from 'lucide-react'
import {
  getDocument,
  processDocument,
  createAnnotation,
  updateAnnotation,
  deleteAnnotation,
  listTemplates,
  applyTemplate,
} from '../api/dataProcessor'
import type { Annotation, LabelType, OcrStatus } from '../types'
import { BoundingBoxCanvas } from './BoundingBoxCanvas'
import { AnnotationToolbar } from './AnnotationToolbar'
import { TemplateSaveModal } from './TemplateSaveModal'
import { ExportPanel } from './ExportPanel'
import { ValidationWorkflow } from './ValidationWorkflow'

interface DocumentAnnotationModalProps {
  documentId: string
  filename: string
  channelId: number
  onClose: () => void
  onStatusChange?: (status: OcrStatus) => void
}

// Label type colors
const LABEL_COLORS: Record<LabelType, string> = {
  header: '#3B82F6', // blue
  table: '#10B981', // green
  signature: '#8B5CF6', // purple
  date: '#F59E0B', // amber
  amount: '#EF4444', // red
  custom: '#6B7280', // gray
}

export function DocumentAnnotationModal({
  documentId,
  filename,
  channelId,
  onClose,
  onStatusChange,
}: DocumentAnnotationModalProps) {
  const queryClient = useQueryClient()

  // State
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [selectedAnnotation, setSelectedAnnotation] =
    useState<Annotation | null>(null)
  const [activeLabelType, setActiveLabelType] = useState<LabelType>('custom')
  const [labelName, setLabelName] = useState('')
  const [tool, setTool] = useState<'select' | 'draw'>('select')
  const [zoom, setZoom] = useState(1)
  const [ocrProgress, setOcrProgress] = useState<{
    stage: string
    progress: number
    message: string
  } | null>(null)
  const [extractedText, setExtractedText] = useState<string>('')
  const [showTemplateSaveModal, setShowTemplateSaveModal] = useState(false)
  const [isExportPanelOpen, setIsExportPanelOpen] = useState(false)
  const [isValidationWorkflowOpen, setIsValidationWorkflowOpen] =
    useState(false)

  // Fetch document details
  const { data: document, isLoading: isLoadingDocument } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => getDocument(documentId),
    enabled: !!documentId,
  })

  // Fetch templates
  const { data: templates } = useQuery({
    queryKey: ['templates', channelId],
    queryFn: () => listTemplates(channelId),
  })

  // Update annotations when document loads
  useEffect(() => {
    if (document?.annotations) {
      setAnnotations(document.annotations)
    }
    if (document?.ocr_result?.extracted_text) {
      setExtractedText(document.ocr_result.extracted_text)
    }
  }, [document])

  // Process OCR mutation
  const processMutation = useMutation({
    mutationFn: () => processDocument(documentId),
    onSuccess: () => {
      onStatusChange?.('processing')
    },
  })

  // Create annotation mutation
  const createAnnotationMutation = useMutation({
    mutationFn: (data: {
      label_type: LabelType
      label_name: string
      color: string
      x: number
      y: number
      width: number
      height: number
    }) => createAnnotation(documentId, data),
    onSuccess: (newAnnotation) => {
      setAnnotations((prev) => [...prev, newAnnotation])
    },
  })

  // Update annotation mutation
  const updateAnnotationMutation = useMutation({
    mutationFn: ({ id, ...updates }: { id: string } & Partial<Annotation>) =>
      updateAnnotation(documentId, id, updates),
    onSuccess: (updatedAnnotation) => {
      setAnnotations((prev) =>
        prev.map((a) =>
          a.id === updatedAnnotation.id ? updatedAnnotation : a,
        ),
      )
    },
  })

  // Delete annotation mutation
  const deleteAnnotationMutation = useMutation({
    mutationFn: (annotationId: string) =>
      deleteAnnotation(documentId, annotationId),
    onSuccess: (_, annotationId) => {
      setAnnotations((prev) => prev.filter((a) => a.id !== annotationId))
      if (selectedAnnotation?.id === annotationId) {
        setSelectedAnnotation(null)
      }
    },
  })

  // Apply template mutation
  const applyTemplateMutation = useMutation({
    mutationFn: (templateId: string) =>
      applyTemplate(documentId, { template_id: templateId }),
    onSuccess: () => {
      // Refetch document to get updated annotations
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
    },
  })

  // Handle creating annotation from canvas drawing
  const handleCreateAnnotation = useCallback(
    (box: { x: number; y: number; width: number; height: number }) => {
      const name = labelName || `${activeLabelType} ${annotations.length + 1}`
      createAnnotationMutation.mutate({
        label_type: activeLabelType,
        label_name: name,
        color: LABEL_COLORS[activeLabelType],
        ...box,
      })
      setLabelName('')
    },
    [activeLabelType, labelName, annotations.length, createAnnotationMutation],
  )

  // Handle annotation update from canvas manipulation
  const handleUpdateAnnotation = useCallback(
    (
      id: string,
      box: { x: number; y: number; width: number; height: number },
    ) => {
      updateAnnotationMutation.mutate({ id, ...box })
    },
    [updateAnnotationMutation],
  )

  // Handle delete selected annotation
  const handleDeleteSelected = useCallback(() => {
    if (selectedAnnotation) {
      deleteAnnotationMutation.mutate(selectedAnnotation.id)
    }
  }, [selectedAnnotation, deleteAnnotationMutation])

  // Zoom controls
  const handleZoomIn = () => setZoom((z) => Math.min(z * 1.2, 5))
  const handleZoomOut = () => setZoom((z) => Math.max(z / 1.2, 0.2))
  const handleResetZoom = () => setZoom(1)

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedAnnotation) {
          handleDeleteSelected()
        }
      } else if (e.key === '+' || e.key === '=') {
        handleZoomIn()
      } else if (e.key === '-') {
        handleZoomOut()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose, selectedAnnotation, handleDeleteSelected])

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/90">
      {/* Modal Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-700">
        <div className="flex items-center gap-4">
          <h2 className="text-white font-semibold">{filename}</h2>
          {ocrProgress && (
            <div className="flex items-center gap-2 text-sm">
              <Loader2 size={14} className="animate-spin text-blue-400" />
              <span className="text-gray-400">
                {ocrProgress.stage}: {ocrProgress.progress}%
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Process OCR Button */}
          <button
            onClick={() => processMutation.mutate()}
            disabled={processMutation.isPending}
            className="flex items-center gap-2 px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50 min-h-[36px]"
          >
            {processMutation.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Play size={16} />
            )}
            Run OCR
          </button>

          {/* Validation Button */}
          <button
            onClick={() => setIsValidationWorkflowOpen(true)}
            disabled={annotations.length === 0}
            className="flex items-center gap-2 px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50 min-h-[36px]"
          >
            <CheckSquare size={16} />
            Validate
          </button>

          {/* Export Button */}
          <button
            onClick={() => setIsExportPanelOpen(true)}
            disabled={annotations.length === 0}
            className="flex items-center gap-2 px-3 py-2 rounded bg-green-600 hover:bg-green-700 text-white text-sm disabled:opacity-50 min-h-[36px]"
          >
            <Download size={16} />
            Export
          </button>

          {/* Save as Template */}
          <button
            onClick={() => setShowTemplateSaveModal(true)}
            disabled={annotations.length === 0}
            className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm disabled:opacity-50 min-h-[36px]"
          >
            <Save size={16} />
            Save Template
          </button>

          {/* Close Button */}
          <button
            onClick={onClose}
            className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white min-w-[36px] min-h-[36px]"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Toolbar */}
        <AnnotationToolbar
          activeLabelType={activeLabelType}
          onLabelTypeChange={setActiveLabelType}
          tool={tool}
          onToolChange={setTool}
          labelName={labelName}
          onLabelNameChange={setLabelName}
          onDelete={handleDeleteSelected}
          hasSelection={!!selectedAnnotation}
          templates={templates || []}
          onApplyTemplate={(templateId: string) =>
            applyTemplateMutation.mutate(templateId)
          }
        />

        {/* Canvas Area */}
        <div className="flex-1 relative overflow-hidden bg-gray-950">
          {/* Zoom Controls */}
          <div className="absolute top-4 right-4 flex items-center gap-2 z-10">
            <button
              onClick={handleZoomOut}
              className="p-2 rounded bg-gray-800 hover:bg-gray-700 text-white min-w-[36px] min-h-[36px]"
              title="Zoom Out (-)"
            >
              <ZoomOut size={18} />
            </button>
            <span className="px-3 py-1 bg-gray-800 rounded text-white text-sm min-w-[60px] text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              className="p-2 rounded bg-gray-800 hover:bg-gray-700 text-white min-w-[36px] min-h-[36px]"
              title="Zoom In (+)"
            >
              <ZoomIn size={18} />
            </button>
            <button
              onClick={handleResetZoom}
              className="p-2 rounded bg-gray-800 hover:bg-gray-700 text-white min-w-[36px] min-h-[36px]"
              title="Reset Zoom"
            >
              <Move size={18} />
            </button>
          </div>

          {/* Loading State */}
          {isLoadingDocument ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 size={48} className="animate-spin text-gray-500" />
            </div>
          ) : (
            <BoundingBoxCanvas
              documentId={documentId}
              imageUrl={document?.image_url}
              annotations={annotations}
              selectedAnnotation={selectedAnnotation}
              onSelectAnnotation={setSelectedAnnotation}
              onCreateAnnotation={handleCreateAnnotation}
              onUpdateAnnotation={handleUpdateAnnotation}
              tool={tool}
              zoom={zoom}
              activeColor={LABEL_COLORS[activeLabelType]}
            />
          )}
        </div>

        {/* Right Panel - Annotations & Extracted Text */}
        <div className="w-80 bg-gray-900 border-l border-gray-700 flex flex-col">
          {/* Annotations List */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-3 border-b border-gray-700">
              <h3 className="font-medium text-white text-sm">
                Annotations ({annotations.length})
              </h3>
            </div>
            {annotations.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">
                Draw bounding boxes on the document to create annotations
              </div>
            ) : (
              <div className="p-2 space-y-2">
                {annotations.map((annotation) => (
                  <div
                    key={annotation.id}
                    onClick={() => setSelectedAnnotation(annotation)}
                    className={`p-3 rounded cursor-pointer transition-colors ${
                      selectedAnnotation?.id === annotation.id
                        ? 'bg-gray-700 ring-2 ring-blue-500'
                        : 'bg-gray-800 hover:bg-gray-750'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div
                        className="w-3 h-3 rounded"
                        style={{ backgroundColor: annotation.color }}
                      />
                      <span className="font-medium text-white text-sm">
                        {annotation.label_name}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mb-1">
                      {annotation.label_type}
                    </div>
                    {annotation.extracted_text && (
                      <div className="text-xs text-gray-300 bg-gray-900 p-2 rounded mt-2 line-clamp-2">
                        {annotation.extracted_text}
                      </div>
                    )}
                    {annotation.confidence !== null && (
                      <div className="text-xs text-gray-500 mt-1">
                        Confidence:{' '}
                        {Math.round((annotation.confidence || 0) * 100)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Extracted Text */}
          {extractedText && (
            <div className="border-t border-gray-700">
              <div className="p-3 border-b border-gray-700">
                <h3 className="font-medium text-white text-sm">
                  Extracted Text
                </h3>
              </div>
              <div className="p-3 max-h-48 overflow-y-auto">
                <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                  {extractedText}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Template Save Modal */}
      {showTemplateSaveModal && (
        <TemplateSaveModal
          isOpen={showTemplateSaveModal}
          onClose={() => setShowTemplateSaveModal(false)}
          channelId={channelId}
          annotations={annotations}
          documentWidth={document?.width || 1024}
          documentHeight={document?.height || 1024}
          sourceDocumentId={documentId}
        />
      )}

      {/* Export Panel */}
      <ExportPanel
        documentId={documentId}
        filename={filename}
        annotations={annotations}
        isOpen={isExportPanelOpen}
        onClose={() => setIsExportPanelOpen(false)}
      />

      {/* Validation Workflow */}
      <ValidationWorkflow
        documentId={documentId}
        annotations={annotations}
        onAnnotationUpdate={(updated) => {
          setAnnotations((prev) =>
            prev.map((a) => (a.id === updated.id ? updated : a)),
          )
        }}
        onComplete={() => {
          setIsValidationWorkflowOpen(false)
          // Could show a success message or trigger export
        }}
        onCancel={() => setIsValidationWorkflowOpen(false)}
        isOpen={isValidationWorkflowOpen}
      />
    </div>
  )
}
