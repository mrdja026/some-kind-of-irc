import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getCurrentUser } from '../api'
import type { User, Player, GameSnapshotPayload, Obstacle, BattlefieldProp } from '../types'
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
  sendGameCommand: (channelId: number, command: string, targetUsername?: string) => void
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

async function joinGameChannel(channelId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/game/join/${channelId}`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!response.ok) throw new Error('Failed to join game channel')
}

export function GameChannel({ channelId, channelName, sendGameCommand }: GameChannelProps) {
  const [targetUsername, setTargetUsername] = useState('')
  const [actionLog] = useState<string[]>([])
  
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

  // Get players from query cache (populated by WebSocket)
  const { data: players } = useQuery<Player[]>({
    queryKey: ['channelGameStates', channelId],
    queryFn: async () => [],
    enabled: false, // Purely client-side cache
    initialData: [],
  })

  const { data: snapshot } = useQuery<GameSnapshotPayload | undefined>({
    queryKey: ['gameSnapshot', channelId],
    queryFn: async () => undefined,
    enabled: false,
  })

  // Join game channel on mount
  useEffect(() => {
    if (channelId) {
      joinGameChannel(channelId).catch(console.error)
    }
  }, [channelId])

  const executeCommand = (command: string) => {
    if (!channelId) return
    
    const target = ['attack'].includes(command)
      ? targetUsername || undefined
      : undefined
      
    // Send via WebSocket - no awaiting result here, feedback comes via WS events
    sendGameCommand(channelId, command, target)
    
    // Optimistic log (or wait for action_result)
    // setActionLog((prev) => [...prev.slice(-9), `> ${command}`])
  }

  // Grid visualization - show full 64x64 grid
  const gridSize = 64 // Full 64x64 visible grid

  const obstacles: Obstacle[] = snapshot?.obstacles || []
  const battlefieldProps: BattlefieldProp[] = snapshot?.battlefield?.props || []
  const bufferTiles = snapshot?.battlefield?.buffer?.tiles || []

  const playersByPosition = useMemo(() => {
    const map = new Map<string, Player>()
    for (const player of players || []) {
      map.set(`${player.position.x}:${player.position.y}`, player)
    }
    return map
  }, [players])

  const obstaclesByPosition = useMemo(() => {
    const map = new Map<string, Obstacle>()
    for (const obstacle of obstacles) {
      map.set(`${obstacle.position.x}:${obstacle.position.y}`, obstacle)
    }
    return map
  }, [obstacles])

  const propsByPosition = useMemo(() => {
    const map = new Map<string, BattlefieldProp>()
    for (const prop of battlefieldProps) {
      map.set(`${prop.position.x}:${prop.position.y}`, prop)
    }
    return map
  }, [battlefieldProps])

  const bufferPositionSet = useMemo(() => {
    const set = new Set<string>()
    for (const tile of bufferTiles) {
      set.add(`${tile.x}:${tile.y}`)
    }
    return set
  }, [bufferTiles])

  // Get current user's state from players list
  const currentUserState = players?.find((s) => s.user_id === user?.id)

  type GridCell = {
    player: Player | null
    obstacle: Obstacle | null
    prop: BattlefieldProp | null
    isBuffer: boolean
  }

  const getVisibleGrid = () => {
    const grid: GridCell[][] = []

    for (let y = 0; y < gridSize; y++) {
      const row: GridCell[] = []
      for (let x = 0; x < gridSize; x++) {
        const key = `${x}:${y}`
        row.push({
          player: playersByPosition.get(key) || null,
          obstacle: obstaclesByPosition.get(key) || null,
          prop: propsByPosition.get(key) || null,
          isBuffer: bufferPositionSet.has(key),
        })
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
        <p className="text-sm chat-meta">
          Battlefield: players {players?.length || 0}, obstacles {obstacles.length}, props {battlefieldProps.length}, buffer markers {bufferTiles.length}
        </p>
      </div>

      <div className="flex-1 flex flex-col md:flex-row gap-4 p-4 overflow-auto">
        {/* Game Grid */}
        <div className="flex-1 flex flex-col items-center">
          <div className="mb-4 text-center">
            <div className="text-sm font-semibold">
              Position: ({currentUserState?.position.x ?? '?'},{' '}
              {currentUserState?.position.y ?? '?'})
            </div>
            <div className="text-sm">
              Health: {currentUserState?.health ?? '?'}/
              {currentUserState?.max_health ?? '?'}
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
                   const isCurrentUser = cell.player?.user_id === user?.id

                   return (
                     <div
                       key={`${x}-${y}`}
                       className={`w-3 h-3 flex items-center justify-center text-[8px] font-bold ${
                         cell.player
                           ? isCurrentUser
                             ? 'bg-green-500 text-white'
                             : cell.player.is_npc
                               ? 'bg-blue-500 text-white'
                               : 'bg-red-500 text-white'
                           : cell.obstacle
                             ? 'bg-amber-700 text-white'
                             : cell.prop
                               ? 'bg-emerald-700 text-white'
                               : cell.isBuffer
                                 ? 'bg-slate-300'
                                 : 'bg-gray-100'
                       }`}
                       title={
                         cell.player
                           ? `${cell.player.display_name || cell.player.username} (HP: ${cell.player.health})`
                           : cell.obstacle
                             ? `Obstacle: ${cell.obstacle.type} (${x}, ${y})`
                             : cell.prop
                               ? `Prop: ${cell.prop.type} (${x}, ${y})`
                               : cell.isBuffer
                                 ? `Buffer (${x}, ${y})`
                                 : `(${x}, ${y})`
                       }
                     >
                       {cell.player
                         ? (cell.player.display_name || cell.player.username)?.[0]?.toUpperCase()
                         : cell.obstacle
                           ? 'X'
                           : cell.prop
                             ? cell.prop.type === 'tree'
                               ? 'T'
                               : 'R'
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
              {players?.map((state) => (
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
                onClick={() => executeCommand('move_up')}
                className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
                title="Move Up"
              >
                <ArrowUp size={20} />
              </button>
              <div />
              <button
                onClick={() => executeCommand('move_left')}
                className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
                title="Move Left"
              >
                <ArrowLeft size={20} />
              </button>
              <div className="p-3 flex items-center justify-center text-xs">
                {currentUserState?.position.x ?? '?'},
                {currentUserState?.position.y ?? '?'}
              </div>
              <button
                onClick={() => executeCommand('move_right')}
                className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
                title="Move Right"
              >
                <ArrowRight size={20} />
              </button>
              <div />
              <button
                onClick={() => executeCommand('move_down')}
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
                disabled={!targetUsername}
                className="flex-1 p-2 rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 flex items-center justify-center gap-2"
                title="Attack target"
              >
                <Sword size={16} />
                Attack
              </button>
              <button
                onClick={() => executeCommand('heal')}
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
