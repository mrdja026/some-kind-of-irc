import { useRef, useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import { OrthographicCamera } from '@react-three/drei'
import * as THREE from 'three'
import { getGridCenter } from './hexUtils'

interface IsometricCameraProps {
  gridWidth?: number
  gridHeight?: number
}

/**
 * Orthographic camera setup matching Godot's isometric view
 * 
 * Godot settings (from Game.tscn):
 * - position = Vector3(0, 18, 18)
 * - rotation_degrees = Vector3(-35, 45, 0)
 * - projection = 1 (Orthographic)
 * - size = 24.0
 */
export function IsometricCamera({ gridWidth = 10, gridHeight = 10 }: IsometricCameraProps) {
  const cameraRef = useRef<THREE.OrthographicCamera>(null)
  const didInitZoomRef = useRef(false)
  const { size } = useThree()
  
  // Calculate grid center to position camera
  const gridCenter = getGridCenter(gridWidth, gridHeight)
  
  // Godot's camera rotation converted to Three.js
  // Godot: rotation_degrees = (-35, 45, 0) - but we need -45 for Y in Three.js
  // Using manual rotation order 'YXZ' to match Godot behavior
  const rotationY = -Math.PI / 4 // -45 degrees
  const rotationX = Math.atan(-1 / Math.sqrt(2)) // ~-35.26 degrees (true isometric)
  
  // Camera distance from center
  const distance = 18
  
  // Calculate camera position based on rotation
  // Position camera looking at grid center from isometric angle
  const cameraPosition: [number, number, number] = [
    gridCenter.x + distance * Math.sin(-rotationY) * Math.cos(rotationX),
    distance * Math.sin(-rotationX) + 5,
    gridCenter.z + distance * Math.cos(-rotationY) * Math.cos(rotationX),
  ]
  
  // Zoom to fit the grid (Godot size=24 means viewport shows 24 units vertically)
  const zoom = Math.min(size.width, size.height) / 24

  useEffect(() => {
    if (cameraRef.current) {
      // Look at grid center
      cameraRef.current.lookAt(gridCenter.x, 0, gridCenter.z)
      if (!didInitZoomRef.current) {
        cameraRef.current.zoom = zoom
        didInitZoomRef.current = true
      }
      cameraRef.current.updateProjectionMatrix()
    }
  }, [gridCenter.x, gridCenter.z, zoom])

  return (
    <OrthographicCamera
      ref={cameraRef}
      makeDefault
      position={cameraPosition}
      near={0.1}
      far={1000}
    />
  )
}
