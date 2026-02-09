import { useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Heart, MessageCircle } from 'lucide-react'
import type { Message, User } from '../types'

interface ImagePopupProps {
  message: Message
  currentUser: User | undefined
  onClose: () => void
  onReply: (messageId: number, content: string) => void
  senderName: string
}

export function ImagePopup({ message, currentUser, onClose, onReply, senderName }: ImagePopupProps) {
  const [isLiked, setIsLiked] = useState(false)

  const handleReply = () => {
    onReply(message.id, `##reply-to-msg${message.id} - `)
    onClose()
  }

  const handleLike = () => {
    setIsLiked(!isLiked)
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  return createPortal(
    <div
      className="fixed inset-0 bg-black/85 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors z-10 min-w-[44px] min-h-[44px] flex items-center justify-center"
        aria-label="Close"
      >
        <X size={24} />
      </button>

      {/* Image container */}
      <div
        className="relative max-w-5xl w-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Image */}
        <div className="relative">
          <img
            src={message.image_url || ''}
            alt="Attachment"
            className="max-h-[75vh] w-auto mx-auto object-contain rounded-lg"
          />

          {/* Action bar overlay */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-4 rounded-b-lg">
            <div className="flex items-center gap-4">
              <button
                onClick={handleLike}
                className={`flex items-center gap-2 px-3 py-2 rounded-full transition-colors min-h-[44px] ${
                  isLiked
                    ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                    : 'bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                <Heart
                  size={20}
                  className={isLiked ? 'fill-red-500 text-red-500' : ''}
                />
                <span className="text-sm font-medium">
                  {isLiked ? 'Liked' : 'Like'}
                </span>
              </button>

              <button
                onClick={handleReply}
                className="flex items-center gap-2 px-3 py-2 rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors min-h-[44px]"
              >
                <MessageCircle size={20} />
                <span className="text-sm font-medium">Reply</span>
              </button>
            </div>

            {/* Message info */}
            <div className="text-white/70 text-xs mt-3">
              Sent by {senderName === 'You' || senderName === currentUser?.display_name || senderName === currentUser?.username ? 'You' : senderName} at {formatTimestamp(message.timestamp)}
            </div>

            {/* Message content if exists */}
            {message.content && (
              <div className="text-white text-sm mt-2 break-words">
                {message.content}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}
