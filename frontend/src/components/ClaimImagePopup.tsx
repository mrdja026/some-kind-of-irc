import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

interface ClaimImagePopupProps {
  imageUrl: string
  filename: string
  onClose: () => void
}

export function ClaimImagePopup({ imageUrl, filename, onClose }: ClaimImagePopupProps) {
  return createPortal(
    <div
      className="fixed inset-0 bg-black/85 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors z-10 min-w-[44px] min-h-[44px] flex items-center justify-center"
        aria-label="Close"
      >
        <X size={24} />
      </button>

      <div
        className="relative max-w-5xl w-full flex flex-col items-center"
        onClick={(e) => e.stopPropagation()}
      >
        <img
          src={imageUrl}
          alt={filename}
          className="max-h-[80vh] w-auto object-contain rounded-lg"
        />
        <div className="mt-3 text-white/70 text-sm font-mono">{filename}</div>
      </div>
    </div>,
    document.body,
  )
}
