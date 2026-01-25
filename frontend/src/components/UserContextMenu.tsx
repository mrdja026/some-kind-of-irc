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
  // Adjust position to prevent overflow on mobile
  const adjustedPosition = {
    x: Math.min(position.x, window.innerWidth - 150), // Ensure menu doesn't overflow right
    y: Math.min(position.y, window.innerHeight - 100), // Ensure menu doesn't overflow bottom
  }

  return (
    <div
      className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-32 max-w-[calc(100vw-2rem)]"
      style={{ 
        left: `${adjustedPosition.x}px`, 
        top: `${adjustedPosition.y}px`,
        maxWidth: 'calc(100vw - 2rem)', // Prevent overflow on mobile
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        onClick={() => {
          onProfile()
          onClose()
        }}
        className="w-full text-left px-4 py-3 hover:bg-gray-100 text-sm min-h-[44px]"
      >
        Profile
      </button>
      <button
        onClick={() => {
          onMessage()
          onClose()
        }}
        className="w-full text-left px-4 py-3 hover:bg-gray-100 text-sm min-h-[44px]"
      >
        Message
      </button>
    </div>
  )
}
