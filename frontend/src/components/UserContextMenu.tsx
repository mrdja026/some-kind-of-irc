import type { User } from '../types'

interface UserContextMenuProps {
  position: { x: number; y: number }
  user: User
  onClose: () => void
  onProfile: () => void
  onMessage: () => void
}

export function UserContextMenu({
  position,
  user,
  onClose,
  onProfile,
  onMessage,
}: UserContextMenuProps) {
  return (
    <div
      className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-32"
      style={{ left: position.x, top: position.y }}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        onClick={() => {
          onProfile()
          onClose()
        }}
        className="w-full text-left px-4 py-2 hover:bg-gray-100 text-sm"
      >
        Profile
      </button>
      <button
        onClick={() => {
          onMessage()
          onClose()
        }}
        className="w-full text-left px-4 py-2 hover:bg-gray-100 text-sm"
      >
        Message
      </button>
    </div>
  )
}
