import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getCurrentUser } from '../api'
import type { GameState, GameCommandResponse, User } from '../types'
import {
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Sword,
  Heart,
} from 'lucide-react'

const API_BASE_URL =
  import.meta.env.VITE_PUBLIC_API_URL ||
  import.meta.env.VITE_API_URL ||
  'http://localhost:8002'

interface GameChannelProps {
  channelId: number
  channelName: string
}

// API functions for game
async function getGameCommands(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/game/commands`, {
    credentials: 'include',
  })
  if (!response.ok) throw new Error('Failed to fetch game commands')
  const data = await response.json()
  return data.commands
}

async function getMyGameState(): Promise<GameState> {
  const response = await fetch(`${API_BASE_URL}/game/state`, {
    credentials: 'include',
  })
  if (!response.ok) throw new Error('Failed to fetch game state')
  return response.json()
}

async function getChannelGameStates(channelId: number): Promise<GameState[]> {
  const response = await fetch(
    `${API_BASE_URL}/game/channel/${channelId}/states`,
    {
      credentials: 'include',
    },
  )
  if (!response.ok) throw new Error('Failed to fetch channel game states')
  return response.json()
}

async function executeGameCommand(
  command: string,
  targetUsername?: string,
  channelId?: number,
): Promise<GameCommandResponse> {
  const response = await fetch(`${API_BASE_URL}/game/command`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      command,
      target_username: targetUsername,
      channel_id: channelId,
    }),
  })
  if (!response.ok) throw new Error('Failed to execute command')
  return response.json()
}

async function joinGameChannel(channelId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/game/join/${channelId}`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!response.ok) throw new Error('Failed to join game channel')
}

export function GameChannel({ channelId, channelName }: GameChannelProps) {
  const queryClient = useQueryClient()
  const [targetUsername, setTargetUsername] = useState('')
  const [actionLog, setActionLog] = useState<string[]>([])
  const [isExecuting, setIsExecuting] = useState(false)

  // Fetch current user
  const { data: user } = useQuery<User>({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
  })

  // Fetch available commands
  const { data: commands } = useQuery<string[]>({
    queryKey: ['gameCommands'],
    queryFn: getGameCommands,
  })

  // Fetch my game state
  const { data: myGameState, refetch: refetchMyState } = useQuery<GameState>({
    queryKey: ['myGameState'],
    queryFn: getMyGameState,
    enabled: !!user,
    staleTime: 0, // Treat as immediately stale for game state
    refetchInterval: 500, // Poll every 500ms for responsive gameplay
  })

  // Fetch all players in channel
  const { data: channelStates, refetch: refetchChannelStates } = useQuery<
    GameState[]
  >({
    queryKey: ['channelGameStates', channelId],
    queryFn: () => getChannelGameStates(channelId),
    enabled: !!channelId,
    staleTime: 0, // Treat as immediately stale
    refetchInterval: 500, // Poll every 500ms for responsive gameplay
  })

  // Join game channel on mount
  useEffect(() => {
    if (channelId) {
      joinGameChannel(channelId).catch(console.error)
    }
  }, [channelId])

  const executeCommand = async (command: string) => {
    if (isExecuting) return
    setIsExecuting(true)

    try {
      const target = ['attack'].includes(command)
        ? targetUsername || undefined
        : undefined
      const result = await executeGameCommand(command, target, channelId)

      if (result.success) {
        setActionLog((prev) => [...prev.slice(-9), `✓ ${result.message}`])
        // Refetch states
        await Promise.all([refetchMyState(), refetchChannelStates()])
      } else {
        setActionLog((prev) => [...prev.slice(-9), `✗ ${result.error}`])
      }
    } catch (error) {
      setActionLog((prev) => [...prev.slice(-9), `✗ Error: ${error}`])
    } finally {
      setIsExecuting(false)
    }
  }

  // Grid visualization - show full 64x64 grid
  const gridSize = 64 // Full 64x64 visible grid
  const showInfiniteGrid = false // Static grid view

  // Get current user's state from channelStates for consistency
  const currentUserState = channelStates?.find((s) => s.user_id === user?.id)

  // Use channelStates position as single source of truth for grid centering
  const effectiveGameState = currentUserState || myGameState

  const getVisibleGrid = () => {
    if (!channelStates) return []

    const grid: (GameState | null)[][] = []

    for (let y = 0; y < gridSize; y++) {
      const row: (GameState | null)[] = []
      for (let x = 0; x < gridSize; x++) {
        // Full 64x64 grid - show all coordinates (0-63, 0-63)
        const worldX = x
        const worldY = y

        // Check if any player is at this position
        const player = channelStates.find(
          (s) => s.position_x === worldX && s.position_y === worldY,
        )
        row.push(player || null)
      }
      grid.push(row)
    }

    return grid
  }

  const visibleGrid = getVisibleGrid()

  return (
    <div className="flex flex-col h-full">
      {/* Game Header */}
      <div className="p-4 border-b chat-divider">
        <h2 className="text-lg font-bold">{channelName} - Game Mode</h2>
        <p className="text-sm chat-meta">
          Available commands: {commands?.join(', ') || 'Loading...'}
        </p>
      </div>

      <div className="flex-1 flex flex-col md:flex-row gap-4 p-4 overflow-auto">
        {/* Game Grid */}
        <div className="flex-1 flex flex-col items-center">
          <div className="mb-4 text-center">
            <div className="text-sm font-semibold">
              Position: ({effectiveGameState?.position_x ?? '?'},{' '}
              {effectiveGameState?.position_y ?? '?'})
            </div>
            <div className="text-sm">
              Health: {effectiveGameState?.health ?? '?'}/
              {effectiveGameState?.max_health ?? '?'}
            </div>
          </div>

          {/* Grid Visualization */}
          <div className="border rounded p-1 max-h-96 overflow-auto">
            <div className="text-xs text-gray-600 mb-2 text-center">
              Full 64×64 Game Grid (scroll to navigate)
            </div>
            <div
              className="grid gap-px"
              style={{
                gridTemplateColumns: `repeat(${gridSize}, minmax(0, 1fr))`,
                width: 'fit-content',
              }}
            >
              {visibleGrid.map((row, y) =>
                row.map((cell, x) => {
                  const isCurrentUser = cell?.user_id === user?.id

                  return (
                    <div
                      key={`${x}-${y}`}
                      className={`w-3 h-3 flex items-center justify-center text-[8px] font-bold ${
                        cell
                          ? isCurrentUser
                            ? 'bg-green-500 text-white'
                            : 'bg-red-500 text-white'
                          : 'bg-gray-100'
                      }`}
                      title={
                        cell
                          ? `${cell.display_name || cell.username} (HP: ${cell.health})`
                          : `(${x}, ${y})`
                      }
                    >
                      {cell
                        ? (cell.display_name ||
                            cell.username)?.[0]?.toUpperCase()
                        : ''}
                    </div>
                  )
                }),
              )}
            </div>
          </div>

          {/* Player List */}
          <div className="mt-4 w-full max-w-xs">
            <h3 className="font-semibold text-sm mb-2">Players in Channel:</h3>
            <div className="space-y-1">
              {channelStates?.map((state) => (
                <div
                  key={state.user_id}
                  className={`flex justify-between text-sm p-1 rounded ${
                    state.user_id === user?.id ? 'bg-green-100' : 'bg-gray-100'
                  }`}
                >
                  <span>{state.display_name || state.username}</span>
                  <span>
                    HP: {state.health}/{state.max_health}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="w-full md:w-64 flex flex-col gap-4">
          {/* Movement Controls */}
          <div className="flex flex-col items-center gap-2">
            <h3 className="font-semibold text-sm">Movement</h3>
            <div className="grid grid-cols-3 gap-1">
              <div />
              <button
                onClick={() => executeCommand('move up')}
                disabled={isExecuting}
                className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
                title="Move Up"
              >
                <ArrowUp size={20} />
              </button>
              <div />
              <button
                onClick={() => executeCommand('move left')}
                disabled={isExecuting}
                className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
                title="Move Left"
              >
                <ArrowLeft size={20} />
              </button>
              <div className="p-3 flex items-center justify-center text-xs">
                {effectiveGameState?.position_x},
                {effectiveGameState?.position_y}
              </div>
              <button
                onClick={() => executeCommand('move right')}
                disabled={isExecuting}
                className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
                title="Move Right"
              >
                <ArrowRight size={20} />
              </button>
              <div />
              <button
                onClick={() => executeCommand('move down')}
                disabled={isExecuting}
                className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
                title="Move Down"
              >
                <ArrowDown size={20} />
              </button>
              <div />
            </div>
          </div>

          {/* Action Controls */}
          <div className="flex flex-col gap-2">
            <h3 className="font-semibold text-sm">Actions</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={targetUsername}
                onChange={(e) => setTargetUsername(e.target.value)}
                placeholder="Target @username"
                className="flex-1 px-2 py-1 text-sm border rounded"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => executeCommand('attack')}
                disabled={isExecuting || !targetUsername}
                className="flex-1 p-2 rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 flex items-center justify-center gap-2"
                title="Attack target"
              >
                <Sword size={16} />
                Attack
              </button>
              <button
                onClick={() => executeCommand('heal')}
                disabled={isExecuting}
                className="flex-1 p-2 rounded bg-green-500 text-white hover:bg-green-600 disabled:opacity-50 flex items-center justify-center gap-2"
                title="Heal yourself"
              >
                <Heart size={16} />
                Heal
              </button>
            </div>
          </div>

          {/* Action Log */}
          <div className="flex-1 flex flex-col">
            <h3 className="font-semibold text-sm mb-2">Action Log</h3>
            <div className="flex-1 bg-gray-100 rounded p-2 text-xs space-y-1 max-h-40 overflow-y-auto">
              {actionLog.length === 0 ? (
                <div className="text-gray-500">No actions yet</div>
              ) : (
                actionLog.map((log, i) => (
                  <div
                    key={i}
                    className={
                      log.startsWith('✓') ? 'text-green-600' : 'text-red-600'
                    }
                  >
                    {log}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
