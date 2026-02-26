import { useCallback, useState, useRef } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Upload,
  FileImage,
  Trash2,
  Eye,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Layout,
  Layers,
} from 'lucide-react'
import {
  uploadDocument,
  deleteDocument,
  listDocuments,
  listTemplates,
} from '../api/dataProcessor'
import type { Document, OcrStatus } from '../types'
import { TemplateManager } from './TemplateManager'
import { BatchStatusDashboard } from './BatchStatusDashboard'

interface DataProcessorChannelProps {
  channelId: number
  channelName: string
}

const STATUS_ICONS: Record<OcrStatus, React.ReactNode> = {
  pending: <Clock size={16} className="text-yellow-500" />,
  processing: <Loader2 size={16} className="text-blue-500 animate-spin" />,
  completed: <CheckCircle size={16} className="text-green-500" />,
  failed: <AlertCircle size={16} className="text-red-500" />,
}

const STATUS_LABELS: Record<OcrStatus, string> = {
  pending: 'Pending',
  processing: 'Processing...',
  completed: 'Completed',
  failed: 'Failed',
}

export function DataProcessorChannel({
  channelId,
  channelName,
}: DataProcessorChannelProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    null,
  )
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [isTemplateManagerOpen, setIsTemplateManagerOpen] = useState(false)
  const [isBatchDashboardOpen, setIsBatchDashboardOpen] = useState(false)

  // Fetch documents for this channel
  const { data: documentsResponse, isLoading: isLoadingDocuments } = useQuery({
    queryKey: ['documents', channelId],
    queryFn: () => listDocuments(channelId),
  })

  const documents = documentsResponse?.documents || []

  // Fetch templates for batch processing
  const { data: templates = [] } = useQuery({
    queryKey: ['templates', channelId],
    queryFn: () => listTemplates(channelId),
  })

  const navigateToDocument = useCallback(
    (documentId: string) => {
      try {
        navigate({
          to: '/data-processing/$channelId/$documentId',
          params: {
            channelId: String(channelId),
            documentId,
          },
        })
      } catch {
        window.location.assign(`/data-processing/${channelId}/${documentId}`)
      }
    },
    [channelId, navigate],
  )

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      return uploadDocument(file, channelId)
    },
    onSuccess: (data) => {
      setSelectedDocumentId(data.id)
      setUploadError(null)
      void queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
      navigateToDocument(data.id)
    },
    onError: (error: Error) => {
      setUploadError(error.message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (documentId: string) => {
      await deleteDocument(documentId)
      return documentId
    },
    onSuccess: async (documentId) => {
      if (selectedDocumentId === documentId) {
        setSelectedDocumentId(null)
      }
      await queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
    },
  })

  const handleFileSelect = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = '' // Reset input

    if (!file) return

    // Validate file type
    const validTypes = [
      'image/jpeg',
      'image/jpg',
      'image/png',
      'image/webp',
      'application/pdf',
    ]
    if (!validTypes.includes(file.type)) {
      setUploadError('Please upload a valid image or PDF file (JPEG, PNG, WebP, or PDF)')
      return
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('File size must be less than 10MB')
      return
    }

    uploadMutation.mutate(file)
  }

  const handleViewDocument = (doc: Document) => {
    setSelectedDocumentId(doc.id)
    navigateToDocument(doc.id)
  }

  const handleDeleteDocument = (doc: Document) => {
    if (confirm(`Delete "${doc.original_filename}"?`)) {
      deleteMutation.mutate(doc.id)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b chat-divider">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Document Processor</h2>
            <p className="text-sm chat-meta">
              Upload documents to annotate and extract data in {channelName}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setIsTemplateManagerOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg chat-attach-button min-h-[44px]"
            >
              <Layout size={18} />
              Templates
            </button>
            {documents.length > 0 && (
              <button
                onClick={() => setIsBatchDashboardOpen(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg chat-attach-button min-h-[44px]"
              >
                <Layers size={18} />
                Batch Process
              </button>
            )}
            <button
              onClick={handleFileSelect}
              disabled={uploadMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-lg chat-send-button disabled:opacity-50 min-h-[44px]"
            >
              {uploadMutation.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Upload size={18} />
              )}
              Upload Document
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/jpg,image/png,image/webp,application/pdf"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {uploadError && (
          <div className="mt-2 p-2 rounded bg-red-100 text-red-700 text-sm">
            {uploadError}
          </div>
        )}
      </div>

      {/* Document List */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoadingDocuments ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 size={48} className="animate-spin text-gray-500" />
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <FileImage size={64} className="chat-meta mb-4" />
            <h3 className="text-lg font-medium mb-2">No documents yet</h3>
            <p className="chat-meta mb-4 max-w-md">
              Upload an image or PDF to start annotating regions of interest
              and extracting structured data.
            </p>
            <button
              onClick={handleFileSelect}
              disabled={uploadMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-lg chat-send-button disabled:opacity-50 min-h-[44px]"
            >
              <Upload size={18} />
              Upload Your First Document
            </button>
          </div>
        ) : (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="border rounded-lg p-4 chat-card hover:shadow-md transition-shadow"
              >
                {/* Document Preview */}
                <div className="aspect-video bg-gray-100 rounded mb-3 flex items-center justify-center">
                  {doc.image_url ? (
                    <img
                      src={doc.image_url}
                      alt={doc.original_filename}
                      className="w-full h-full object-contain rounded"
                    />
                  ) : (
                    <FileImage size={48} className="text-gray-400" />
                  )}
                </div>

                {/* Document Info */}
                <div className="mb-3">
                  <h4
                    className="font-medium truncate"
                    title={doc.original_filename}
                  >
                    {doc.original_filename}
                  </h4>
                  <div className="flex items-center gap-2 mt-1">
                    {STATUS_ICONS[doc.ocr_status]}
                    <span className="text-sm chat-meta">
                      {STATUS_LABELS[doc.ocr_status]}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleViewDocument(doc)}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded chat-attach-button min-h-[44px]"
                  >
                    <Eye size={16} />
                    View
                  </button>
                  <button
                    onClick={() => handleDeleteDocument(doc)}
                    disabled={deleteMutation.isPending}
                    className="px-3 py-2 rounded chat-menu-button hover:bg-red-100 hover:text-red-600 transition-colors min-h-[44px]"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Template Manager Modal */}
      <TemplateManager
        channelId={channelId}
        isOpen={isTemplateManagerOpen}
        onClose={() => setIsTemplateManagerOpen(false)}
        selectedDocumentId={selectedDocumentId || undefined}
        onApplyTemplate={() => {
          queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
          setIsTemplateManagerOpen(false)
        }}
      />

      {/* Batch Status Dashboard */}
      <BatchStatusDashboard
        channelId={channelId}
        isOpen={isBatchDashboardOpen}
        onClose={() => setIsBatchDashboardOpen(false)}
        documentIds={documents.map((doc) => doc.id)}
        templates={templates}
        onBatchComplete={() => {
          queryClient.invalidateQueries({ queryKey: ['documents', channelId] })
        }}
      />
    </div>
  )
}
