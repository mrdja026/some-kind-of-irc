import { useState, useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getCurrentUser,
  getChannels,
  getDirectMessages,
  getMessages,
  sendMessage,
  joinChannel,
  createDirectMessageChannel,
  getUserById,
  searchChannels,
} from '../api'
import { useChatSocket } from '../hooks/useChatSocket'
import type { Channel, Message, User } from '../types'

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
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-white text-lg">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-900 flex">
      {/* Sidebar */}
      <div className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
        {/* User info */}
        <div className="p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-cyan-500 flex items-center justify-center">
              <span className="text-white font-bold">
                {user?.username[0].toUpperCase()}
              </span>
            </div>
            <div>
              <div className="text-white font-medium">{user?.username}</div>
              <div className="text-sm text-green-500">Online</div>
            </div>
          </div>
        </div>

        {/* Channels list */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="text-xs text-slate-400 uppercase tracking-wider font-medium px-3 py-2">
            Channels
          </div>
          {channels
            ?.filter((ch) => ch.type === 'public')
            .map((channel) => (
              <div
                key={channel.id}
                onClick={() => handleChannelSelect(channel)}
                className={`px-3 py-2 rounded cursor-pointer transition-colors ${
                  selectedChannelId === channel.id
                    ? 'bg-cyan-500/10 text-cyan-400'
                    : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                {channel.name}
              </div>
            ))}

          {/* Direct Messages */}
          <div className="text-xs text-slate-400 uppercase tracking-wider font-medium px-3 py-2 mt-4">
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
                className={`px-3 py-2 rounded cursor-pointer transition-colors ${
                  selectedChannelId === dmChannel.id
                    ? 'bg-cyan-500/10 text-cyan-400'
                    : 'text-slate-300 hover:bg-slate-700'
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
                className="flex-1 px-3 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
              />
              <button
                type="submit"
                disabled={!dmUserIdInput.trim()}
                className="px-3 py-1 bg-cyan-500 hover:bg-cyan-600 disabled:bg-cyan-500/50 text-white text-sm font-medium rounded transition-colors"
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
            <div className="p-4 border-b border-slate-700">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-cyan-500"></div>
                <div className="text-white font-medium">
                  {channels?.find((c) => c.id === selectedChannelId)?.name}
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4">
              {messagesLoading ? (
                <div className="text-white text-center py-8">
                  Loading messages...
                </div>
              ) : messages?.length === 0 ? (
                <div className="text-slate-400 text-center py-8">
                  No messages yet. Start the conversation!
                </div>
              ) : (
                <div className="space-y-4">
                  {messages?.map((message) => (
                    <div key={message.id} className="flex gap-3">
                      <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0">
                        <span className="text-white text-xs">
                          {/* Show sender's initial */}
                          {message.sender_id === user?.id
                            ? 'You'
                            : `User${message.sender_id}`[0].toUpperCase()}
                        </span>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <div className="text-sm text-white font-medium">
                            {message.sender_id === user?.id
                              ? 'You'
                              : `User${message.sender_id}`}
                          </div>
                          <div className="text-xs text-slate-400">
                            {new Date(message.timestamp).toLocaleTimeString()}
                          </div>
                        </div>
                        <div className="text-slate-300 mt-1">
                          {message.content}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Typing indicator */}
              {typingUsers.size > 0 && (
                <div className="flex items-center gap-3 mt-4">
                  <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-white text-xs">
                      {/* Show first typing user's initial */}
                      {Array.from(typingUsers)[0] === user?.id
                        ? 'You'
                        : `User${Array.from(typingUsers)[0]}`[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="text-slate-400 text-sm">
                      {Array.from(typingUsers)
                        .map((userId) =>
                          userId === user?.id ? 'You' : `User${userId}`,
                        )
                        .join(', ')}{' '}
                      is typing...
                    </div>
                    <div className="flex gap-1">
                      <div className="w-2 h-2 rounded-full bg-slate-400 animate-bounce"></div>
                      <div
                        className="w-2 h-2 rounded-full bg-slate-400 animate-bounce"
                        style={{ animationDelay: '0.1s' }}
                      ></div>
                      <div
                        className="w-2 h-2 rounded-full bg-slate-400 animate-bounce"
                        style={{ animationDelay: '0.2s' }}
                      ></div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Message input */}
            <div className="p-4 border-t border-slate-700">
              <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                  type="text"
                  value={messageInput}
                  onChange={handleInputChange}
                  placeholder="Type your message..."
                  className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                />
                <button
                  type="submit"
                  disabled={!messageInput.trim() || !selectedChannelId}
                  className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:bg-cyan-500/50 text-white font-medium rounded-lg transition-colors"
                >
                  Send
                </button>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-400">
            Select a channel to start chatting
          </div>
        )}
      </div>
    </div>
  )
}
