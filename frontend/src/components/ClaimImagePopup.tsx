import { createPortal } from 'react-dom'
import { useEffect, useRef } from 'react'
import { X, PenSquare } from 'lucide-react'

interface ClaimImagePopupProps {
  imageUrl: string
  filename: string
  onClose: () => void
  onAnnotate?: () => void
}

export function ClaimImagePopup({ imageUrl, filename, onClose, onAnnotate }: ClaimImagePopupProps) {
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    dialogRef.current?.focus()
  }, [])

  return createPortal(
    <div
      ref={dialogRef}
      className="fixed inset-0 bg-black/85 flex items-center justify-center z-50 p-4"
      onClick={onClose}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label={`Image preview: ${filename}`}
      tabIndex={-1}
    >
      <button
        onClick={(e) => {
          e.stopPropagation()
          onClose()
        }}
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
        <div className="mt-3 flex items-center gap-4">
          <span className="text-white/70 text-sm font-mono">{filename}</span>
          {onAnnotate && (
            <button
              onClick={onAnnotate}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors min-h-[40px]"
            >
              <PenSquare size={16} />
              Annotate Damage
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
