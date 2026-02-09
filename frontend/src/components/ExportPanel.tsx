import { useState, useMemo, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Download,
  FileJson,
  FileSpreadsheet,
  Database,
  Loader2,
  Check,
  AlertTriangle,
  Copy,
  Eye,
  EyeOff,
  ChevronDown,
  ChevronRight,
  X,
} from 'lucide-react'
import { exportDocument, type ExportFormat } from '../api/dataProcessor'
import type { Annotation, LabelType } from '../types'

interface ExportPanelProps {
  documentId: string
  filename: string
  annotations: Annotation[]
  onClose: () => void
  isOpen: boolean
}

// Field validation status
type ValidationStatus = 'valid' | 'warning' | 'error'

interface ValidationResult {
  annotationId: string
  status: ValidationStatus
  message: string
}

// Export format configurations
const EXPORT_FORMATS: Array<{
  id: ExportFormat
  name: string
  description: string
  icon: React.ReactNode
  extension: string
}> = [
  {
    id: 'json',
    name: 'JSON',
    description: 'Structured data format for AI/ML pipelines',
    icon: <FileJson size={20} />,
    extension: '.json',
  },
  {
    id: 'csv',
    name: 'CSV',
    description: 'Spreadsheet-compatible format',
    icon: <FileSpreadsheet size={20} />,
    extension: '.csv',
  },
  {
    id: 'sql',
    name: 'SQL',
    description: 'Database insert statements',
    icon: <Database size={20} />,
    extension: '.sql',
  },
]

// Label type color for display
const LABEL_COLORS: Record<LabelType, string> = {
  header: '#3B82F6',
  table: '#10B981',
  signature: '#8B5CF6',
  date: '#F59E0B',
  amount: '#EF4444',
  custom: '#6B7280',
}

// Validation patterns for different label types
const VALIDATION_PATTERNS: Partial<Record<LabelType, RegExp>> = {
  date: /^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$|^\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}$/,
  amount: /^\$?\€?\£?[\d,]+\.?\d*$/,
}

function validateAnnotation(annotation: Annotation): ValidationResult {
  const result: ValidationResult = {
    annotationId: annotation.id,
    status: 'valid',
    message: '',
  }

  // Check if extracted text exists
  if (!annotation.extracted_text || annotation.extracted_text.trim() === '') {
    return {
      ...result,
      status: 'warning',
      message: 'No text extracted for this field',
    }
  }

  // Check confidence level
  if (
    annotation.confidence !== null &&
    annotation.confidence !== undefined &&
    annotation.confidence < 0.7
  ) {
    return {
      ...result,
      status: 'warning',
      message: `Low confidence (${Math.round((annotation.confidence || 0) * 100)}%)`,
    }
  }

  // Check format validation for specific types
  const pattern = VALIDATION_PATTERNS[annotation.label_type]
  if (pattern && !pattern.test(annotation.extracted_text.trim())) {
    return {
      ...result,
      status: 'warning',
      message: `Format may not match expected ${annotation.label_type} pattern`,
    }
  }

  return {
    ...result,
    status: 'valid',
    message: 'Validation passed',
  }
}

export function ExportPanel({
  documentId,
  filename,
  annotations,
  onClose,
  isOpen,
}: ExportPanelProps) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('json')
  const [showPreview, setShowPreview] = useState(true)
  const [previewContent, setPreviewContent] = useState<string | null>(null)
  const [expandedAnnotations, setExpandedAnnotations] = useState<Set<string>>(
    new Set(),
  )
  const [copiedToClipboard, setCopiedToClipboard] = useState(false)

  // Validate all annotations
  const validationResults = useMemo(() => {
    return annotations.map(validateAnnotation)
  }, [annotations])

  // Summary stats
  const validationSummary = useMemo(() => {
    const valid = validationResults.filter((r) => r.status === 'valid').length
    const warnings = validationResults.filter(
      (r) => r.status === 'warning',
    ).length
    const errors = validationResults.filter((r) => r.status === 'error').length
    return { valid, warnings, errors }
  }, [validationResults])

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: (format: ExportFormat) => exportDocument(documentId, format),
    onSuccess: (data) => {
      // Set preview content
      setPreviewContent(data.content)

      // Download file
      const blob = new Blob([data.content], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = window.document.createElement('a')
      a.href = url
      a.download = data.filename
      a.click()
      URL.revokeObjectURL(url)
    },
  })

  // Preview mutation (doesn't download)
  const previewMutation = useMutation({
    mutationFn: (format: ExportFormat) => exportDocument(documentId, format),
    onSuccess: (data) => {
      setPreviewContent(data.content)
    },
  })

  const handleExport = useCallback(() => {
    exportMutation.mutate(selectedFormat)
  }, [exportMutation, selectedFormat])

  const handlePreview = useCallback(() => {
    previewMutation.mutate(selectedFormat)
  }, [previewMutation, selectedFormat])

  const handleCopyToClipboard = useCallback(async () => {
    if (previewContent) {
      await navigator.clipboard.writeText(previewContent)
      setCopiedToClipboard(true)
      setTimeout(() => setCopiedToClipboard(false), 2000)
    }
  }, [previewContent])

  const toggleAnnotationExpand = useCallback((id: string) => {
    setExpandedAnnotations((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const getValidationIcon = (status: ValidationStatus) => {
    switch (status) {
      case 'valid':
        return <Check size={14} className="text-green-500" />
      case 'warning':
        return <AlertTriangle size={14} className="text-yellow-500" />
      case 'error':
        return <AlertTriangle size={14} className="text-red-500" />
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-gray-900 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div>
            <h2 className="text-lg font-semibold text-white">Export Data</h2>
            <p className="text-sm text-gray-400">{filename}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors min-w-[36px] min-h-[36px]"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex">
          {/* Left Panel - Format Selection & Validation */}
          <div className="w-80 border-r border-gray-700 flex flex-col">
            {/* Format Selection */}
            <div className="p-4 border-b border-gray-700">
              <h3 className="text-sm font-medium text-white mb-3">
                Export Format
              </h3>
              <div className="space-y-2">
                {EXPORT_FORMATS.map((format) => (
                  <button
                    key={format.id}
                    onClick={() => {
                      setSelectedFormat(format.id)
                      setPreviewContent(null)
                    }}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg transition-colors ${
                      selectedFormat === format.id
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    {format.icon}
                    <div className="text-left">
                      <div className="font-medium">{format.name}</div>
                      <div
                        className={`text-xs ${selectedFormat === format.id ? 'text-blue-200' : 'text-gray-500'}`}
                      >
                        {format.description}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Validation Summary */}
            <div className="p-4 border-b border-gray-700">
              <h3 className="text-sm font-medium text-white mb-3">
                Validation Summary
              </h3>
              <div className="flex gap-4">
                <div className="flex items-center gap-2">
                  <Check size={16} className="text-green-500" />
                  <span className="text-sm text-gray-300">
                    {validationSummary.valid} valid
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <AlertTriangle size={16} className="text-yellow-500" />
                  <span className="text-sm text-gray-300">
                    {validationSummary.warnings} warnings
                  </span>
                </div>
              </div>
            </div>

            {/* Fields List */}
            <div className="flex-1 overflow-y-auto p-4">
              <h3 className="text-sm font-medium text-white mb-3">
                Fields to Export ({annotations.length})
              </h3>
              <div className="space-y-2">
                {annotations.map((annotation, index) => {
                  const validation = validationResults[index]
                  const isExpanded = expandedAnnotations.has(annotation.id)

                  return (
                    <div
                      key={annotation.id}
                      className="bg-gray-800 rounded-lg overflow-hidden"
                    >
                      <button
                        onClick={() => toggleAnnotationExpand(annotation.id)}
                        className="w-full flex items-center gap-3 p-3 text-left hover:bg-gray-750 transition-colors"
                      >
                        {isExpanded ? (
                          <ChevronDown size={16} className="text-gray-400" />
                        ) : (
                          <ChevronRight size={16} className="text-gray-400" />
                        )}
                        <div
                          className="w-3 h-3 rounded"
                          style={{
                            backgroundColor:
                              LABEL_COLORS[annotation.label_type],
                          }}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-white text-sm truncate">
                            {annotation.label_name}
                          </div>
                          <div className="text-xs text-gray-500">
                            {annotation.label_type}
                          </div>
                        </div>
                        {getValidationIcon(validation.status)}
                      </button>

                      {isExpanded && (
                        <div className="px-3 pb-3 space-y-2">
                          {/* Extracted Text */}
                          <div className="bg-gray-900 rounded p-2">
                            <div className="text-xs text-gray-500 mb-1">
                              Extracted Text
                            </div>
                            <div className="text-sm text-gray-300 font-mono">
                              {annotation.extracted_text || (
                                <span className="text-gray-500 italic">
                                  No text
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Confidence */}
                          {annotation.confidence !== null && (
                            <div className="flex items-center gap-2">
                              <div className="text-xs text-gray-500">
                                Confidence:
                              </div>
                              <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                                <div
                                  className={`h-full transition-all ${
                                    (annotation.confidence || 0) >= 0.8
                                      ? 'bg-green-500'
                                      : (annotation.confidence || 0) >= 0.5
                                        ? 'bg-yellow-500'
                                        : 'bg-red-500'
                                  }`}
                                  style={{
                                    width: `${(annotation.confidence || 0) * 100}%`,
                                  }}
                                />
                              </div>
                              <div className="text-xs text-gray-400">
                                {Math.round((annotation.confidence || 0) * 100)}
                                %
                              </div>
                            </div>
                          )}

                          {/* Validation Message */}
                          {validation.status !== 'valid' && (
                            <div
                              className={`text-xs flex items-center gap-2 ${
                                validation.status === 'warning'
                                  ? 'text-yellow-400'
                                  : 'text-red-400'
                              }`}
                            >
                              <AlertTriangle size={12} />
                              {validation.message}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Right Panel - Preview */}
          <div className="flex-1 flex flex-col">
            {/* Preview Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className="flex items-center gap-2 text-sm text-gray-300 hover:text-white"
                >
                  {showPreview ? <Eye size={16} /> : <EyeOff size={16} />}
                  {showPreview ? 'Hide Preview' : 'Show Preview'}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handlePreview}
                  disabled={
                    previewMutation.isPending || annotations.length === 0
                  }
                  className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm disabled:opacity-50 min-h-[36px]"
                >
                  {previewMutation.isPending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Eye size={16} />
                  )}
                  Preview
                </button>
                {previewContent && (
                  <button
                    onClick={handleCopyToClipboard}
                    className="flex items-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[36px]"
                  >
                    {copiedToClipboard ? (
                      <Check size={16} className="text-green-500" />
                    ) : (
                      <Copy size={16} />
                    )}
                    {copiedToClipboard ? 'Copied!' : 'Copy'}
                  </button>
                )}
              </div>
            </div>

            {/* Preview Content */}
            <div className="flex-1 overflow-hidden">
              {showPreview ? (
                previewContent ? (
                  <div className="h-full overflow-auto p-4">
                    <pre className="text-sm text-gray-300 font-mono whitespace-pre-wrap break-words bg-gray-950 p-4 rounded-lg">
                      {previewContent}
                    </pre>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-gray-500">
                    <Eye size={48} className="mb-4 opacity-50" />
                    <p className="text-sm">
                      Click "Preview" to see the export output
                    </p>
                  </div>
                )
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                  <EyeOff size={48} className="mb-4 opacity-50" />
                  <p className="text-sm">Preview is hidden</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-700">
          <div className="text-sm text-gray-400">
            {annotations.length} field{annotations.length !== 1 ? 's' : ''} will
            be exported
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={exportMutation.isPending || annotations.length === 0}
              className="flex items-center gap-2 px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50 min-h-[40px]"
            >
              {exportMutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Download size={16} />
              )}
              Export as{' '}
              {EXPORT_FORMATS.find((f) => f.id === selectedFormat)?.name}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
