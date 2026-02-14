import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getCurrentUser } from '../api'
import type { User, Player, GameSnapshotPayload, Position } from '../types'
import { ArrowUp, ArrowDown, Sword, Heart } from 'lucide-react'
import { GameScene } from './game3d/GameScene'
import { axialToWorld } from './game3d/hexUtils'
import { findPathBfs, hexDistanceOffset, pathToCommands } from './game3d/interaction/hexPathing'

const API_BASE_URL =
  import.meta.env.VITE_PUBLIC_API_URL ||
  import.meta.env.VITE_API_URL ||
  'http://localhost:8002'

interface GameChannelProps {
  channelId: number
  channelName: string
  sendGameCommand: (channelId: number, command: string, targetUsername?: string) => void
  sendGameJoin: (channelId: number) => void
}

async function getGameCommands(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/game/commands`, { credentials: 'include' })
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

function isTextInputActive(): boolean {
  const active = document.activeElement as HTMLElement | null
  if (!active) return false
  const tag = active.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || active.isContentEditable
}

export function GameChannel({ channelId, channelName, sendGameCommand, sendGameJoin }: GameChannelProps) {
  const [targetUsername, setTargetUsername] = useState('')
  const [actionLog, setActionLog] = useState<Array<string>>([])
  const [highlightedPath, setHighlightedPath] = useState<Array<Position>>([])
  const [selectedTargetUserId, setSelectedTargetUserId] = useState<number | null>(null)
  const moveTimersRef = useRef<Array<number>>([])

  const { data: user } = useQuery<User>({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
  })

  const { data: commands } = useQuery<Array<string>>({
    queryKey: ['gameCommands'],
    queryFn: getGameCommands,
  })

  const { data: players } = useQuery<Array<Player>>({
    queryKey: ['channelGameStates', channelId],
    queryFn: async () => [],
    enabled: false,
    initialData: [],
  })

  const { data: snapshot } = useQuery<GameSnapshotPayload | undefined>({
    queryKey: ['gameSnapshot', channelId],
    queryFn: async () => undefined,
    enabled: false,
  })

  useEffect(() => {
    if (!channelId) return
    joinGameChannel(channelId)
      .then(() => sendGameJoin(channelId))
      .catch(console.error)
  }, [channelId, sendGameJoin])

  useEffect(() => {
    return () => {
      moveTimersRef.current.forEach((timer) => window.clearTimeout(timer))
      moveTimersRef.current = []
    }
  }, [])

  const appendLog = (line: string) => {
    setActionLog((prev) => [...prev.slice(-19), line])
  }

  const gridWidth = snapshot?.map?.width ?? 10
  const gridHeight = snapshot?.map?.height ?? 10
  const obstacles = snapshot?.obstacles || []
  const battlefieldProps = snapshot?.battlefield?.props || []
  const bufferTiles = snapshot?.battlefield?.buffer?.tiles || []
  const activeTurnUserId = snapshot?.active_turn_user_id

  const currentUserState = players?.find((state) => state.user_id === user?.id)
  const isMyTurn = Boolean(user?.id && activeTurnUserId === user.id)

  const executeCommand = (command: string) => {
    if (!channelId) return
    const target = command === 'attack' ? targetUsername || undefined : undefined
    sendGameCommand(channelId, command, target)
  }

  const eligibleTargets = useMemo(() => {
    if (!currentUserState || !players?.length || !user?.id) return [] as Array<Player>
    const origin = currentUserState.position

    const candidates = players.filter(
      (p) => p.user_id !== user.id && p.health > 0 && hexDistanceOffset(origin, p.position) === 1
    )

    return [...candidates].sort((a, b) => {
      const aWorld = axialToWorld(a.position.x, a.position.y)
      const bWorld = axialToWorld(b.position.x, b.position.y)
      const oWorld = axialToWorld(origin.x, origin.y)
      const aAngle = Math.atan2(aWorld.z - oWorld.z, aWorld.x - oWorld.x)
      const bAngle = Math.atan2(bWorld.z - oWorld.z, bWorld.x - oWorld.x)
      if (aAngle === bAngle) return a.user_id - b.user_id
      return bAngle - aAngle
    })
  }, [currentUserState, players, user?.id])

  useEffect(() => {
    if (selectedTargetUserId == null) return
    const stillValid = eligibleTargets.some((target) => target.user_id === selectedTargetUserId)
    if (!stillValid) {
      setSelectedTargetUserId(null)
      setTargetUsername('')
    }
  }, [eligibleTargets, selectedTargetUserId])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return
      if (isTextInputActive()) return
      if (!isMyTurn) return

      const pool = eligibleTargets
      if (pool.length === 0) {
        event.preventDefault()
        return
      }

      event.preventDefault()
      const direction = event.shiftKey ? -1 : 1
      const currentIndex = pool.findIndex((target) => target.user_id === selectedTargetUserId)
      const baseIndex = currentIndex >= 0 ? currentIndex : direction > 0 ? -1 : 0
      const nextIndex = (baseIndex + direction + pool.length) % pool.length
      const nextTarget = pool[nextIndex]
      setSelectedTargetUserId(nextTarget.user_id)
      setTargetUsername(nextTarget.username)
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [eligibleTargets, isMyTurn, selectedTargetUserId])

  const handleUnitClick = (player: Player) => {
    if (!isMyTurn || !currentUserState || !user?.id) return
    if (player.user_id === user.id) return
    if (player.health <= 0) return
    if (hexDistanceOffset(currentUserState.position, player.position) !== 1) return
    setSelectedTargetUserId(player.user_id)
    setTargetUsername(player.username)
  }

  const handleTileClick = (target: Position) => {
    if (!isMyTurn) return
    if (!currentUserState) return
    if (!channelId) return

    const blocked = new Set<string>()
    const key = (pos: Position) => `${pos.x}:${pos.y}`

    obstacles.forEach((obstacle) => blocked.add(key(obstacle.position)))
    battlefieldProps.forEach((prop) => {
      if (prop.is_blocking) blocked.add(key(prop.position))
    })
    bufferTiles.forEach((tile) => blocked.add(key(tile)))
    players.forEach((player) => {
      if (player.user_id !== currentUserState.user_id) blocked.add(key(player.position))
    })

    const targetKey = key(target)
    const currentKey = key(currentUserState.position)
    if (targetKey === currentKey) return
    if (target.x < 0 || target.y < 0 || target.x >= gridWidth || target.y >= gridHeight) return
    if (blocked.has(targetKey)) {
      appendLog(`✗ Blocked tile (${target.x}, ${target.y})`)
      return
    }

    const path = findPathBfs(currentUserState.position, target, {
      width: gridWidth,
      height: gridHeight,
      blocked,
    })
    if (!path || path.length < 2) {
      appendLog(`✗ No valid path to (${target.x}, ${target.y})`)
      return
    }

    const commandsToSend = pathToCommands(path)
    if (commandsToSend.length === 0) {
      appendLog(`✗ Could not resolve movement command chain`)
      return
    }

    moveTimersRef.current.forEach((timer) => window.clearTimeout(timer))
    moveTimersRef.current = []
    setHighlightedPath(path.slice(1))

    appendLog(`✓ Moving ${commandsToSend.length} steps`)

    commandsToSend.forEach((command, index) => {
      const timerId = window.setTimeout(() => {
        sendGameCommand(channelId, command)
        setHighlightedPath((prev) => prev.slice(1))
        if (index === commandsToSend.length - 1) {
          window.setTimeout(() => setHighlightedPath([]), 120)
        }
      }, index * 220)
      moveTimersRef.current.push(timerId)
    })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b chat-divider">
        <h2 className="text-lg font-bold">{channelName} - Game Mode</h2>
        <p className="text-sm chat-meta">Available commands: {commands?.join(', ') || 'Loading...'}</p>
        <p className="text-sm chat-meta">
          Battlefield: players {players?.length || 0}, obstacles {obstacles.length}, props {battlefieldProps.length},
          buffer markers {bufferTiles.length}
        </p>
      </div>

      <div className="flex-1 flex flex-col md:flex-row gap-4 p-4 overflow-auto">
        <div className="flex-1 flex flex-col">
          <div className="mb-2 text-center">
            <div className="text-sm font-semibold">
              Position: ({currentUserState?.position.x ?? '?'}, {currentUserState?.position.y ?? '?'})
            </div>
            <div className="text-sm">
              Health: {currentUserState?.health ?? '?'}/{currentUserState?.max_health ?? '?'}
            </div>
            <div className="text-xs text-gray-500">{isMyTurn ? 'Your turn' : 'Waiting for turn'}</div>
          </div>
          <div className="mb-2 rounded border bg-gray-50 px-3 py-2 text-xs text-gray-700">
            <div className="font-semibold mb-1">3D Controls</div>
            <div>Left Click: select/move</div>
            <div>Tab / Shift+Tab: cycle adjacent targets (includes NPCs)</div>
            <div>Alt + Left Drag: rotate camera (360°)</div>
            <div>Right Drag: pan camera</div>
            <div>Mouse Wheel: zoom in/out</div>
            <div>Shift + Left Drag: move sun & shadows</div>
          </div>

          <div className="flex-1 border rounded overflow-hidden" style={{ minHeight: '400px' }}>
            <GameScene
              players={players || []}
              obstacles={obstacles}
              props={battlefieldProps}
              bufferTiles={bufferTiles}
              currentUserId={user?.id}
              activeTurnUserId={activeTurnUserId}
              gridWidth={gridWidth}
              gridHeight={gridHeight}
              highlightedTiles={highlightedPath}
              selectedTargetUserId={selectedTargetUserId}
              onTileClick={handleTileClick}
              onUnitClick={handleUnitClick}
            />
          </div>

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
                  <span>HP: {state.health}/{state.max_health}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="w-full md:w-64 flex flex-col gap-4">
          <div className="flex flex-col items-center gap-2">
            <h3 className="font-semibold text-sm">Movement</h3>
            <div className="grid grid-cols-3 gap-1">
              <button onClick={() => executeCommand('move_nw')} disabled={!isMyTurn} className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50" title="Move North-West">NW</button>
              <button onClick={() => executeCommand('move_n')} disabled={!isMyTurn} className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50" title="Move North"><ArrowUp size={20} /></button>
              <button onClick={() => executeCommand('move_ne')} disabled={!isMyTurn} className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50" title="Move North-East">NE</button>
              <button onClick={() => executeCommand('move_sw')} disabled={!isMyTurn} className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50" title="Move South-West">SW</button>
              <button onClick={() => executeCommand('move_s')} disabled={!isMyTurn} className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50" title="Move South"><ArrowDown size={20} /></button>
              <button onClick={() => executeCommand('move_se')} disabled={!isMyTurn} className="p-3 rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50" title="Move South-East">SE</button>
              <div className="col-span-3 p-2 flex items-center justify-center text-xs">
                {currentUserState?.position.x ?? '?'}, {currentUserState?.position.y ?? '?'}
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <h3 className="font-semibold text-sm">Actions</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={targetUsername}
                onChange={(event) => setTargetUsername(event.target.value)}
                placeholder="Target @username (Tab cycles)"
                className="flex-1 px-2 py-1 text-sm border rounded"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => executeCommand('attack')}
                disabled={!isMyTurn || !targetUsername}
                className="flex-1 p-2 rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 flex items-center justify-center gap-2"
                title="Attack target"
              >
                <Sword size={16} />
                Attack
              </button>
              <button
                onClick={() => executeCommand('heal')}
                disabled={!isMyTurn}
                className="flex-1 p-2 rounded bg-green-500 text-white hover:bg-green-600 disabled:opacity-50 flex items-center justify-center gap-2"
                title="Heal yourself"
              >
                <Heart size={16} />
                Heal
              </button>
              <button
                onClick={() => executeCommand('end_turn')}
                disabled={!isMyTurn}
                className="flex-1 p-2 rounded bg-slate-600 text-white hover:bg-slate-700 disabled:opacity-50"
                title="End current turn"
              >
                End Turn
              </button>
            </div>
          </div>

          <div className="flex-1 flex flex-col">
            <h3 className="font-semibold text-sm mb-2">Action Log</h3>
            <div className="flex-1 bg-gray-100 rounded p-2 text-xs space-y-1 max-h-40 overflow-y-auto">
              {actionLog.length === 0 ? (
                <div className="text-gray-500">No actions yet</div>
              ) : (
                actionLog.map((log, i) => (
                  <div key={i} className={log.startsWith('✓') ? 'text-green-600' : 'text-red-600'}>
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

