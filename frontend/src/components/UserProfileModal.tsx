import type { User } from '../types'

interface UserProfileModalProps {
  user: User
  onClose: () => void
}

export function UserProfileModal({ user, onClose }: UserProfileModalProps) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg p-4 sm:p-6 max-w-sm sm:max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg sm:text-xl font-semibold">User Profile</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 min-w-[44px] min-h-[44px] flex items-center justify-center"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="flex flex-col sm:flex-row items-center gap-3 sm:gap-4 mb-4">
          {user.profile_picture_url ? (
            <img
              src={user.profile_picture_url}
              alt={user.display_name || user.username}
              className="w-16 h-16 sm:w-20 sm:h-20 rounded-full object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full flex items-center justify-center bg-gray-200 flex-shrink-0">
              <span className="text-lg sm:text-xl font-semibold">
                {(user.display_name || user.username)?.[0].toUpperCase()}
              </span>
            </div>
          )}
          <div className="text-center sm:text-left">
            <div className="text-base sm:text-lg font-semibold">
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
