import { useMemo } from 'react'
import * as THREE from 'three'
import { axialToWorld } from './hexUtils'
import { createOutlineMaterial } from './shaders/outlineShader'
import type { Player } from '../../types'

interface PlayerUnitProps {
  player: Player
  isCurrentUser: boolean
  isActiveTurn: boolean
  isSelectedTarget?: boolean
  onClick?: (player: Player) => void
}

const CURRENT_USER_COLOR = new THREE.Color(0x22c55e)
const OTHER_PLAYER_COLOR = new THREE.Color(0xef4444)
const NPC_COLOR = new THREE.Color(0x3b82f6)

export function PlayerUnit({
  player,
  isCurrentUser,
  isActiveTurn,
  isSelectedTarget = false,
  onClick,
}: PlayerUnitProps) {
  const { x, z } = axialToWorld(player.position.x, player.position.y)

  const color = useMemo(() => {
    if (isCurrentUser) return CURRENT_USER_COLOR
    if (player.is_npc) return NPC_COLOR
    return OTHER_PLAYER_COLOR
  }, [isCurrentUser, player.is_npc])

  const bodyGeometry = useMemo(() => new THREE.CylinderGeometry(0.3, 0.35, 1.2, 16), [])
  const headGeometry = useMemo(() => new THREE.SphereGeometry(0.25, 16, 12), [])
  const outlineMaterial = useMemo(() => createOutlineMaterial(new THREE.Color(0xffffff), 0.06), [])

  return (
    <group position={[x, 0.7, z]} name={`player-${player.user_id}`} onClick={() => onClick?.(player)}>
      <mesh geometry={bodyGeometry}>
        <meshStandardMaterial color={color} />
      </mesh>
      <mesh geometry={headGeometry} position={[0, 0.8, 0]}>
        <meshStandardMaterial color={color} />
      </mesh>

      {isActiveTurn && (
        <>
          <mesh geometry={bodyGeometry} material={outlineMaterial} />
          <mesh geometry={headGeometry} material={outlineMaterial} position={[0, 0.8, 0]} />
        </>
      )}

      {isSelectedTarget && (
        <mesh position={[0, -0.58, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.55, 0.75, 24]} />
          <meshBasicMaterial color={0xf59e0b} transparent opacity={0.9} side={THREE.DoubleSide} />
        </mesh>
      )}

      <group position={[0, 1.4, 0]}>
        <mesh>
          <boxGeometry args={[0.6, 0.08, 0.08]} />
          <meshBasicMaterial color={0x333333} />
        </mesh>
        <mesh position={[(player.health / player.max_health - 1) * 0.3, 0, 0.01]}>
          <boxGeometry args={[0.6 * (player.health / player.max_health), 0.06, 0.06]} />
          <meshBasicMaterial color={0x22c55e} />
        </mesh>
      </group>
    </group>
  )
}

