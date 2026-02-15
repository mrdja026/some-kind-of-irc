import { useMemo } from 'react'
import * as THREE from 'three'
import { axialToWorld, HEX_SIZE } from './hexUtils'
import { createHexTerrainMaterial, createBufferTerrainMaterial } from './shaders/hexTerrainShader'

interface HexTileProps {
  q: number
  r: number
  isBuffer?: boolean
  isHighlighted?: boolean
  onClick?: (x: number, y: number) => void
}

/**
 * Single hex tile rendered as a flat hexagonal cylinder
 * Uses pointy-top orientation to match Godot
 */
export function HexTile({ q, r, isBuffer = false, isHighlighted = false, onClick }: HexTileProps) {
  const { x, z } = axialToWorld(q, r)
  
  // Create hex geometry - CylinderGeometry with 6 radial segments makes a hexagon
  // Rotated 90 degrees on X to lay flat, then 30 degrees on Y for pointy-top
  const geometry = useMemo(() => {
    const geo = new THREE.CylinderGeometry(
      HEX_SIZE * 0.95, // top radius (slightly smaller to show gaps)
      HEX_SIZE * 0.95, // bottom radius
      0.1,             // height (thin)
      6                // radial segments (hexagon)
    )
    // Rotate to lay flat on XZ plane with pointy-top
    geo.rotateY(Math.PI / 6) // 30 degrees for pointy-top orientation
    return geo
  }, [])
  
  const material = useMemo(() => {
    return isBuffer ? createBufferTerrainMaterial() : createHexTerrainMaterial()
  }, [isBuffer])

  return (
    <group position={[x, 0, z]}>
      <mesh
        geometry={geometry}
        material={material}
        onClick={() => onClick?.(q, r)}
      />
      {isHighlighted && (
        <mesh geometry={geometry} position={[0, 0.06, 0]}>
          <meshBasicMaterial color={0xfacc15} transparent opacity={0.55} />
        </mesh>
      )}
    </group>
  )
}
