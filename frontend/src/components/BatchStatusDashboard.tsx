import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  X,
  Play,
  Pause,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader2,
  FileImage,
  ChevronDown,
  ChevronRight,
  Download,
  Trash2,
} from 'lucide-react'
import {
  getBatchJob,
  processBatchJob,
  createBatchJob,
  exportDocument,
  type BatchJob,
  type ExportFormat,
} from '../api/dataProcessor'
import type { Template } from '../types'

interface BatchStatusDashboardProps {
  channelId: number
  isOpen: boolean
  onClose: () => void
  documentIds: string[]
  templates: Template[]
  onBatchComplete?: () => void
}

type BatchStatus = 'pending' | 'processing' | 'completed' | 'failed'

const STATUS_CONFIG: Record<
  BatchStatus,
  { icon: React.ReactNode; color: string; label: string }
> = {
  pending: {
    icon: <Clock size={16} />,
    color: 'text-yellow-500',
    label: 'Pending',
  },
  processing: {
    icon: <Loader2 size={16} className="animate-spin" />,
    color: 'text-blue-500',
    label: 'Processing',
  },
  completed: {
    icon: <CheckCircle size={16} />,
    color: 'text-green-500',
    label: 'Completed',
  },
  failed: {
    icon: <AlertCircle size={16} />,
    color: 'text-red-500',
    label: 'Failed',
  },
}

interface DocumentStatus {
  id: string
  filename?: string
  status: BatchStatus
  result?: string
}

export function BatchStatusDashboard({
  channelId,
  isOpen,
  onClose,
  documentIds,
  templates,
  onBatchComplete,
}: BatchStatusDashboardProps) {
  const queryClient = useQueryClient()
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [selectedDocuments, setSelectedDocuments] =
    useState<string[]>(documentIds)
  const [exportFormat, setExportFormat] = useState<ExportFormat>('json')
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['config', 'progress']),
  )

  // Fetch batch job status
  const {
    data: batchJob,
    refetch: refetchBatchJob,
    isLoading: isLoadingBatch,
  } = useQuery({
    queryKey: ['batchJob', activeBatchId],
    queryFn: () => (activeBatchId ? getBatchJob(activeBatchId) : null),
    enabled: !!activeBatchId,
    refetchInterval: (query) => {
      const data = query.state.data as BatchJob | null
      // Poll while processing
      if (data?.status === 'processing') {
        return 2000
      }
      return false
    },
  })

  // Create batch job mutation
  const createBatchMutation = useMutation({
    mutationFn: () =>
      createBatchJob(channelId, {
        template_id: selectedTemplateId || undefined,
        document_ids: selectedDocuments,
      }),
    onSuccess: (job) => {
      setActiveBatchId(job.id)
    },
  })

  // Start processing mutation
  const processBatchMutation = useMutation({
    mutationFn: (jobId: string) => processBatchJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batchJob', activeBatchId] })
    },
  })

  // Export all mutation
  const exportAllMutation = useMutation({
    mutationFn: async () => {
      if (!batchJob) return

      const exports = await Promise.all(
        batchJob.document_ids.map((docId) =>
          exportDocument(docId, exportFormat),
        ),
      )

      // Combine exports into a zip-like download
      const combined = exports.map((e) => e.content).join('\n\n---\n\n')
      const blob = new Blob([combined], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = window.document.createElement('a')
      a.href = url
      a.download = `batch-export-${batchJob.id}.${exportFormat}`
      a.click()
      URL.revokeObjectURL(url)
    },
  })

  // Effect to handle batch completion
  useEffect(() => {
    if (batchJob?.status === 'completed') {
      onBatchComplete?.()
    }
  }, [batchJob?.status, onBatchComplete])

  const toggleSection = useCallback((section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }, [])

  const toggleDocument = useCallback((docId: string) => {
    setSelectedDocuments((prev) =>
      prev.includes(docId)
        ? prev.filter((id) => id !== docId)
        : [...prev, docId],
    )
  }, [])

  const handleStartBatch = useCallback(() => {
    if (selectedDocuments.length > 0) {
      createBatchMutation.mutate()
    }
  }, [createBatchMutation, selectedDocuments])

  const handleProcessBatch = useCallback(() => {
    if (activeBatchId) {
      processBatchMutation.mutate(activeBatchId)
    }
  }, [activeBatchId, processBatchMutation])

  const handleNewBatch = useCallback(() => {
    setActiveBatchId(null)
    setSelectedDocuments(documentIds)
  }, [documentIds])

  // Calculate progress
  const progress = batchJob
    ? {
        total: batchJob.document_ids.length,
        processed: batchJob.processed_count,
        failed: batchJob.failed_count,
        percent: Math.round(
          (batchJob.processed_count / batchJob.document_ids.length) * 100,
        ),
      }
    : null

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-gray-900 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div>
            <h2 className="text-lg font-semibold text-white">
              Batch Processing
            </h2>
            <p className="text-sm text-gray-400">
              Process multiple documents at once
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors min-w-[36px] min-h-[36px]"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Configuration Section */}
          {!activeBatchId && (
            <div className="border-b border-gray-700">
              <button
                onClick={() => toggleSection('config')}
                className="w-full flex items-center justify-between px-6 py-3 hover:bg-gray-800 transition-colors"
              >
                <span className="font-medium text-white">Configuration</span>
                {expandedSections.has('config') ? (
                  <ChevronDown size={18} className="text-gray-400" />
                ) : (
                  <ChevronRight size={18} className="text-gray-400" />
                )}
              </button>

              {expandedSections.has('config') && (
                <div className="px-6 pb-4 space-y-4">
                  {/* Template Selection */}
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Apply Template (Optional)
                    </label>
                    <select
                      value={selectedTemplateId}
                      onChange={(e) => setSelectedTemplateId(e.target.value)}
                      className="w-full p-3 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">No template (process only)</option>
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Document Selection */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium text-gray-300">
                        Documents ({selectedDocuments.length} selected)
                      </label>
                      <button
                        onClick={() =>
                          setSelectedDocuments(
                            selectedDocuments.length === documentIds.length
                              ? []
                              : documentIds,
                          )
                        }
                        className="text-xs text-blue-400 hover:text-blue-300"
                      >
                        {selectedDocuments.length === documentIds.length
                          ? 'Deselect All'
                          : 'Select All'}
                      </button>
                    </div>
                    <div className="max-h-48 overflow-y-auto bg-gray-800 rounded-lg border border-gray-700">
                      {documentIds.length === 0 ? (
                        <div className="p-4 text-center text-gray-500">
                          No documents available
                        </div>
                      ) : (
                        documentIds.map((docId) => (
                          <label
                            key={docId}
                            className="flex items-center gap-3 p-3 hover:bg-gray-750 cursor-pointer border-b border-gray-700 last:border-b-0"
                          >
                            <input
                              type="checkbox"
                              checked={selectedDocuments.includes(docId)}
                              onChange={() => toggleDocument(docId)}
                              className="w-4 h-4 rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
                            />
                            <FileImage size={16} className="text-gray-400" />
                            <span className="text-sm text-gray-300 truncate">
                              {docId}
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Start Button */}
                  <button
                    onClick={handleStartBatch}
                    disabled={
                      selectedDocuments.length === 0 ||
                      createBatchMutation.isPending
                    }
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50 transition-colors min-h-[48px]"
                  >
                    {createBatchMutation.isPending ? (
                      <Loader2 size={18} className="animate-spin" />
                    ) : (
                      <Play size={18} />
                    )}
                    Create Batch Job
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Active Batch Section */}
          {activeBatchId && (
            <>
              {/* Progress Section */}
              <div className="border-b border-gray-700">
                <button
                  onClick={() => toggleSection('progress')}
                  className="w-full flex items-center justify-between px-6 py-3 hover:bg-gray-800 transition-colors"
                >
                  <span className="font-medium text-white">Progress</span>
                  {expandedSections.has('progress') ? (
                    <ChevronDown size={18} className="text-gray-400" />
                  ) : (
                    <ChevronRight size={18} className="text-gray-400" />
                  )}
                </button>

                {expandedSections.has('progress') && (
                  <div className="px-6 pb-4">
                    {isLoadingBatch ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2
                          size={32}
                          className="animate-spin text-gray-500"
                        />
                      </div>
                    ) : batchJob ? (
                      <div className="space-y-4">
                        {/* Status Badge */}
                        <div className="flex items-center gap-3">
                          <div
                            className={`flex items-center gap-2 ${STATUS_CONFIG[batchJob.status as BatchStatus].color}`}
                          >
                            {STATUS_CONFIG[batchJob.status as BatchStatus].icon}
                            <span className="font-medium">
                              {
                                STATUS_CONFIG[batchJob.status as BatchStatus]
                                  .label
                              }
                            </span>
                          </div>
                          {batchJob.status === 'pending' && (
                            <button
                              onClick={handleProcessBatch}
                              disabled={processBatchMutation.isPending}
                              className="flex items-center gap-1 px-3 py-1 text-sm rounded bg-blue-600 hover:bg-blue-700 text-white"
                            >
                              {processBatchMutation.isPending ? (
                                <Loader2 size={14} className="animate-spin" />
                              ) : (
                                <Play size={14} />
                              )}
                              Start
                            </button>
                          )}
                          <button
                            onClick={() => refetchBatchJob()}
                            className="ml-auto p-1 rounded hover:bg-gray-700 text-gray-400"
                            title="Refresh status"
                          >
                            <RefreshCw size={16} />
                          </button>
                        </div>

                        {/* Progress Bar */}
                        {progress && (
                          <div>
                            <div className="flex items-center justify-between text-sm mb-2">
                              <span className="text-gray-400">
                                {progress.processed} of {progress.total}{' '}
                                documents processed
                              </span>
                              <span className="text-gray-300 font-medium">
                                {progress.percent}%
                              </span>
                            </div>
                            <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
                              <div
                                className={`h-full transition-all duration-500 ${
                                  progress.failed > 0
                                    ? 'bg-gradient-to-r from-green-500 to-red-500'
                                    : 'bg-green-500'
                                }`}
                                style={{ width: `${progress.percent}%` }}
                              />
                            </div>
                            {progress.failed > 0 && (
                              <div className="flex items-center gap-2 mt-2 text-sm text-red-400">
                                <AlertCircle size={14} />
                                {progress.failed} document
                                {progress.failed !== 1 ? 's' : ''} failed
                              </div>
                            )}
                          </div>
                        )}

                        {/* Batch Info */}
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div className="bg-gray-800 rounded-lg p-3">
                            <div className="text-gray-500 mb-1">Batch ID</div>
                            <div className="text-gray-300 font-mono text-xs truncate">
                              {batchJob.id}
                            </div>
                          </div>
                          <div className="bg-gray-800 rounded-lg p-3">
                            <div className="text-gray-500 mb-1">Template</div>
                            <div className="text-gray-300">
                              {batchJob.template_id
                                ? templates.find(
                                    (t) => t.id === batchJob.template_id,
                                  )?.name || 'Unknown'
                                : 'None'}
                            </div>
                          </div>
                          <div className="bg-gray-800 rounded-lg p-3">
                            <div className="text-gray-500 mb-1">Created</div>
                            <div className="text-gray-300">
                              {new Date(batchJob.created_at).toLocaleString()}
                            </div>
                          </div>
                          <div className="bg-gray-800 rounded-lg p-3">
                            <div className="text-gray-500 mb-1">Documents</div>
                            <div className="text-gray-300">
                              {batchJob.document_ids.length}
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center text-gray-500 py-8">
                        No batch job data available
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Export Section */}
              {batchJob?.status === 'completed' && (
                <div className="border-b border-gray-700">
                  <button
                    onClick={() => toggleSection('export')}
                    className="w-full flex items-center justify-between px-6 py-3 hover:bg-gray-800 transition-colors"
                  >
                    <span className="font-medium text-white">Export All</span>
                    {expandedSections.has('export') ? (
                      <ChevronDown size={18} className="text-gray-400" />
                    ) : (
                      <ChevronRight size={18} className="text-gray-400" />
                    )}
                  </button>

                  {expandedSections.has('export') && (
                    <div className="px-6 pb-4 space-y-4">
                      {/* Export Format */}
                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          Export Format
                        </label>
                        <div className="flex gap-2">
                          {(['json', 'csv', 'sql'] as ExportFormat[]).map(
                            (format) => (
                              <button
                                key={format}
                                onClick={() => setExportFormat(format)}
                                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                                  exportFormat === format
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                }`}
                              >
                                {format.toUpperCase()}
                              </button>
                            ),
                          )}
                        </div>
                      </div>

                      {/* Export Button */}
                      <button
                        onClick={() => exportAllMutation.mutate()}
                        disabled={exportAllMutation.isPending}
                        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-green-600 hover:bg-green-700 text-white font-medium disabled:opacity-50 transition-colors min-h-[48px]"
                      >
                        {exportAllMutation.isPending ? (
                          <Loader2 size={18} className="animate-spin" />
                        ) : (
                          <Download size={18} />
                        )}
                        Export All ({batchJob.processed_count} documents)
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-700">
          {activeBatchId ? (
            <>
              <button
                onClick={handleNewBatch}
                className="flex items-center gap-2 px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
              >
                <RefreshCw size={16} />
                New Batch
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
              >
                Close
              </button>
            </>
          ) : (
            <div className="flex-1 flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm min-h-[40px]"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
