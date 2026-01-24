import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getCurrentUser,
  getChannels,
  getDirectMessages,
  getMessages,
  sendMessage,
  uploadImage,
  joinChannel,
  createDirectMessageChannel,
  getUserById,
  searchChannels,
} from '../api'
import { useChatSocket } from '../hooks/useChatSocket'
import type { Channel, Message, User } from '../types'
import { Home, LogIn, Menu, MessageSquare, X } from 'lucide-react'

export const Route = createFileRoute('/chat')({ component: ChatPage })

function ChatPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(
    null,
  )
  const [messageInput, setMessageInput] = useState('')
  const [dmUserIdInput, setDmUserIdInput] = useState('')
  const [typingUsers, setTypingUsers] = useState<Set<number>>(new Set())
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [isNavOpen, setIsNavOpen] = useState(false)

  // Get current user
  const {
    data: user,
    error: userError,
    isLoading: userLoading,
  } = useQuery({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
  })

  // Get channels
  const {
    data: channels,
    error: channelsError,
    isLoading: channelsLoading,
    refetch: refetchChannels,
  } = useQuery({
    queryKey: ['channels'],
    queryFn: getChannels,
  })

  // Get direct messages
  const {
    data: directMessages,
    error: dmsError,
    isLoading: dmsLoading,
    refetch: refetchDirectMessages,
  } = useQuery({
    queryKey: ['directMessages'],
    queryFn: getDirectMessages,
  })

  // Get messages for selected channel
  const {
    data: messages,
    error: messagesError,
    isLoading: messagesLoading,
    refetch,
  } = useQuery({
    queryKey: ['messages', selectedChannelId],
    queryFn: async () => {
      if (!selectedChannelId) return []
      return getMessages(selectedChannelId)
    },
    enabled: !!selectedChannelId,
  })

  // Handle typing indicator
  const handleTyping = (channelId: number, userId: number) => {
    if (channelId === selectedChannelId) {
      setTypingUsers((prev) => new Set([...prev, userId]))
      // Remove typing indicator after 2 seconds
      setTimeout(() => {
        setTypingUsers((prev) => {
          const newSet = new Set(prev)
          newSet.delete(userId)
          return newSet
        })
      }, 2000)
    }
  }

  // WebSocket connection
  const {
    isConnected,
    sendMessage: sendSocketMessage,
    sendTyping,
  } = useChatSocket(
    user?.id || 0,
    '', // No token needed as we use cookies
    handleTyping,
  )

  // Handle user not authenticated
  useEffect(() => {
    if (userError) {
      navigate({ to: '/login' })
    }
  }, [userError, navigate])

  // Handle channel selection
  const handleChannelSelect = async (channel: Channel) => {
    setSelectedChannelId(channel.id)
    // Join channel if not already joined
    try {
      await joinChannel(channel.id)
    } catch (error) {
      console.error('Failed to join channel:', error)
    }
  }

  // Handle DM channel creation
  const handleCreateDMChannel = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!dmUserIdInput.trim()) return
    const userId = parseInt(dmUserIdInput.trim())
    try {
      const channel = await createDirectMessageChannel(userId)
      setDmUserIdInput('')
      await refetchDirectMessages()
      setSelectedChannelId(channel.id)
    } catch (error) {
      console.error('Failed to create DM channel:', error)
    }
  }

  // Handle message input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMessageInput(e.target.value)
    if (selectedChannelId) {
      sendTyping(selectedChannelId)
    }
  }

  const handleAttachmentClick = () => {
    setUploadError(null)
    if (!selectedChannelId) return
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !selectedChannelId || !user) return

    setIsUploading(true)
    setUploadError(null)

    try {
      const upload = await uploadImage(file)
      const trimmedContent = messageInput.trim()
      const optimisticMessage: Message = {
        id: Date.now(),
        client_temp_id: Date.now(),
        content: trimmedContent,
        sender_id: user.id,
        channel_id: selectedChannelId,
        timestamp: new Date().toISOString(),
        image_url: upload.url,
      }

      queryClient.setQueryData(
        ['messages', selectedChannelId],
        (oldData: Message[] = []) => [...oldData, optimisticMessage],
      )

      setMessageInput('')

      const actualMessage = await sendMessage(
        selectedChannelId,
        trimmedContent,
        upload.url,
      )

      queryClient.setQueryData(
        ['messages', selectedChannelId],
        (oldData: Message[] = []) => {
          const withoutOptimistic = oldData.filter(
            (msg) => msg.client_temp_id !== optimisticMessage.client_temp_id,
          )
          const hasActual = withoutOptimistic.some(
            (msg) => msg.id === actualMessage.id,
          )
          if (hasActual) {
            return withoutOptimistic.map((msg) =>
              msg.id === actualMessage.id ? { ...msg, ...actualMessage } : msg,
            )
          }
          return [...withoutOptimistic, actualMessage]
        },
      )
    } catch (error) {
      setUploadError('Upload failed. Please try again.')
      console.error('Failed to upload image:', error)
    } finally {
      setIsUploading(false)
    }
  }

  // Handle message submission with optimistic UI
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!messageInput.trim() || !selectedChannelId) return

    // Handle slash commands
    const trimmedInput = messageInput.trim()
    if (trimmedInput.startsWith('/')) {
      // Parse command
      const [command, ...args] = trimmedInput.slice(1).split(' ')

      switch (command.toLowerCase()) {
        case 'join':
          if (args.length > 0) {
            const channelName = args[0].startsWith('#')
              ? args[0]
              : `#${args[0]}`
            try {
              // Search for channel by name
              const channels = await searchChannels(channelName)
              if (channels.length > 0) {
                const channel = channels[0]
                await joinChannel(channel.id)
                await refetchChannels() // Refetch channels to update list
                setSelectedChannelId(channel.id) // Join the channel
              } else {
                console.error('Channel not found')
              }
            } catch (error) {
              console.error('Failed to join channel:', error)
            }
          }
          setMessageInput('')
          return
        case 'nick':
          if (args.length > 0) {
            // Implement nickname change (not supported yet)
            console.error('Nickname change not implemented')
          }
          setMessageInput('')
          return
        case 'me':
          if (args.length > 0) {
            const action = args.join(' ')
            // Create optimistic message for /me command
            const optimisticMessage: Message = {
              id: Date.now(), // Temporary ID
              client_temp_id: Date.now(),
              content: `/me ${action}`,
              sender_id: user!.id,
              channel_id: selectedChannelId,
              timestamp: new Date().toISOString(),
              image_url: null,
            }
            // Optimistically update the cache
            queryClient.setQueryData(
              ['messages', selectedChannelId],
              (oldData: Message[] = []) => [...oldData, optimisticMessage],
            )
            // Send the message to the server
            try {
              const actualMessage = await sendMessage(
                selectedChannelId,
                `/me ${action}`,
              )
              // Replace or append, while removing the optimistic message
              queryClient.setQueryData(
                ['messages', selectedChannelId],
                (oldData: Message[] = []) => {
                  const withoutOptimistic = oldData.filter(
                    (msg) =>
                      msg.client_temp_id !== optimisticMessage.client_temp_id,
                  )
                  const hasActual = withoutOptimistic.some(
                    (msg) => msg.id === actualMessage.id,
                  )
                  if (hasActual) {
                    return withoutOptimistic.map((msg) =>
                      msg.id === actualMessage.id
                        ? { ...msg, ...actualMessage }
                        : msg,
                    )
                  }
                  return [...withoutOptimistic, actualMessage]
                },
              )
            } catch (error) {
              // Remove the optimistic message if there's an error
              queryClient.setQueryData(
                ['messages', selectedChannelId],
                (oldData: Message[] = []) =>
                  oldData.filter(
                    (msg) =>
                      msg.client_temp_id !== optimisticMessage.client_temp_id,
                  ),
              )
              console.error('Failed to send message:', error)
            }
            setMessageInput('')
          }
          return
        default:
          console.error('Unknown command:', command)
          setMessageInput('')
          return
      }
    }

    // Regular message with optimistic UI
    const optimisticMessage: Message = {
      id: Date.now(), // Temporary ID
      client_temp_id: Date.now(),
      content: trimmedInput,
      sender_id: user!.id,
      channel_id: selectedChannelId,
      timestamp: new Date().toISOString(),
      image_url: null,
    }
    // Optimistically update the cache
    queryClient.setQueryData(
      ['messages', selectedChannelId],
      (oldData: Message[] = []) => [...oldData, optimisticMessage],
    )
    // Send the message to the server
    try {
      const actualMessage = await sendMessage(selectedChannelId, trimmedInput)
      // Replace or append, while removing the optimistic message
      queryClient.setQueryData(
        ['messages', selectedChannelId],
        (oldData: Message[] = []) => {
          const withoutOptimistic = oldData.filter(
            (msg) => msg.client_temp_id !== optimisticMessage.client_temp_id,
          )
          if (withoutOptimistic.some((msg) => msg.id === actualMessage.id)) {
            return withoutOptimistic
          }
          return [...withoutOptimistic, actualMessage]
        },
      )
    } catch (error) {
      // Remove the optimistic message if there's an error
      queryClient.setQueryData(
        ['messages', selectedChannelId],
        (oldData: Message[] = []) =>
          oldData.filter(
            (msg) => msg.client_temp_id !== optimisticMessage.client_temp_id,
          ),
      )
      console.error('Failed to send message:', error)
    }
    setMessageInput('')
  }

  // Loading states
  if (userLoading || channelsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center chat-shell">
        <div className="text-lg chat-meta">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex chat-shell">
      {isNavOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={() => setIsNavOpen(false)}
        />
      )}
      <aside
        className={`fixed top-0 left-0 h-full w-72 z-50 transform transition-transform duration-300 ease-in-out nav-drawer ${
          isNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b chat-divider">
          <div className="text-lg font-semibold">Navigation</div>
          <button
            onClick={() => setIsNavOpen(false)}
            className="p-2 rounded-lg chat-menu-button"
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <Link
            to="/"
            onClick={() => setIsNavOpen(false)}
            className="flex items-center gap-3 p-3 rounded-lg nav-link"
            activeProps={{
              className:
                'flex items-center gap-3 p-3 rounded-lg nav-link nav-link--active',
            }}
          >
            <Home size={18} />
            <span className="font-medium">Home</span>
          </Link>
          <Link
            to="/login"
            onClick={() => setIsNavOpen(false)}
            className="flex items-center gap-3 p-3 rounded-lg nav-link"
            activeProps={{
              className:
                'flex items-center gap-3 p-3 rounded-lg nav-link nav-link--active',
            }}
          >
            <LogIn size={18} />
            <span className="font-medium">Login</span>
          </Link>
          <Link
            to="/chat"
            onClick={() => setIsNavOpen(false)}
            className="flex items-center gap-3 p-3 rounded-lg nav-link"
            activeProps={{
              className:
                'flex items-center gap-3 p-3 rounded-lg nav-link nav-link--active',
            }}
          >
            <MessageSquare size={18} />
            <span className="font-medium">Chat</span>
          </Link>
        </nav>
      </aside>
      {/* Sidebar */}
      <div className="w-64 flex flex-col chat-sidebar">
        {/* User info */}
        <div className="p-4 border-b chat-divider">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsNavOpen(true)}
              className="p-2 rounded-lg chat-menu-button"
              aria-label="Open menu"
            >
              <Menu size={18} />
            </button>
            <div className="w-10 h-10 rounded-full flex items-center justify-center chat-avatar">
              <span className="font-bold">
                {user?.username[0].toUpperCase()}
              </span>
            </div>
            <div>
              <div className="font-semibold">{user?.username}</div>
              <div className="text-sm chat-meta">Online</div>
            </div>
          </div>
        </div>

        {/* Channels list */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="text-xs uppercase tracking-wider font-semibold px-3 py-2 chat-meta">
            Channels
          </div>
          {channels
            ?.filter((ch) => ch.type === 'public')
            .map((channel) => (
              <div
                key={channel.id}
                onClick={() => handleChannelSelect(channel)}
                className={`px-3 py-2 rounded cursor-pointer transition-colors chat-channel-item ${
                  selectedChannelId === channel.id
                    ? 'chat-channel-item--active'
                    : ''
                }`}
              >
                {channel.name}
              </div>
            ))}

          {/* Direct Messages */}
          <div className="text-xs uppercase tracking-wider font-semibold px-3 py-2 mt-4 chat-meta">
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

            const { data: otherUser } = useQuery<User>({
              queryKey: ['user', otherUserId],
              queryFn: () => getUserById(otherUserId!),
              enabled: !!otherUserId,
            })

            return (
              <div
                key={dmChannel.id}
                onClick={() => handleChannelSelect(dmChannel)}
                className={`px-3 py-2 rounded cursor-pointer transition-colors chat-channel-item ${
                  selectedChannelId === dmChannel.id
                    ? 'chat-channel-item--active'
                    : ''
                }`}
              >
                {otherUser?.username || dmChannel.name}
              </div>
            )
          })}

          {/* Create DM Form */}
          <div className="px-3 py-2 mt-4">
            <form onSubmit={handleCreateDMChannel} className="flex gap-2">
              <input
                type="text"
                value={dmUserIdInput}
                onChange={(e) => setDmUserIdInput(e.target.value)}
                placeholder="User ID"
                className="flex-1 px-3 py-1 rounded text-sm chat-input"
              />
              <button
                type="submit"
                disabled={!dmUserIdInput.trim()}
                className="px-3 py-1 text-sm font-semibold rounded transition-colors chat-send-button disabled:opacity-60"
              >
                DM
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {selectedChannelId ? (
          <>
            {/* Channel header */}
            <div className="p-4 border-b chat-header">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full chat-dot"></div>
                <div className="font-semibold">
                  {channels?.find((c) => c.id === selectedChannelId)?.name}
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4">
              {messagesLoading ? (
                <div className="text-center py-8 chat-meta">
                  Loading messages...
                </div>
              ) : messages?.length === 0 ? (
                <div className="text-center py-8 chat-meta">
                  No messages yet. Start the conversation!
                </div>
              ) : (
                <div className="space-y-4">
                  {messages?.map((message) => (
                    <div key={message.id} className="flex gap-3 chat-card p-3 rounded-xl">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                        <span className="text-xs font-semibold">
                          {/* Show sender's initial */}
                          {message.sender_id === user?.id
                            ? 'You'
                            : `User${message.sender_id}`[0].toUpperCase()}
                        </span>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <div className="text-sm font-semibold">
                            {message.sender_id === user?.id
                              ? 'You'
                              : `User${message.sender_id}`}
                          </div>
                          <div className="text-xs chat-meta">
                            {new Date(message.timestamp).toLocaleTimeString()}
                          </div>
                        </div>
                        {message.content && (
                          <div className="mt-1 chat-message-text">
                            {message.content}
                          </div>
                        )}
                        {message.image_url && (
                          <div className="mt-2">
                            <img
                              src={message.image_url}
                              alt="Attachment"
                              className="max-w-xs rounded chat-image"
                              loading="lazy"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Typing indicator */}
              {typingUsers.size > 0 && (
                <div className="flex items-center gap-3 mt-4">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                    <span className="text-xs font-semibold">
                      {/* Show first typing user's initial */}
                      {Array.from(typingUsers)[0] === user?.id
                        ? 'You'
                        : `User${Array.from(typingUsers)[0]}`[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="text-sm chat-typing">
                      {Array.from(typingUsers)
                        .map((userId) =>
                          userId === user?.id ? 'You' : `User${userId}`,
                        )
                        .join(', ')}{' '}
                      is typing...
                    </div>
                    <div className="flex gap-1">
                      <div className="w-2 h-2 rounded-full bg-amber-700/50 animate-bounce"></div>
                      <div
                        className="w-2 h-2 rounded-full bg-amber-700/50 animate-bounce"
                        style={{ animationDelay: '0.1s' }}
                      ></div>
                      <div
                        className="w-2 h-2 rounded-full bg-amber-700/50 animate-bounce"
                        style={{ animationDelay: '0.2s' }}
                      ></div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Message input */}
            <div className="p-4 border-t chat-input-bar">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
                className="hidden"
              />
              <form onSubmit={handleSubmit} className="flex gap-2">
                <button
                  type="button"
                  onClick={handleAttachmentClick}
                  disabled={!selectedChannelId || isUploading}
                  className="px-3 py-2 rounded-lg transition-colors chat-attach-button disabled:opacity-60"
                >
                  Attach
                </button>
                <input
                  type="text"
                  value={messageInput}
                  onChange={handleInputChange}
                  placeholder="Type your message..."
                  className="flex-1 px-4 py-2 rounded-lg transition-all chat-input"
                />
                <button
                  type="submit"
                  disabled={!messageInput.trim() || !selectedChannelId}
                  className="px-4 py-2 font-semibold rounded-lg transition-colors chat-send-button disabled:opacity-60"
                >
                  Send
                </button>
              </form>
              {(isUploading || uploadError) && (
                <div className="mt-2 text-sm chat-meta">
                  {isUploading ? 'Uploading image...' : uploadError}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center chat-meta">
            Select a channel to start chatting
          </div>
        )}
      </div>
    </div>
  )
}
