import { useMemo } from 'react'
import * as THREE from 'three'
import { axialToWorld } from './hexUtils'
import type { BattlefieldProp } from '../../types'

interface PropMeshProps {
  prop: BattlefieldProp
}

// Prop colors
const TREE_FOLIAGE_COLOR = new THREE.Color(0x166534)  // green-800
const TREE_TRUNK_COLOR = new THREE.Color(0x78350f)    // amber-900
const ROCK_COLOR = new THREE.Color(0x57534e)          // stone-600

/**
 * 3D prop - tree or rock
 */
export function PropMesh({ prop }: PropMeshProps) {
  const { x, z } = axialToWorld(prop.position.x, prop.position.y)
  
  if (prop.type === 'tree') {
    return <TreeMesh x={x} z={z} id={prop.id} />
  }
  
  return <RockMesh x={x} z={z} id={prop.id} />
}

function TreeMesh({ x, z, id }: { x: number; z: number; id: string }) {
  // Foliage - cone shape
  const foliageGeometry = useMemo(() => {
    return new THREE.ConeGeometry(0.5, 1.2, 8)
  }, [])
  
  // Trunk - cylinder
  const trunkGeometry = useMemo(() => {
    return new THREE.CylinderGeometry(0.12, 0.15, 0.5, 8)
  }, [])

  return (
    <group position={[x, 0, z]} name={`prop-tree-${id}`}>
      {/* Trunk */}
      <mesh geometry={trunkGeometry} position={[0, 0.3, 0]}>
        <meshStandardMaterial color={TREE_TRUNK_COLOR} />
      </mesh>
      
      {/* Foliage */}
      <mesh geometry={foliageGeometry} position={[0, 1.1, 0]}>
        <meshStandardMaterial color={TREE_FOLIAGE_COLOR} />
      </mesh>
    </group>
  )
}

function RockMesh({ x, z, id }: { x: number; z: number; id: string }) {
  // Rock - dodecahedron for irregular shape
  const geometry = useMemo(() => {
    return new THREE.DodecahedronGeometry(0.35, 0)
  }, [])

  return (
    <mesh 
      geometry={geometry}
      position={[x, 0.25, z]}
      rotation={[0, Math.random() * Math.PI, 0]} // Random rotation for variety
      name={`prop-rock-${id}`}
    >
      <meshStandardMaterial color={ROCK_COLOR} roughness={0.9} />
    </mesh>
  )
}
