import { useState, useEffect, useRef, useMemo } from 'react'
import { Link, useNavigate, redirect } from '@tanstack/react-router'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useQueryClient, useQueries } from '@tanstack/react-query'
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
  createChannel,
} from '../api'
import {
  getCurrentUserServer,
  getChannelsServer,
  getDirectMessagesServer,
  getMessagesServer,
} from '../api/server'
import { useChatSocket } from '../hooks/useChatSocket'
import { useUserProfileInvalidation } from '../hooks/useUserProfileInvalidation'
import type { Channel, Message, User } from '../types'
import {
  Home,
  LogIn,
  Menu,
  MessageSquare,
  X,
  Settings,
  Sparkles,
  Plus,
  ChevronDown,
  Gamepad2,
} from 'lucide-react'
import { AIChannel } from '../components/AIChannel'
import { GameChannel } from '../components/GameChannel'
import { DataProcessorChannel } from '../components/DataProcessorChannel'
import { MentionAutocomplete } from '../components/MentionAutocomplete'
import { UserProfileModal } from '../components/UserProfileModal'
import { UserContextMenu } from '../components/UserContextMenu'
import { ChannelsSidebar } from '../components/ChannelsSidebar'
import { ImagePopup } from '../components/ImagePopup'

export const Route = createFileRoute('/chat')({
  ssr: true, // Full SSR - render components on server
  loader: async () => {
    try {
      // Fetch initial data server-side
      const [user, channels, directMessages] = await Promise.all([
        getCurrentUserServer(),
        getChannelsServer(),
        getDirectMessagesServer(),
      ])

      // Find #general channel and fetch last 10 messages
      let initialMessages: Message[] = []
      let defaultChannelId: number | null = null
      const generalChannel = channels.find((c) => c.name === '#general')

      if (generalChannel) {
        defaultChannelId = generalChannel.id
        try {
          const allMessages = await getMessagesServer({
            data: { channelId: defaultChannelId },
          })
          // Get last 10 messages
          initialMessages = allMessages.slice(-10)
        } catch (error) {
          // If we can't fetch messages (e.g., not joined), that's okay
          console.error('Failed to fetch initial messages:', error)
        }
      } else if (channels.length > 0) {
        // Fallback to first channel if #general doesn't exist
        defaultChannelId = channels[0].id
        try {
          const allMessages = await getMessagesServer({
            data: { channelId: defaultChannelId },
          })
          initialMessages = allMessages.slice(-10)
        } catch (error) {
          console.error('Failed to fetch initial messages:', error)
        }
      }

      return {
        user,
        channels,
        directMessages,
        initialMessages,
        defaultChannelId,
      }
    } catch (error) {
      // Redirect to login if not authenticated
      throw redirect({ to: '/login' })
    }
  },
  headers: () => ({
    'Cache-Control': 'public, max-age=60, stale-while-revalidate=300',
  }),
  staleTime: 30_000, // 30 seconds client-side cache
  component: ChatPage,
})

// Component for displaying message with avatar
function MessageAvatar({
  message,
  currentUser,
  onUserClick,
  onImageClick,
}: {
  message: Message
  currentUser: User | undefined
  onUserClick?: (user: User, event: React.MouseEvent) => void
  onImageClick?: (message: Message) => void
}) {
  const isSystemMessage =
    message.sender_id === null || message.sender_id === undefined
  const { data: senderUser } = useQuery<User>({
    queryKey: ['user', message.sender_id],
    queryFn: () => getUserById(message.sender_id!),
    enabled:
      !isSystemMessage &&
      message.sender_id !== currentUser?.id &&
      message.sender_id !== null,
  })

  const displayUser =
    message.sender_id === currentUser?.id ? currentUser : senderUser

  // System message styling
  if (isSystemMessage) {
    return (
      <div className="flex gap-1.5 md:gap-2 chat-card p-1.5 md:p-2 rounded-lg opacity-75">
        <div className="w-5 h-5 md:w-6 md:h-6 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar mt-0.5">
          <span className="text-[10px] font-semibold">S</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <div className="text-xs font-semibold italic">
              System
            </div>
            <div className="text-[10px] chat-meta" suppressHydrationWarning>
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
          {message.content && (
            <div className="chat-message-text italic text-xs md:text-sm break-words leading-tight">
              {message.content}
            </div>
          )}
          {message.image_url && (
            <div className="mt-1">
              <img
                src={message.image_url}
                alt="Attachment"
                className="max-h-32 w-auto object-contain rounded cursor-pointer hover:opacity-90 transition-opacity chat-image"
                onClick={() => onImageClick?.(message)}
                loading="lazy"
              />
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-1.5 md:gap-2 chat-card p-1.5 md:p-2 rounded-lg">
      {displayUser?.profile_picture_url ? (
        <img
          src={displayUser.profile_picture_url}
          alt={displayUser.display_name || displayUser.username}
          className="w-5 h-5 md:w-6 md:h-6 rounded-full flex-shrink-0 object-cover mt-0.5"
        />
      ) : (
        <div className="w-5 h-5 md:w-6 md:h-6 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar mt-0.5">
          <span className="text-[10px] font-semibold">
            {(displayUser?.display_name ||
              displayUser?.username)?.[0].toUpperCase() ||
              `User${message.sender_id}`[0].toUpperCase()}
          </span>
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <div
            className={`text-xs font-semibold leading-none ${displayUser && message.sender_id !== currentUser?.id ? 'cursor-pointer hover:underline' : ''}`}
            onClick={
              displayUser && message.sender_id !== currentUser?.id
                ? (e) => {
                    e.stopPropagation()
                    onUserClick?.(displayUser, e)
                  }
                : undefined
            }
          >
            {message.sender_id === currentUser?.id
              ? 'You'
              : displayUser?.display_name ||
                displayUser?.username ||
                `User${message.sender_id}`}
          </div>
          <div className="text-[10px] chat-meta leading-none" suppressHydrationWarning>
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        </div>
        {message.content && (
          <div className="chat-message-text text-xs md:text-sm break-words leading-tight">
            {message.content}
          </div>
        )}
        {message.image_url && (
          <div className="mt-1">
            <img
              src={message.image_url}
              alt="Attachment"
              className="max-h-32 w-auto object-contain rounded cursor-pointer hover:opacity-90 transition-opacity chat-image"
              onClick={() => onImageClick?.(message)}
              loading="lazy"
            />
          </div>
        )}
      </div>
    </div>
  )
}

function ChatPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const loaderData = Route.useLoaderData()
  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(
    loaderData.defaultChannelId,
  )
  const [messageInput, setMessageInput] = useState('')
  const [dmUserIdInput, setDmUserIdInput] = useState('')
  const [typingUsers, setTypingUsers] = useState<Set<number>>(new Set())
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const messageInputRef = useRef<HTMLInputElement | null>(null)
  const messagesContainerRef = useRef<HTMLDivElement | null>(null)
  const messagesLengthRef = useRef<number>(0)
  const [isNavOpen, setIsNavOpen] = useState(false)
  const [channelModes, setChannelModes] = useState<
    Record<number, 'chat' | 'ai' | 'game'>
  >({})
  const [showCreateChannel, setShowCreateChannel] = useState(false)
  const [newChannelName, setNewChannelName] = useState('')
  const [newChannelType, setNewChannelType] = useState<'public' | 'private'>(
    'public',
  )
  const [channelCreateError, setChannelCreateError] = useState<string | null>(
    null,
  )
  const [isCreatingChannel, setIsCreatingChannel] = useState(false)
  const [isDataProcessorChannel, setIsDataProcessorChannel] = useState(false)
  const [contextMenu, setContextMenu] = useState<{
    user: User
    position: { x: number; y: number }
  } | null>(null)
  const [profileUser, setProfileUser] = useState<User | null>(null)
  const [isChannelDrawerOpen, setIsChannelDrawerOpen] = useState(false)
  const [selectedImageMessage, setSelectedImageMessage] = useState<Message | null>(null)

  // Get current user - hydrate from loader data
  const {
    data: user,
    error: userError,
    isLoading: userLoading,
  } = useQuery({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
    initialData: loaderData.user,
    staleTime: 30_000,
  })

  // Get channels - hydrate from loader data
  const {
    data: channels,
    error: channelsError,
    isLoading: channelsLoading,
    refetch: refetchChannels,
  } = useQuery({
    queryKey: ['channels'],
    queryFn: getChannels,
    initialData: loaderData.channels,
    staleTime: 30_000,
  })

  // Get direct messages - hydrate from loader data
  const {
    data: directMessages,
    error: dmsError,
    isLoading: dmsLoading,
    refetch: refetchDirectMessages,
  } = useQuery({
    queryKey: ['directMessages'],
    queryFn: getDirectMessages,
    initialData: loaderData.directMessages,
    staleTime: 30_000,
  })

  const selectedChannel =
    channels?.find((c) => c.id === selectedChannelId) || null
  const defaultMode =
    selectedChannel?.name === '#ai'
      ? 'ai'
      : selectedChannel?.name === '#game'
        ? 'game'
        : 'chat'
  const activeMode = selectedChannelId
    ? (channelModes[selectedChannelId] ?? defaultMode)
    : 'chat'

  const setChannelMode = (mode: 'chat' | 'ai' | 'game') => {
    if (!selectedChannelId) return
    setChannelModes((prev) => ({ ...prev, [selectedChannelId]: mode }))
  }

  const dmUserIds = useMemo(() => {
    if (!directMessages || !user) return []
    const ids: number[] = []
    for (const dmChannel of directMessages) {
      const match = dmChannel.name.match(/dm-(\d+)-(\d+)/)
      if (!match) continue
      const first = parseInt(match[1])
      const second = parseInt(match[2])
      const otherId = first === user.id ? second : first
      if (!Number.isNaN(otherId)) {
        ids.push(otherId)
      }
    }
    return Array.from(new Set(ids))
  }, [directMessages, user])

  const dmUserQueries = useQueries({
    queries: dmUserIds.map((userId) => ({
      queryKey: ['user', userId],
      queryFn: () => getUserById(userId),
      enabled: true,
    })),
  })

  const dmUsersById = useMemo(() => {
    const map = new Map<number, User>()
    dmUserQueries.forEach((query, index) => {
      const userId = dmUserIds[index]
      if (query.data) {
        map.set(userId, query.data)
      }
    })
    return map
  }, [dmUserQueries, dmUserIds])

  const selectedChannelOtherUser = useMemo(() => {
    if (!selectedChannel || selectedChannel.type !== 'private' || !user)
      return null
    const match = selectedChannel.name.match(/dm-(\d+)-(\d+)/)
    if (!match) return null
    const id1 = parseInt(match[1])
    const id2 = parseInt(match[2])
    const otherId = id1 === user.id ? id2 : id1
    return dmUsersById.get(otherId) || null
  }, [selectedChannel, user, dmUsersById])

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

  // Use the invalidation hook to watch for profile changes
  useUserProfileInvalidation()

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

  // Get messages for selected channel - hydrate initial messages if available
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
    refetchInterval: isConnected ? false : 2000,
    initialData:
      selectedChannelId === loaderData.defaultChannelId
        ? loaderData.initialMessages
        : undefined,
    staleTime: 30_000,
  })

  // Auto-scroll to bottom when new messages arrive for the focused channel
  useEffect(() => {
    if (!messages || messages.length === 0) {
      messagesLengthRef.current = 0
      return
    }

    // Only scroll if we have new messages since last render
    const hasNewMessages = messages.length > messagesLengthRef.current
    messagesLengthRef.current = messages.length

    if (hasNewMessages && messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
    }
  }, [messages])

  // Scroll to bottom when switching channels
  useEffect(() => {
    if (messagesContainerRef.current && messages && messages.length > 0) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
    }
    // Reset the message length ref when switching channels
    messagesLengthRef.current = messages?.length || 0
  }, [selectedChannelId])

  // Compute if interactions should be disabled
  const hasUser = !!user
  const isReady = !userLoading && !channelsLoading && !dmsLoading && hasUser
  const isInteractionDisabled = !isReady

  // TODO(debug): remove readiness logger after startup stability is confirmed.
  useEffect(() => {
    if (!import.meta.env.DEV) {
      return
    }

    console.info('[ChatReadyState]', {
      isReady,
      isInteractionDisabled,
      userLoading,
      channelsLoading,
      dmsLoading,
      hasUser,
      isConnected,
    })
  }, [
    isReady,
    isInteractionDisabled,
    userLoading,
    channelsLoading,
    dmsLoading,
    hasUser,
    isConnected,
  ])

  // Auto-join default channel on first load (e.g. #general after fresh register/login)
  useEffect(() => {
    if (loaderData.defaultChannelId) {
      joinChannel(loaderData.defaultChannelId).catch(() => {
        // Already a member or channel doesn't exist — that's fine
      })
    }
  }, [loaderData.defaultChannelId])

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

  // Handle channel creation
  const handleCreateChannel = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newChannelName.trim()) return

    setIsCreatingChannel(true)
    setChannelCreateError(null)

    try {
      const name =
        newChannelType === 'public' && !newChannelName.startsWith('#')
          ? `#${newChannelName.trim()}`
          : newChannelName.trim()
      const channel = await createChannel(
        name,
        newChannelType,
        isDataProcessorChannel,
      )
      setNewChannelName('')
      setNewChannelType('public')
      setIsDataProcessorChannel(false)
      setShowCreateChannel(false)
      await refetchChannels()
      setSelectedChannelId(channel.id)
      // Auto-join the channel
      try {
        await joinChannel(channel.id)
      } catch (error) {
        console.error('Failed to join channel:', error)
      }
    } catch (error) {
      setChannelCreateError(
        error instanceof Error ? error.message : 'Failed to create channel',
      )
    } finally {
      setIsCreatingChannel(false)
    }
  }

  const handleUserClick = (user: User, event: React.MouseEvent) => {
    event.preventDefault()
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
    setContextMenu({
      user,
      position: { x: rect.left, y: rect.bottom },
    })
  }

  const handleContextMenuClose = () => setContextMenu(null)

  const handleProfile = () => {
    if (contextMenu) {
      setProfileUser(contextMenu.user)
      setContextMenu(null)
    }
  }

  const handleMessage = async () => {
    if (contextMenu) {
      try {
        const channel = await createDirectMessageChannel(contextMenu.user.id)
        setSelectedChannelId(channel.id)
        await refetchDirectMessages()
      } catch (error) {
        console.error('Failed to create DM:', error)
      }
      setContextMenu(null)
    }
  }

  const handleReplyToImage = (messageId: number, content: string) => {
    setMessageInput(content)
    messageInputRef.current?.focus()
  }

  // Handle message input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMessageInput(e.target.value)
    if (selectedChannelId && isConnected) {
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
        case 'ai':
          setChannelMode('ai')
          setMessageInput('')
          return
        case 'chat':
          setChannelMode('chat')
          setMessageInput('')
          return
        case 'game':
          setChannelMode('game')
          setMessageInput('')
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

  // Loading states - only show if we don't have initial data
  if (
    (userLoading && !loaderData.user) ||
    (channelsLoading && !loaderData.channels)
  ) {
    return (
      <div className="min-h-screen flex items-center justify-center chat-shell">
        <div className="text-lg chat-meta">Loading...</div>
      </div>
    )
  }

  // If we have no data at all, show loading
  if (!user || !channels) {
    return (
      <div className="min-h-screen flex items-center justify-center chat-shell">
        <div className="text-lg chat-meta">Loading...</div>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen flex chat-shell"
      onClick={handleContextMenuClose}
    >
      {isNavOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={() => setIsNavOpen(false)}
        />
      )}
      <aside
        className={`fixed top-0 left-0 h-full w-full sm:w-72 z-50 transform transition-transform duration-300 ease-in-out nav-drawer ${
          isNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-3 sm:p-4 border-b chat-divider">
          <div className="text-base sm:text-lg font-semibold">Navigation</div>
          <button
            onClick={() => setIsNavOpen(false)}
            className="p-2 rounded-lg chat-menu-button min-w-[44px] min-h-[44px]"
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 p-3 sm:p-4 space-y-2">
          <Link
            to="/"
            onClick={() => setIsNavOpen(false)}
            className="flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link min-h-[44px]"
            activeProps={{
              className:
                'flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link nav-link--active min-h-[44px]',
            }}
          >
            <Home size={18} />
            <span className="font-medium text-sm sm:text-base">Home</span>
          </Link>
          <Link
            to="/login"
            onClick={() => setIsNavOpen(false)}
            className="flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link min-h-[44px]"
            activeProps={{
              className:
                'flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link nav-link--active min-h-[44px]',
            }}
          >
            <LogIn size={18} />
            <span className="font-medium text-sm sm:text-base">Login</span>
          </Link>
          <Link
            to="/chat"
            onClick={() => setIsNavOpen(false)}
            className="flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link min-h-[44px]"
            activeProps={{
              className:
                'flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link nav-link--active min-h-[44px]',
            }}
          >
            <MessageSquare size={18} />
            <span className="font-medium text-sm sm:text-base">Chat</span>
          </Link>
          <Link
            to="/settings"
            onClick={() => setIsNavOpen(false)}
            className="flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link min-h-[44px]"
            activeProps={{
              className:
                'flex items-center gap-2 sm:gap-3 p-3 rounded-lg nav-link nav-link--active min-h-[44px]',
            }}
          >
            <Settings size={18} />
            <span className="font-medium text-sm sm:text-base">Settings</span>
          </Link>
        </nav>
      </aside>
      {/* Sidebar */}
      <div className="hidden md:flex md:w-64 flex-col chat-sidebar">
        {/* User info */}
        <div className="p-3 md:p-4 border-b chat-divider">
          <div className="flex items-center gap-2 md:gap-3">
            <button
              onClick={() => setIsNavOpen(true)}
              className="p-2 rounded-lg chat-menu-button min-w-[44px] min-h-[44px]"
              aria-label="Open menu"
            >
              <Menu size={18} />
            </button>
            {user?.profile_picture_url ? (
              <img
                src={user.profile_picture_url}
                alt={user.display_name || user.username}
                className="w-8 h-8 md:w-10 md:h-10 rounded-full object-cover flex-shrink-0"
              />
            ) : (
              <div className="w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center chat-avatar flex-shrink-0">
                <span className="font-bold text-xs md:text-sm">
                  {(user?.display_name || user?.username)?.[0].toUpperCase()}
                </span>
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="font-semibold text-sm md:text-base truncate">
                {user?.display_name || user?.username}
              </div>
              <div className="text-xs md:text-sm chat-meta">Online</div>
            </div>
          </div>
        </div>

        {/* Channels list */}
        <ChannelsSidebar
          channels={channels}
          directMessages={directMessages}
          selectedChannelId={selectedChannelId}
          user={user}
          dmUsersById={dmUsersById}
          isInteractionDisabled={isInteractionDisabled}
          onChannelSelect={handleChannelSelect}
          showCreateChannel={showCreateChannel}
          setShowCreateChannel={setShowCreateChannel}
          newChannelName={newChannelName}
          setNewChannelName={setNewChannelName}
          newChannelType={newChannelType}
          setNewChannelType={setNewChannelType}
          isDataProcessorChannel={isDataProcessorChannel}
          setIsDataProcessorChannel={setIsDataProcessorChannel}
          channelCreateError={channelCreateError}
          setChannelCreateError={setChannelCreateError}
          isCreatingChannel={isCreatingChannel}
          onCreateChannel={handleCreateChannel}
        />
      </div>

      {/* Mobile Channels Drawer */}
      {isChannelDrawerOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40 md:hidden"
          onClick={() => setIsChannelDrawerOpen(false)}
        />
      )}
      <aside
        className={`fixed top-0 left-0 h-full w-full sm:w-72 z-50 transform transition-transform duration-300 ease-in-out md:hidden nav-drawer flex flex-col ${
          isChannelDrawerOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-3 sm:p-4 border-b chat-divider">
          <div className="text-base sm:text-lg font-semibold">Channels</div>
          <button
            onClick={() => setIsChannelDrawerOpen(false)}
            className="p-2 rounded-lg chat-menu-button min-w-[44px] min-h-[44px]"
            aria-label="Close channels"
          >
            <X size={20} />
          </button>
        </div>
        <ChannelsSidebar
          channels={channels}
          directMessages={directMessages}
          selectedChannelId={selectedChannelId}
          user={user}
          dmUsersById={dmUsersById}
          isInteractionDisabled={isInteractionDisabled}
          onChannelSelect={handleChannelSelect}
          onClose={() => setIsChannelDrawerOpen(false)}
          showCreateChannel={showCreateChannel}
          setShowCreateChannel={setShowCreateChannel}
          newChannelName={newChannelName}
          setNewChannelName={setNewChannelName}
          newChannelType={newChannelType}
          setNewChannelType={setNewChannelType}
          isDataProcessorChannel={isDataProcessorChannel}
          setIsDataProcessorChannel={setIsDataProcessorChannel}
          channelCreateError={channelCreateError}
          setChannelCreateError={setChannelCreateError}
          isCreatingChannel={isCreatingChannel}
          onCreateChannel={handleCreateChannel}
        />
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col w-full md:w-auto">
        {/* Mobile menu button - shown only on mobile */}
        <div className="md:hidden p-2 border-b chat-header flex items-center gap-2">
          <button
            onClick={() => setIsNavOpen(true)}
            className="p-2 rounded-lg chat-menu-button min-w-[44px] min-h-[44px]"
            aria-label="Open menu"
          >
            <Menu size={18} />
          </button>
          {user?.profile_picture_url ? (
            <img
              src={user.profile_picture_url}
              alt={user.display_name || user.username}
              className="w-8 h-8 rounded-full object-cover"
            />
          ) : (
            <div className="w-8 h-8 rounded-full flex items-center justify-center chat-avatar">
              <span className="font-bold text-xs">
                {(user?.display_name || user?.username)?.[0].toUpperCase()}
              </span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-sm truncate">
              {user?.display_name || user?.username}
            </div>
          </div>
        </div>
        {selectedChannelId ? (
          <>
            {/* Channel header with mode toggle */}
            <div className="p-2 md:p-2.5 border-b chat-header">
              <div className="flex items-center justify-between gap-2 md:gap-4">
                <button
                  type="button"
                  onClick={() => setIsChannelDrawerOpen(true)}
                  className="no-touch-target flex items-center gap-2 min-w-0 flex-1 text-left md:pointer-events-none"
                >
                  <div className="w-2 h-2 rounded-full chat-dot flex-shrink-0"></div>
                  <div className="font-semibold text-sm md:text-base truncate">
                    {selectedChannel?.type === 'private' &&
                    selectedChannelOtherUser
                      ? `DM-${selectedChannelOtherUser.display_name || selectedChannelOtherUser.username}`
                      : selectedChannel?.name || `Channel ${selectedChannelId}`}
                  </div>
                  <ChevronDown size={16} className="flex-shrink-0 md:hidden" />
                </button>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => setChannelMode('chat')}
                    disabled={isInteractionDisabled}
                    className={`px-2 md:px-3 py-2 text-xs md:text-sm rounded transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed ${
                      activeMode === 'chat'
                        ? 'chat-send-button'
                        : 'chat-attach-button'
                    }`}
                  >
                    Chat
                  </button>
                  <button
                    type="button"
                    onClick={() => setChannelMode('ai')}
                    disabled={isInteractionDisabled}
                    className={`px-2 md:px-3 py-2 text-xs md:text-sm rounded transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed ${
                      activeMode === 'ai'
                        ? 'chat-send-button'
                        : 'chat-attach-button'
                    }`}
                  >
                    AI
                  </button>
                  <button
                    type="button"
                    onClick={() => setChannelMode('game')}
                    disabled={isInteractionDisabled}
                    className={`px-2 md:px-3 py-2 text-xs md:text-sm rounded transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 ${
                      activeMode === 'game'
                        ? 'chat-send-button'
                        : 'chat-attach-button'
                    }`}
                  >
                    <Gamepad2 size={14} />
                    Game
                  </button>
                </div>
              </div>
            </div>

            {/* Data Processor Channel - takes priority over mode toggle */}
            {selectedChannel?.is_data_processor ? (
              <DataProcessorChannel
                channelId={selectedChannelId}
                channelName={selectedChannel?.name || '#data-processor'}
              />
            ) : activeMode === 'ai' ? (
              <AIChannel
                channelId={selectedChannelId}
                channelName={selectedChannel?.name || '#ai'}
                showHeader={false}
                onCommand={(command) => {
                  if (command === 'chat') {
                    setChannelMode('chat')
                  }
                  if (command === 'ai') {
                    setChannelMode('ai')
                  }
                  if (command === 'game') {
                    setChannelMode('game')
                  }
                }}
              />
            ) : activeMode === 'game' ? (
              <GameChannel
                channelId={selectedChannelId}
                channelName={selectedChannel?.name || '#game'}
              />
            ) : (
              <>
                {/* Messages */}
                <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-1.5 md:p-2 touch-pan-y">
                  {messagesLoading ? (
                    <div className="text-center py-4 chat-meta text-sm">
                      Loading messages...
                    </div>
                  ) : messages?.length === 0 ? (
                    <div className="text-center py-4 chat-meta text-sm">
                      No messages yet. Start the conversation!
                    </div>
                  ) : (
                    <div className="space-y-1 md:space-y-1.5">
                      {messages?.map((message) => (
                        <MessageAvatar
                          key={message.id}
                          message={message}
                          currentUser={user}
                          onUserClick={handleUserClick}
                          onImageClick={setSelectedImageMessage}
                        />
                      ))}
                    </div>
                  )}

                  {/* Typing indicator */}
                  {typingUsers.size > 0 && (
                    <div className="flex items-center gap-1.5 md:gap-2 mt-2">
                      <div className="w-5 h-5 md:w-6 md:h-6 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                        <span className="text-[10px] font-semibold">
                          {/* Show first typing user's initial */}
                          {Array.from(typingUsers)[0] === user?.id
                            ? 'You'
                            : `User${Array.from(typingUsers)[0]}`[0].toUpperCase()}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 flex-wrap">
                        <div className="text-xs chat-typing">
                          {Array.from(typingUsers)
                            .map((userId) =>
                              userId === user?.id ? 'You' : `User${userId}`,
                            )
                            .join(', ')}{' '}
                          is typing...
                        </div>
                        <div className="flex gap-0.5">
                          <div className="w-1.5 h-1.5 rounded-full bg-amber-700/50 animate-bounce"></div>
                          <div
                            className="w-1.5 h-1.5 rounded-full bg-amber-700/50 animate-bounce"
                            style={{ animationDelay: '0.1s' }}
                          ></div>
                          <div
                            className="w-1.5 h-1.5 rounded-full bg-amber-700/50 animate-bounce"
                            style={{ animationDelay: '0.2s' }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Message input */}
                <div className="p-1.5 md:p-2 border-t chat-input-bar">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <form
                    onSubmit={handleSubmit}
                    className="flex flex-col sm:flex-row gap-2 relative"
                  >
                    <div className="flex gap-2 flex-1 min-w-0">
                      <button
                        type="button"
                        onClick={handleAttachmentClick}
                        disabled={
                          isInteractionDisabled ||
                          !selectedChannelId ||
                          isUploading
                        }
                        className="px-3 py-2 rounded-lg transition-colors chat-attach-button disabled:opacity-60 min-h-[44px] text-sm md:text-base flex-shrink-0"
                      >
                        Attach
                      </button>
                      <div className="flex-1 relative min-w-0">
                        <input
                          ref={messageInputRef}
                          type="text"
                          value={messageInput}
                          onChange={handleInputChange}
                          placeholder="Type your message..."
                          disabled={isInteractionDisabled}
                          className="w-full px-3 md:px-4 py-2 rounded-lg transition-all chat-input min-h-[44px] text-sm md:text-base disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                        <MentionAutocomplete
                          channelId={selectedChannelId}
                          inputValue={messageInput}
                          onInputChange={setMessageInput}
                          inputRef={messageInputRef}
                        />
                      </div>
                    </div>
                    <button
                      type="submit"
                      disabled={
                        isInteractionDisabled ||
                        !messageInput.trim() ||
                        !selectedChannelId
                      }
                      className="px-4 py-2 font-semibold rounded-lg transition-colors chat-send-button disabled:opacity-60 min-h-[44px] text-sm md:text-base w-full sm:w-auto flex-shrink-0"
                    >
                      Send
                    </button>
                  </form>
                  {(isUploading || uploadError) && (
                    <div className="mt-2 text-xs md:text-sm chat-meta">
                      {isUploading ? 'Uploading image...' : uploadError}
                    </div>
                  )}
                </div>
              </>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center chat-meta text-sm md:text-base px-4 text-center">
            Select a channel to start chatting
          </div>
        )}
      </div>
      {profileUser && (
        <UserProfileModal
          user={profileUser}
          onClose={() => setProfileUser(null)}
        />
      )}
      {contextMenu && (
        <UserContextMenu
          position={contextMenu.position}
          user={contextMenu.user}
          onClose={handleContextMenuClose}
          onProfile={handleProfile}
          onMessage={handleMessage}
        />
      )}
      {selectedImageMessage && (
        <ImagePopup
          message={selectedImageMessage}
          currentUser={user}
          onClose={() => setSelectedImageMessage(null)}
          onReply={handleReplyToImage}
          senderName={
            selectedImageMessage.sender_id === user?.id
              ? 'You'
              : messages?.find(m => m.id === selectedImageMessage.id)?.username ||
                messages?.find(m => m.id === selectedImageMessage.id)?.display_name ||
                `User${selectedImageMessage.sender_id}`
          }
        />
      )}
    </div>
  )
}
