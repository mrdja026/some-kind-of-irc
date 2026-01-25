import type { User } from '../types'

interface UserProfileModalProps {
  user: User
  onClose: () => void
}

export function UserProfileModal({ user, onClose }: UserProfileModalProps) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg p-6 max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">User Profile</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="flex items-center gap-4 mb-4">
          {user.profile_picture_url ? (
            <img
              src={user.profile_picture_url}
              alt={user.display_name || user.username}
              className="w-16 h-16 rounded-full object-cover"
            />
          ) : (
            <div className="w-16 h-16 rounded-full flex items-center justify-center bg-gray-200">
              <span className="text-lg font-semibold">
                {(user.display_name || user.username)?.[0].toUpperCase()}
              </span>
            </div>
          )}
          <div>
            <div className="text-lg font-semibold">
              {user.display_name || user.username}
            </div>
            <div className="text-sm text-gray-600">@{user.username}</div>
          </div>
        </div>
        {/* Add more profile info if available */}
      </div>
    </div>
  )
}
