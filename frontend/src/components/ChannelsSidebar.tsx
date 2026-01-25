import { Plus, X, Sparkles, FileText } from 'lucide-react'
import type { Channel, User } from '../types'

interface ChannelsSidebarProps {
  channels: Channel[] | undefined
  directMessages: Channel[] | undefined
  selectedChannelId: number | null
  user: User | undefined
  dmUsersById: Map<number, User>
  isInteractionDisabled: boolean
  onChannelSelect: (channel: Channel) => void
  onClose?: () => void
  // Channel creation props
  showCreateChannel: boolean
  setShowCreateChannel: (show: boolean) => void
  newChannelName: string
  setNewChannelName: (name: string) => void
  newChannelType: 'public' | 'private'
  setNewChannelType: (type: 'public' | 'private') => void
  channelCreateError: string | null
  setChannelCreateError: (error: string | null) => void
  isCreatingChannel: boolean
  onCreateChannel: (e: React.FormEvent) => void
  isDataProcessorChannel: boolean
  setIsDataProcessorChannel: (isDataProcessor: boolean) => void
}

export function ChannelsSidebar({
  channels,
  directMessages,
  selectedChannelId,
  user,
  dmUsersById,
  isInteractionDisabled,
  onChannelSelect,
  onClose,
  showCreateChannel,
  setShowCreateChannel,
  newChannelName,
  setNewChannelName,
  newChannelType,
  setNewChannelType,
  channelCreateError,
  setChannelCreateError,
  isCreatingChannel,
  onCreateChannel,
  isDataProcessorChannel,
  setIsDataProcessorChannel,
}: ChannelsSidebarProps) {
  const handleChannelClick = (channel: Channel) => {
    if (!isInteractionDisabled) {
      onChannelSelect(channel)
      onClose?.()
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-2 touch-pan-y">
      <div className="flex items-center justify-between px-2 md:px-3 py-2">
        <div className="text-xs uppercase tracking-wider font-semibold chat-meta">
          Channels
        </div>
        <button
          onClick={() => setShowCreateChannel(true)}
          disabled={isInteractionDisabled}
          className="p-2 rounded transition-colors chat-menu-button hover:opacity-80 min-w-[44px] min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Create channel"
          title="Create channel"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Create Channel Form */}
      {showCreateChannel && (
        <div className="px-2 md:px-3 py-2 mb-2 border rounded-lg chat-divider">
          <form onSubmit={onCreateChannel} className="space-y-2">
            <input
              type="text"
              value={newChannelName}
              onChange={(e) => setNewChannelName(e.target.value)}
              placeholder={
                newChannelType === 'public' ? '#channel-name' : 'Channel name'
              }
              disabled={isInteractionDisabled}
              className="w-full px-3 py-2 rounded text-sm chat-input min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
              autoFocus
            />
            <div className="flex items-center gap-2 px-1">
              <input
                type="checkbox"
                id="isDataProcessor"
                checked={isDataProcessorChannel}
                onChange={(e) => setIsDataProcessorChannel(e.target.checked)}
                disabled={isInteractionDisabled}
                className="w-4 h-4 rounded chat-checkbox disabled:opacity-50"
              />
              <label
                htmlFor="isDataProcessor"
                className="text-xs chat-meta cursor-pointer select-none"
              >
                Data Processor Channel
              </label>
            </div>
            <div className="flex gap-2">
              <select
                value={newChannelType}
                onChange={(e) =>
                  setNewChannelType(e.target.value as 'public' | 'private')
                }
                disabled={isInteractionDisabled}
                className="flex-1 px-2 py-2 rounded text-sm chat-input min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="public">Public</option>
                <option value="private">Private</option>
              </select>
              <button
                type="submit"
                disabled={
                  isInteractionDisabled ||
                  !newChannelName.trim() ||
                  isCreatingChannel
                }
                className="px-3 py-2 text-sm font-semibold rounded transition-colors chat-send-button disabled:opacity-60 min-h-[44px]"
              >
                {isCreatingChannel ? '...' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateChannel(false)
                  setNewChannelName('')
                  setNewChannelType('public')
                  setChannelCreateError(null)
                }}
                className="px-2 py-2 text-sm rounded transition-colors chat-menu-button min-w-[44px] min-h-[44px]"
              >
                <X size={14} />
              </button>
            </div>
            {channelCreateError && (
              <div className="text-xs text-red-600">{channelCreateError}</div>
            )}
          </form>
        </div>
      )}

      {/* Public Channels */}
      {channels
        ?.filter((ch) => ch.type === 'public')
        .map((channel) => (
          <div
            key={channel.id}
            onClick={() => handleChannelClick(channel)}
            className={`px-2 md:px-3 py-2 rounded transition-colors chat-channel-item flex items-center gap-2 min-h-[44px] ${
              selectedChannelId === channel.id
                ? 'chat-channel-item--active'
                : ''
            } ${
              isInteractionDisabled
                ? 'opacity-50 cursor-not-allowed'
                : 'cursor-pointer'
            }`}
          >
            {channel.name === '#ai' && (
              <Sparkles size={14} className="text-amber-600 flex-shrink-0" />
            )}
            {channel.is_data_processor && (
              <FileText size={14} className="text-blue-600 flex-shrink-0" />
            )}
            <span className="text-sm md:text-base truncate">
              {channel.name}
            </span>
          </div>
        ))}

      {/* Direct Messages */}
      <div className="text-xs uppercase tracking-wider font-semibold px-2 md:px-3 py-2 mt-4 chat-meta">
        Direct Messages
      </div>
      {directMessages?.map((dmChannel) => {
        // Parse DM channel name to get other user ID
        const match = dmChannel.name.match(/dm-(\d+)-(\d+)/)
        const otherUserId = match
          ? parseInt(match[1]) === user?.id
            ? parseInt(match[2])
            : parseInt(match[1])
          : null
        const otherUser = otherUserId ? dmUsersById.get(otherUserId) : null

        return (
          <div
            key={dmChannel.id}
            onClick={() => handleChannelClick(dmChannel)}
            className={`px-2 md:px-3 py-2 rounded transition-colors chat-channel-item min-h-[44px] ${
              selectedChannelId === dmChannel.id
                ? 'chat-channel-item--active'
                : ''
            } ${
              isInteractionDisabled
                ? 'opacity-50 cursor-not-allowed'
                : 'cursor-pointer'
            }`}
          >
            <span className="text-sm md:text-base truncate">
              {otherUser?.display_name || otherUser?.username || dmChannel.name}
            </span>
          </div>
        )
      })}
    </div>
  )
}
