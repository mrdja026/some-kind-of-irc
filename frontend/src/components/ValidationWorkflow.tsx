import { useState, useMemo, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Check,
  X,
  AlertTriangle,
  Edit2,
  Save,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Eye,
  Loader2,
} from 'lucide-react'
import { updateAnnotation } from '../api/dataProcessor'
import type { Annotation, LabelType } from '../types'

interface ValidationWorkflowProps {
  documentId: string
  annotations: Annotation[]
  onAnnotationUpdate: (updated: Annotation) => void
  onComplete: () => void
  onCancel: () => void
  isOpen: boolean
}

type ValidationState = 'pending' | 'valid' | 'corrected' | 'skipped'

interface FieldValidation {
  annotation: Annotation
  originalText: string
  correctedText: string
  state: ValidationState
  isEditing: boolean
}

// Label type colors
const LABEL_COLORS: Record<LabelType, string> = {
  header: '#3B82F6',
  table: '#10B981',
  signature: '#8B5CF6',
  date: '#F59E0B',
  amount: '#EF4444',
  custom: '#6B7280',
}

export function ValidationWorkflow({
  documentId,
  annotations,
  onAnnotationUpdate,
  onComplete,
  onCancel,
  isOpen,
}: ValidationWorkflowProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [validations, setValidations] = useState<FieldValidation[]>(() =>
    annotations.map((annotation) => ({
      annotation,
      originalText: annotation.extracted_text || '',
      correctedText: annotation.extracted_text || '',
      state: 'pending',
      isEditing: false,
    })),
  )

  // Update annotation mutation
  const updateMutation = useMutation({
    mutationFn: ({
      annotationId,
      text,
    }: {
      annotationId: string
      text: string
    }) =>
      updateAnnotation(documentId, annotationId, {
        extracted_text: text,
      } as Record<string, unknown>),
    onSuccess: (updated) => {
      onAnnotationUpdate(updated)
    },
  })

  // Stats
  const stats = useMemo(() => {
    const validated = validations.filter((v) => v.state !== 'pending').length
    const valid = validations.filter((v) => v.state === 'valid').length
    const corrected = validations.filter((v) => v.state === 'corrected').length
    const skipped = validations.filter((v) => v.state === 'skipped').length
    return { validated, valid, corrected, skipped, total: validations.length }
  }, [validations])

  const currentField = validations[currentIndex]

  // Navigation
  const goToNext = useCallback(() => {
    if (currentIndex < validations.length - 1) {
      setCurrentIndex(currentIndex + 1)
    }
  }, [currentIndex, validations.length])

  const goToPrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }, [currentIndex])

  // Actions
  const handleAccept = useCallback(() => {
    setValidations((prev) =>
      prev.map((v, i) => (i === currentIndex ? { ...v, state: 'valid' } : v)),
    )
    goToNext()
  }, [currentIndex, goToNext])

  const handleSkip = useCallback(() => {
    setValidations((prev) =>
      prev.map((v, i) => (i === currentIndex ? { ...v, state: 'skipped' } : v)),
    )
    goToNext()
  }, [currentIndex, goToNext])

  const startEditing = useCallback(() => {
    setValidations((prev) =>
      prev.map((v, i) => (i === currentIndex ? { ...v, isEditing: true } : v)),
    )
  }, [currentIndex])

  const cancelEditing = useCallback(() => {
    setValidations((prev) =>
      prev.map((v, i) =>
        i === currentIndex
          ? { ...v, isEditing: false, correctedText: v.originalText }
          : v,
      ),
    )
  }, [currentIndex])

  const handleTextChange = useCallback(
    (text: string) => {
      setValidations((prev) =>
        prev.map((v, i) =>
          i === currentIndex ? { ...v, correctedText: text } : v,
        ),
      )
    },
    [currentIndex],
  )

  const saveCorrection = useCallback(() => {
    const field = validations[currentIndex]
    if (field.correctedText !== field.originalText) {
      // Update via API
      updateMutation.mutate({
        annotationId: field.annotation.id,
        text: field.correctedText,
      })
      setValidations((prev) =>
        prev.map((v, i) =>
          i === currentIndex
            ? { ...v, state: 'corrected', isEditing: false }
            : v,
        ),
      )
    } else {
      setValidations((prev) =>
        prev.map((v, i) =>
          i === currentIndex ? { ...v, state: 'valid', isEditing: false } : v,
        ),
      )
    }
    goToNext()
  }, [currentIndex, validations, goToNext, updateMutation])

  const resetField = useCallback(() => {
    setValidations((prev) =>
      prev.map((v, i) =>
        i === currentIndex
          ? {
              ...v,
              state: 'pending',
              isEditing: false,
              correctedText: v.originalText,
            }
          : v,
      ),
    )
  }, [currentIndex])

  const handleCompleteValidation = useCallback(() => {
    // Check if all fields are validated
    const allValidated = validations.every((v) => v.state !== 'pending')
    if (allValidated) {
      onComplete()
    }
  }, [validations, onComplete])

  const getStateIcon = (state: ValidationState) => {
    switch (state) {
      case 'valid':
        return <Check size={14} className="text-green-500" />
      case 'corrected':
        return <Edit2 size={14} className="text-blue-500" />
      case 'skipped':
        return <AlertTriangle size={14} className="text-yellow-500" />
      default:
        return <Eye size={14} className="text-gray-500" />
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-gray-900 rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div>
            <h2 className="text-lg font-semibold text-white">
              Field Validation
            </h2>
            <p className="text-sm text-gray-400">
              Review and correct extracted text before export
            </p>
          </div>
          <button
            onClick={onCancel}
            className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors min-w-[36px] min-h-[36px]"
          >
            <X size={20} />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="px-6 py-3 border-b border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">
              Field {currentIndex + 1} of {validations.length}
            </span>
            <span className="text-sm text-gray-400">
              {stats.validated} validated ({stats.valid} accepted,{' '}
              {stats.corrected} corrected, {stats.skipped} skipped)
            </span>
          </div>
          <div className="flex gap-1">
            {validations.map((v, i) => (
              <button
                key={v.annotation.id}
                onClick={() => setCurrentIndex(i)}
                className={`flex-1 h-2 rounded transition-all ${
                  i === currentIndex ? 'ring-2 ring-blue-500' : ''
                } ${
                  v.state === 'valid'
                    ? 'bg-green-500'
                    : v.state === 'corrected'
                      ? 'bg-blue-500'
                      : v.state === 'skipped'
                        ? 'bg-yellow-500'
                        : 'bg-gray-700'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Field List Sidebar */}
          <div className="w-64 border-r border-gray-700 overflow-y-auto">
            <div className="p-3">
              <h3 className="text-xs font-medium text-gray-500 uppercase mb-2">
                All Fields
              </h3>
              <div className="space-y-1">
                {validations.map((v, i) => (
                  <button
                    key={v.annotation.id}
                    onClick={() => setCurrentIndex(i)}
                    className={`w-full flex items-center gap-2 p-2 rounded text-left transition-colors ${
                      i === currentIndex
                        ? 'bg-gray-700 ring-1 ring-blue-500'
                        : 'hover:bg-gray-800'
                    }`}
                  >
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{
                        backgroundColor: LABEL_COLORS[v.annotation.label_type],
                      }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate">
                        {v.annotation.label_name}
                      </div>
                    </div>
                    {getStateIcon(v.state)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Current Field Details */}
          <div className="flex-1 flex flex-col p-6">
            {currentField && (
              <>
                {/* Field Header */}
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-4 h-4 rounded"
                    style={{
                      backgroundColor:
                        LABEL_COLORS[currentField.annotation.label_type],
                    }}
                  />
                  <div>
                    <h3 className="text-lg font-medium text-white">
                      {currentField.annotation.label_name}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {currentField.annotation.label_type}
                    </p>
                  </div>
                  {currentField.state !== 'pending' && (
                    <div className="ml-auto flex items-center gap-2">
                      {getStateIcon(currentField.state)}
                      <span className="text-sm text-gray-400 capitalize">
                        {currentField.state}
                      </span>
                    </div>
                  )}
                </div>

                {/* Bounding Box Info */}
                <div className="mb-4 p-3 bg-gray-800 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">Position</div>
                  <div className="flex gap-4 text-sm text-gray-400">
                    <span>
                      X: {Math.round(currentField.annotation.bounding_box.x)}
                    </span>
                    <span>
                      Y: {Math.round(currentField.annotation.bounding_box.y)}
                    </span>
                    <span>
                      W:{' '}
                      {Math.round(currentField.annotation.bounding_box.width)}
                    </span>
                    <span>
                      H:{' '}
                      {Math.round(currentField.annotation.bounding_box.height)}
                    </span>
                  </div>
                </div>

                {/* Extracted Text */}
                <div className="flex-1 min-h-[200px]">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-gray-300">
                      Extracted Text
                    </label>
                    {currentField.annotation.confidence !== null &&
                      currentField.annotation.confidence !== undefined && (
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            currentField.annotation.confidence >= 0.8
                              ? 'bg-green-900 text-green-300'
                              : currentField.annotation.confidence >= 0.5
                                ? 'bg-yellow-900 text-yellow-300'
                                : 'bg-red-900 text-red-300'
                          }`}
                        >
                          {Math.round(currentField.annotation.confidence * 100)}
                          % confidence
                        </span>
                      )}
                  </div>

                  {currentField.isEditing ? (
                    <textarea
                      value={currentField.correctedText}
                      onChange={(e) => handleTextChange(e.target.value)}
                      className="w-full h-32 p-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                      autoFocus
                    />
                  ) : (
                    <div className="w-full h-32 p-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-300 font-mono text-sm overflow-auto">
                      {currentField.correctedText || (
                        <span className="text-gray-500 italic">
                          No text extracted
                        </span>
                      )}
                    </div>
                  )}

                  {/* Show diff if corrected */}
                  {currentField.state === 'corrected' &&
                    currentField.originalText !==
                      currentField.correctedText && (
                      <div className="mt-2 p-2 bg-gray-800 rounded border border-gray-700">
                        <div className="text-xs text-gray-500 mb-1">
                          Original text:
                        </div>
                        <div className="text-sm text-gray-500 line-through">
                          {currentField.originalText}
                        </div>
                      </div>
                    )}
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
                  <button
                    onClick={goToPrev}
                    disabled={currentIndex === 0}
                    className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm disabled:opacity-50 min-h-[40px]"
                  >
                    <ChevronLeft size={16} />
                    Previous
                  </button>

                  <div className="flex items-center gap-2">
                    {currentField.isEditing ? (
                      <>
                        <button
                          onClick={cancelEditing}
                          className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
                        >
                          <X size={16} />
                          Cancel
                        </button>
                        <button
                          onClick={saveCorrection}
                          disabled={updateMutation.isPending}
                          className="flex items-center gap-2 px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm min-h-[40px]"
                        >
                          {updateMutation.isPending ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : (
                            <Save size={16} />
                          )}
                          Save
                        </button>
                      </>
                    ) : (
                      <>
                        {currentField.state !== 'pending' && (
                          <button
                            onClick={resetField}
                            className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
                          >
                            <RotateCcw size={16} />
                            Reset
                          </button>
                        )}
                        <button
                          onClick={handleSkip}
                          className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
                        >
                          <AlertTriangle size={16} />
                          Skip
                        </button>
                        <button
                          onClick={startEditing}
                          className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
                        >
                          <Edit2 size={16} />
                          Edit
                        </button>
                        <button
                          onClick={handleAccept}
                          className="flex items-center gap-2 px-3 py-2 rounded bg-green-600 hover:bg-green-700 text-white text-sm min-h-[40px]"
                        >
                          <Check size={16} />
                          Accept
                        </button>
                      </>
                    )}
                  </div>

                  <button
                    onClick={goToNext}
                    disabled={currentIndex === validations.length - 1}
                    className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm disabled:opacity-50 min-h-[40px]"
                  >
                    Next
                    <ChevronRight size={16} />
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-6 py-4 border-t border-gray-700">
          <div className="flex items-center gap-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
            >
              Cancel
            </button>
            <button
              onClick={handleCompleteValidation}
              disabled={stats.validated < stats.total}
              className="flex items-center gap-2 px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50 min-h-[40px]"
            >
              <Check size={16} />
              Complete Validation ({stats.validated}/{stats.total})
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
