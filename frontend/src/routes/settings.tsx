import { useState, useRef, useEffect } from 'react'
import { createFileRoute, useNavigate, redirect } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getCurrentUser,
  getChannels,
  updateUserProfile,
  uploadImage,
  createChannel,
  searchUsers,
  addUserToChannel,
} from '../api'
import {
  getCurrentUserServer,
  getChannelsServer,
} from '../api/server'
import { useUserProfileInvalidation } from '../hooks/useUserProfileInvalidation'
import type { User, Channel } from '../types'
import { Settings as SettingsIcon, Upload, X, Search, Plus } from 'lucide-react'

export const Route = createFileRoute('/settings')({
  ssr: true, // Full SSR - render components on server
  loader: async () => {
    try {
      const [currentUser, channels] = await Promise.all([
        getCurrentUserServer(),
        getChannelsServer(),
      ])
      return { currentUser, channels }
    } catch (error) {
      // Redirect to login if not authenticated
      throw redirect({ to: '/login' })
    }
  },
  headers: () => ({
    'Cache-Control': 'private, max-age=30', // User-specific, shorter cache
  }),
  staleTime: 15_000,
  component: SettingsPage,
})

function SettingsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const loaderData = Route.useLoaderData()

  // Use the invalidation hook
  useUserProfileInvalidation()

  // Current user query - hydrate from loader data
  const {
    data: currentUser,
    isLoading: userLoading,
    error: userError,
  } = useQuery<User>({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
    initialData: loaderData.currentUser,
    staleTime: 15_000,
  })

  // Channels query - hydrate from loader data
  const { data: channels } = useQuery<Channel[]>({
    queryKey: ['channels'],
    queryFn: getChannels,
    initialData: loaderData.channels,
    staleTime: 15_000,
  })

  // Profile picture state
  const [profilePreview, setProfilePreview] = useState<string | null>(null)
  const [isUploadingProfile, setIsUploadingProfile] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)

  // Display name state
  const [newDisplayName, setNewDisplayName] = useState('')
  const [isUpdatingDisplayName, setIsUpdatingDisplayName] = useState(false)
  const [displayNameError, setDisplayNameError] = useState<string | null>(null)

  // Channel creation state
  const [channelName, setChannelName] = useState('')
  const [channelType, setChannelType] = useState<'public' | 'private'>('public')
  const [channelError, setChannelError] = useState<string | null>(null)

  // Add user to channel state
  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(
    null,
  )
  const [usernameSearch, setUsernameSearch] = useState('')
  const [searchResults, setSearchResults] = useState<User[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [isAddingUser, setIsAddingUser] = useState(false)
  const [addUserError, setAddUserError] = useState<string | null>(null)

  // Initialize display name field
  useEffect(() => {
    if (currentUser) {
      setNewDisplayName(currentUser.display_name || currentUser.username)
    }
  }, [currentUser])

  // Handle user not authenticated
  useEffect(() => {
    if (userError) {
      navigate({ to: '/login' })
    }
  }, [userError, navigate])

  // Search users debounced
  useEffect(() => {
    if (!usernameSearch.trim() || usernameSearch.length < 2) {
      setSearchResults([])
      return
    }

    const timeoutId = setTimeout(async () => {
      setIsSearching(true)
      try {
        const results = await searchUsers(usernameSearch)
        setSearchResults(results)
      } catch (error) {
        console.error('Failed to search users:', error)
        setSearchResults([])
      } finally {
        setIsSearching(false)
      }
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [usernameSearch])

  // Profile picture upload mutation
  const profileUpdateMutation = useMutation({
    mutationFn: (profilePictureUrl: string | null) =>
      updateUserProfile(undefined, profilePictureUrl),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentUser'] })
      setProfilePreview(null)
      setProfileError(null)
    },
    onError: (error: Error) => {
      setProfileError(error.message)
    },
  })

  // Display name update mutation
  const displayNameUpdateMutation = useMutation({
    mutationFn: (displayName: string) =>
      updateUserProfile(displayName, undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentUser'] })
      setDisplayNameError(null)
    },
    onError: (error: Error) => {
      setDisplayNameError(error.message)
    },
  })

  // Channel creation mutation
  const channelCreateMutation = useMutation({
    mutationFn: ({
      name,
      type,
    }: {
      name: string
      type: 'public' | 'private'
    }) => createChannel(name, type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      setChannelName('')
      setChannelType('public')
      setChannelError(null)
    },
    onError: (error: Error) => {
      setChannelError(error.message)
    },
  })

  // Add user to channel mutation
  const addUserMutation = useMutation({
    mutationFn: ({
      channelId,
      username,
    }: {
      channelId: number
      username: string
    }) => addUserToChannel(channelId, username),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      setUsernameSearch('')
      setSearchResults([])
      setSelectedChannelId(null)
      setAddUserError(null)
    },
    onError: (error: Error) => {
      setAddUserError(error.message)
    },
  })

  const handleProfilePictureSelect = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setProfileError('Please select an image file')
      return
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setProfileError('Image size must be less than 10MB')
      return
    }

    // Create preview
    const reader = new FileReader()
    reader.onloadend = () => {
      setProfilePreview(reader.result as string)
    }
    reader.readAsDataURL(file)
  }

  const handleProfilePictureUpload = async () => {
    const file = fileInputRef.current?.files?.[0]
    if (!file) return

    setIsUploadingProfile(true)
    setProfileError(null)

    try {
      const uploadResult = await uploadImage(file)
      profileUpdateMutation.mutate(uploadResult.url)
    } catch (error) {
      setProfileError(
        error instanceof Error ? error.message : 'Failed to upload image',
      )
    } finally {
      setIsUploadingProfile(false)
    }
  }

  const handleRemoveProfilePicture = () => {
    profileUpdateMutation.mutate(null)
  }

  const handleDisplayNameUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (
      !newDisplayName.trim() ||
      newDisplayName === (currentUser?.display_name || currentUser?.username)
    )
      return

    setIsUpdatingDisplayName(true)
    setDisplayNameError(null)

    try {
      displayNameUpdateMutation.mutate(newDisplayName.trim())
    } catch (error) {
      // Error handled by mutation
    } finally {
      setIsUpdatingDisplayName(false)
    }
  }

  const handleCreateChannel = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!channelName.trim()) return

    setChannelError(null)

    const name =
      channelType === 'public' && !channelName.startsWith('#')
        ? `#${channelName.trim()}`
        : channelName.trim()
    channelCreateMutation.mutate({ name, type: channelType })
  }

  const handleAddUserToChannel = async (username: string) => {
    if (!selectedChannelId) return

    setIsAddingUser(true)
    setAddUserError(null)

    try {
      addUserMutation.mutate({ channelId: selectedChannelId, username })
    } catch (error) {
      // Error handled by mutation
    } finally {
      setIsAddingUser(false)
    }
  }

  if (userLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center chat-shell">
        <div className="text-lg chat-meta">Loading...</div>
      </div>
    )
  }

  if (!currentUser) {
    return null
  }

  const displayProfilePicture =
    profilePreview || currentUser.profile_picture_url

  return (
    <div className="min-h-screen chat-shell p-4 sm:p-6">
      <div className="max-w-4xl mx-auto space-y-4 md:space-y-6">
        <h1 className="text-2xl sm:text-3xl font-bold chat-message-text mb-4 md:mb-6">Settings</h1>

        {/* Profile Picture Section */}
        <div className="chat-card p-4 sm:p-6 rounded-xl">
          <h2 className="text-lg sm:text-xl font-semibold chat-message-text mb-4">
            Profile Picture
          </h2>

          <div className="flex flex-col sm:flex-row items-start gap-4 sm:gap-6">
            <div className="flex-shrink-0 mx-auto sm:mx-0">
              {displayProfilePicture ? (
                <div className="relative">
                  <img
                    src={displayProfilePicture}
                    alt="Profile"
                    className="w-24 h-24 sm:w-32 sm:h-32 rounded-full object-cover border-2 border-solid"
                    style={{ borderColor: 'rgba(212, 163, 115, 0.5)' }}
                  />
                  {currentUser.profile_picture_url && (
                    <button
                      onClick={handleRemoveProfilePicture}
                      className="absolute -top-2 -right-2 p-1 rounded-full chat-menu-button min-w-[44px] min-h-[44px]"
                      aria-label="Remove profile picture"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              ) : (
                <div className="w-24 h-24 sm:w-32 sm:h-32 rounded-full flex items-center justify-center chat-avatar text-3xl sm:text-4xl font-bold">
                  {currentUser.username[0].toUpperCase()}
                </div>
              )}
            </div>

            <div className="flex-1 w-full sm:w-auto">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleProfilePictureSelect}
                className="hidden"
              />

              <div className="space-y-3">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploadingProfile}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors chat-attach-button disabled:opacity-60 min-h-[44px] w-full sm:w-auto justify-center"
                >
                  <Upload size={18} />
                  <span className="text-sm sm:text-base">{profilePreview ? 'Change Picture' : 'Upload Picture'}</span>
                </button>

                {profilePreview && (
                  <div className="flex flex-col sm:flex-row gap-2">
                    <button
                      onClick={handleProfilePictureUpload}
                      disabled={isUploadingProfile}
                      className="px-4 py-2 rounded-lg transition-colors chat-send-button disabled:opacity-60 min-h-[44px] text-sm sm:text-base"
                    >
                      {isUploadingProfile ? 'Uploading...' : 'Save'}
                    </button>
                    <button
                      onClick={() => {
                        setProfilePreview(null)
                        if (fileInputRef.current) {
                          fileInputRef.current.value = ''
                        }
                      }}
                      className="px-4 py-2 rounded-lg transition-colors chat-menu-button min-h-[44px] text-sm sm:text-base"
                    >
                      Cancel
                    </button>
                  </div>
                )}

                {profileError && (
                  <div className="text-sm text-red-600">{profileError}</div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Display Name Section */}
        <div className="chat-card p-4 sm:p-6 rounded-xl">
          <h2 className="text-lg sm:text-xl font-semibold chat-message-text mb-4">
            Display Name
          </h2>

          <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <p className="text-sm chat-message-text">
              <strong>Registered Username:</strong> {currentUser.username}
            </p>
            <p className="text-xs chat-meta mt-1">
              This is your login name and cannot be changed. The display name is
              what others see.
            </p>
          </div>

          <form onSubmit={handleDisplayNameUpdate} className="space-y-4">
            <div>
              <label
                htmlFor="displayName"
                className="block text-sm font-semibold mb-2 chat-message-text"
              >
                Display Name
              </label>
              <input
                type="text"
                id="displayName"
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
                className="w-full px-4 py-2 rounded-lg transition-all chat-input min-h-[44px] text-base"
                placeholder="Enter display name"
                required
                minLength={1}
                maxLength={50}
              />
            </div>

            {displayNameError && (
              <div className="text-sm text-red-600">{displayNameError}</div>
            )}

            <button
              type="submit"
              disabled={
                isUpdatingDisplayName ||
                newDisplayName.trim() ===
                  (currentUser.display_name || currentUser.username)
              }
              className="px-4 py-2 rounded-lg transition-colors chat-send-button disabled:opacity-60 min-h-[44px] text-sm sm:text-base w-full sm:w-auto"
            >
              {isUpdatingDisplayName ? 'Updating...' : 'Update Display Name'}
            </button>
          </form>
        </div>

        {/* Create Channel Section */}
        <div className="chat-card p-4 sm:p-6 rounded-xl">
          <h2 className="text-lg sm:text-xl font-semibold chat-message-text mb-4">
            Create Channel
          </h2>

          <form onSubmit={handleCreateChannel} className="space-y-4">
            <div>
              <label
                htmlFor="channelName"
                className="block text-sm font-semibold mb-2 chat-message-text"
              >
                Channel Name
              </label>
              <input
                type="text"
                id="channelName"
                value={channelName}
                onChange={(e) => setChannelName(e.target.value)}
                className="w-full px-4 py-2 rounded-lg transition-all chat-input min-h-[44px] text-base"
                placeholder={
                  channelType === 'public' ? '#channel-name' : 'Channel name'
                }
                required
              />
            </div>

            <div>
              <label
                htmlFor="channelType"
                className="block text-sm font-semibold mb-2 chat-message-text"
              >
                Channel Type
              </label>
              <select
                id="channelType"
                value={channelType}
                onChange={(e) =>
                  setChannelType(e.target.value as 'public' | 'private')
                }
                className="w-full px-4 py-2 rounded-lg transition-all chat-input min-h-[44px] text-base"
              >
                <option value="public">Public</option>
                <option value="private">Private</option>
              </select>
            </div>

            {channelError && (
              <div className="text-sm text-red-600">{channelError}</div>
            )}

            <button
              type="submit"
              disabled={channelCreateMutation.isPending || !channelName.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors chat-send-button disabled:opacity-60 min-h-[44px] text-sm sm:text-base w-full sm:w-auto justify-center"
            >
              <Plus size={18} />
              {channelCreateMutation.isPending ? 'Creating...' : 'Create Channel'}
            </button>
          </form>
        </div>

        {/* Add Users to Channel Section */}
        <div className="chat-card p-4 sm:p-6 rounded-xl">
          <h2 className="text-lg sm:text-xl font-semibold chat-message-text mb-4">
            Add Users to Channel
          </h2>

          <div className="space-y-4">
            <div>
              <label
                htmlFor="channelSelect"
                className="block text-sm font-semibold mb-2 chat-message-text"
              >
                Select Channel
              </label>
              <select
                id="channelSelect"
                value={selectedChannelId || ''}
                onChange={(e) =>
                  setSelectedChannelId(
                    e.target.value ? parseInt(e.target.value) : null,
                  )
                }
                className="w-full px-4 py-2 rounded-lg transition-all chat-input min-h-[44px] text-base"
              >
                <option value="">Choose a channel...</option>
                {channels
                  ?.filter((ch) => ch.type === 'public')
                  .map((channel) => (
                    <option key={channel.id} value={channel.id}>
                      {channel.name}
                    </option>
                  ))}
              </select>
            </div>

            {selectedChannelId && (
              <>
                <div>
                  <label
                    htmlFor="usernameSearch"
                    className="block text-sm font-semibold mb-2 chat-message-text"
                  >
                    Search Users by Username
                  </label>
                  <div className="relative">
                    <Search
                      className="absolute left-3 top-1/2 transform -translate-y-1/2 chat-meta"
                      size={18}
                    />
                    <input
                      type="text"
                      id="usernameSearch"
                      value={usernameSearch}
                      onChange={(e) => setUsernameSearch(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 rounded-lg transition-all chat-input min-h-[44px] text-base"
                      placeholder="Type username to search..."
                    />
                  </div>

                  {isSearching && (
                    <div className="mt-2 text-sm chat-meta">Searching...</div>
                  )}

                  {searchResults.length > 0 && (
                    <div className="mt-2 border rounded-lg chat-divider overflow-hidden max-h-64 overflow-y-auto">
                      {searchResults.map((user) => (
                        <button
                          key={user.id}
                          onClick={() => handleAddUserToChannel(user.username)}
                          disabled={isAddingUser}
                          className="w-full px-3 sm:px-4 py-2 sm:py-3 text-left hover:bg-opacity-50 transition-colors chat-channel-item flex items-center gap-2 sm:gap-3 min-h-[44px]"
                        >
                          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 chat-avatar">
                            {user.profile_picture_url ? (
                              <img
                                src={user.profile_picture_url}
                                alt={user.display_name || user.username}
                                className="w-full h-full rounded-full object-cover"
                              />
                            ) : (
                              <span className="text-xs font-semibold">
                                {(user.display_name ||
                                  user.username)?.[0].toUpperCase()}
                              </span>
                            )}
                          </div>
                          <span className="text-sm sm:text-base truncate">{user.display_name || user.username}</span>
                        </button>
                      ))}
                    </div>
                  )}

                  {usernameSearch.length >= 2 &&
                    !isSearching &&
                    searchResults.length === 0 && (
                      <div className="mt-2 text-sm chat-meta">
                        No users found
                      </div>
                    )}
                </div>

                {addUserError && (
                  <div className="text-sm text-red-600">{addUserError}</div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
