import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { HexTerrain } from './HexTerrain'
import { PlayerUnit } from './PlayerUnit'
import { ObstacleMesh } from './ObstacleMesh'
import { PropMesh } from './PropMesh'
import { IsometricCamera } from './IsometricCamera'
import { GameCameraControls } from './GameCameraControls'
import { ShiftStarIndicator } from './ShiftStarIndicator'
import { getGridCenter } from './hexUtils'
import type { Player, Obstacle, BattlefieldProp, Position } from '../../types'

interface GameSceneProps {
  players: Player[]
  obstacles: Obstacle[]
  props: BattlefieldProp[]
  bufferTiles: Position[]
  currentUserId?: number
  activeTurnUserId?: number | null
  gridWidth?: number
  gridHeight?: number
  highlightedTiles?: Position[]
  selectedTargetUserId?: number | null
  onTileClick?: (position: Position) => void
  onUnitClick?: (player: Player) => void
}

export function GameScene({
  players,
  obstacles,
  props,
  bufferTiles,
  currentUserId,
  activeTurnUserId,
  gridWidth = 10,
  gridHeight = 10,
  highlightedTiles = [],
  selectedTargetUserId,
  onTileClick,
  onUnitClick,
}: GameSceneProps) {
  const [altHeld, setAltHeld] = useState(false)
  const [shiftHeld, setShiftHeld] = useState(false)
  const [sunDragging, setSunDragging] = useState(false)
  const [sunAzimuth, setSunAzimuth] = useState(Math.PI / 4)
  const [sunElevation, setSunElevation] = useState(0.9)
  const dragStartRef = useRef<{ x: number; y: number } | null>(null)
  const gridCenter = useMemo(() => getGridCenter(gridWidth, gridHeight), [gridWidth, gridHeight])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Alt') setAltHeld(true)
      if (event.key === 'Shift') setShiftHeld(true)
    }
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key === 'Alt') setAltHeld(false)
      if (event.key === 'Shift') {
        setShiftHeld(false)
        setSunDragging(false)
        dragStartRef.current = null
      }
    }
    const onBlur = () => {
      setAltHeld(false)
      setShiftHeld(false)
      setSunDragging(false)
      dragStartRef.current = null
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onBlur)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('blur', onBlur)
    }
  }, [])

  const sunPosition = useMemo(() => {
    const radius = 26
    const x = Math.cos(sunAzimuth) * radius * Math.cos(sunElevation)
    const y = Math.sin(sunElevation) * radius
    const z = Math.sin(sunAzimuth) * radius * Math.cos(sunElevation)
    return [x, y, z] as [number, number, number]
  }, [sunAzimuth, sunElevation])

  const handlePointerDown = (event: any) => {
    if (event.button !== 0) return
    if (!shiftHeld) return
    setSunDragging(true)
    dragStartRef.current = { x: event.clientX, y: event.clientY }
    event.preventDefault()
  }

  const handlePointerMove = (event: any) => {
    if (!sunDragging) return
    const start = dragStartRef.current
    if (!start) return
    const dx = event.clientX - start.x
    const dy = event.clientY - start.y
    dragStartRef.current = { x: event.clientX, y: event.clientY }

    setSunAzimuth((prev) => prev + dx * 0.012)
    setSunElevation((prev) => Math.min(1.35, Math.max(0.2, prev - dy * 0.006)))
    event.preventDefault()
  }

  const stopSunDrag = () => {
    setSunDragging(false)
    dragStartRef.current = null
  }

  return (
    <div
      style={{ width: '100%', height: '100%', minHeight: '400px' }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopSunDrag}
      onPointerLeave={stopSunDrag}
    >
      <Canvas
        style={{ width: '100%', height: '100%' }}
        gl={{ antialias: true }}
        onCreated={({ gl }) => {
          gl.domElement.oncontextmenu = (event) => event.preventDefault()
        }}
      >
        <IsometricCamera gridWidth={gridWidth} gridHeight={gridHeight} />
        <GameCameraControls
          gridWidth={gridWidth}
          gridHeight={gridHeight}
          rotateEnabled={altHeld && !sunDragging}
          panEnabled={!sunDragging}
        />

        <ambientLight intensity={0.42} />
        <directionalLight
          position={sunPosition}
          intensity={1.05}
          castShadow
          shadow-mapSize={[1024, 1024]}
        />
        <pointLight position={[0, 10, 0]} intensity={0.28} />
        {shiftHeld && (
          <ShiftStarIndicator position={[gridCenter.x, 1.5, gridCenter.z]} />
        )}

        <HexTerrain
          width={gridWidth}
          height={gridHeight}
          bufferTiles={bufferTiles}
          highlightedTiles={highlightedTiles}
          onTileClick={onTileClick}
        />

        {obstacles.map((obstacle) => (
          <ObstacleMesh key={obstacle.id} obstacle={obstacle} />
        ))}
        {props.map((prop) => (
          <PropMesh key={prop.id} prop={prop} />
        ))}
        {players.map((player) => (
          <PlayerUnit
            key={player.user_id}
            player={player}
            isCurrentUser={player.user_id === currentUserId}
            isActiveTurn={player.user_id === activeTurnUserId}
            isSelectedTarget={selectedTargetUserId === player.user_id}
            onClick={onUnitClick}
          />
        ))}
      </Canvas>
    </div>
  )
}

