import { useMemo } from 'react'
import * as THREE from 'three'
import { axialToWorld } from './hexUtils'
import type { Obstacle } from '../../types'

interface ObstacleMeshProps {
  obstacle: Obstacle
}

// Obstacle color - dark amber/brown matching original
const OBSTACLE_COLOR = new THREE.Color(0x78350f) // amber-900

/**
 * 3D obstacle rendered as a box
 */
export function ObstacleMesh({ obstacle }: ObstacleMeshProps) {
  const { x, z } = axialToWorld(obstacle.position.x, obstacle.position.y)
  
  const geometry = useMemo(() => {
    return new THREE.BoxGeometry(0.7, 0.8, 0.7)
  }, [])

  return (
    <mesh 
      geometry={geometry}
      position={[x, 0.45, z]}
      name={`obstacle-${obstacle.id}`}
    >
      <meshStandardMaterial color={OBSTACLE_COLOR} roughness={0.8} />
    </mesh>
  )
}
