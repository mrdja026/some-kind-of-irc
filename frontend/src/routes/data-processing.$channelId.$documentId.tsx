import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { getChannels } from '../api'
import { getDocument } from '../api/dataProcessor'
import { DocumentAnnotationModal } from '../components/DocumentAnnotationModal'

export const Route = createFileRoute('/data-processing/$channelId/$documentId')(
  {
    component: DataProcessingDocumentPage,
  },
)

function DataProcessingDocumentPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { channelId, documentId } = Route.useParams()
  const parsedChannelId = Number(channelId)
  const hasValidChannelId =
    Number.isInteger(parsedChannelId) && parsedChannelId > 0

  const { data: channels, isLoading: isLoadingChannels } = useQuery({
    queryKey: ['channels'],
    queryFn: getChannels,
    enabled: hasValidChannelId,
  })

  const {
    data: document,
    isLoading: isLoadingDocument,
    isError: isDocumentError,
  } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => getDocument(documentId),
    enabled: !!documentId,
  })

  const selectedChannel = channels?.find((channel) => channel.id === parsedChannelId)
  const isDataProcessorChannel = !!selectedChannel?.is_data_processor
  const isDocumentChannelMismatch =
    !!document && String(document.channel_id) !== String(parsedChannelId)

  const handleBack = () => {
    queryClient.invalidateQueries({ queryKey: ['documents', parsedChannelId] })
    navigate({
      to: '/chat',
      search: {
        channelId: parsedChannelId,
      },
    })
  }

  if (!hasValidChannelId) {
    return (
      <div className="flex h-screen items-center justify-center p-4">
        <button
          type="button"
          onClick={() => navigate({ to: '/chat' })}
          className="flex items-center gap-2 rounded bg-gray-800 px-4 py-2 text-white"
        >
          <ArrowLeft size={16} />
          Back to chat
        </button>
      </div>
    )
  }

  if (isLoadingChannels || isLoadingDocument) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <Loader2 size={48} className="animate-spin text-gray-400" />
      </div>
    )
  }

  if (isDocumentError || !document || !selectedChannel || !isDataProcessorChannel || isDocumentChannelMismatch) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-black p-4 text-center text-white">
        <p className="text-sm text-gray-300">
          This document is not available for the selected data-processing channel.
        </p>
        <button
          type="button"
          onClick={handleBack}
          className="flex items-center gap-2 rounded bg-gray-800 px-4 py-2 text-white"
        >
          <ArrowLeft size={16} />
          Back to channel
        </button>
      </div>
    )
  }

  return (
    <DocumentAnnotationModal
      documentId={documentId}
      filename={document.original_filename}
      channelId={parsedChannelId}
      onClose={handleBack}
      onStatusChange={() => {
        queryClient.invalidateQueries({ queryKey: ['documents', parsedChannelId] })
      }}
    />
  )
}
