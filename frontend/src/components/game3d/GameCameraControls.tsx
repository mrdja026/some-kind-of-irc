import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { axialToWorld, getGridCenter } from './hexUtils'

interface GameCameraControlsProps {
  gridWidth: number
  gridHeight: number
  rotateEnabled?: boolean
  panEnabled?: boolean
}

export function GameCameraControls({
  gridWidth,
  gridHeight,
  rotateEnabled = false,
  panEnabled = true,
}: GameCameraControlsProps) {
  const controlsRef = useRef<any>(null)
  const { camera } = useThree()
  const center = useMemo(() => getGridCenter(gridWidth, gridHeight), [gridWidth, gridHeight])

  const maxCorner = useMemo(() => axialToWorld(gridWidth - 1, gridHeight - 1), [gridWidth, gridHeight])
  const minX = -4
  const minZ = -4
  const maxX = maxCorner.x + 4
  const maxZ = maxCorner.z + 4

  useEffect(() => {
    const controls = controlsRef.current
    if (!controls) return
    controls.target.set(center.x, 0, center.z)
    controls.update()
  }, [center.x, center.z])

  useFrame(() => {
    const controls = controlsRef.current
    if (!controls) return

    controls.target.x = THREE.MathUtils.clamp(controls.target.x, minX, maxX)
    controls.target.z = THREE.MathUtils.clamp(controls.target.z, minZ, maxZ)

    const cam = camera as THREE.OrthographicCamera
    cam.zoom = THREE.MathUtils.clamp(cam.zoom, 18, 90)
    cam.updateProjectionMatrix()
    controls.update()
  })

  return (
    <OrbitControls
      ref={controlsRef}
      args={[camera]}
      enableRotate={rotateEnabled}
      enablePan={panEnabled}
      enableZoom
      screenSpacePanning={false}
      zoomSpeed={0.85}
      panSpeed={0.85}
      rotateSpeed={0.7}
      minZoom={18}
      maxZoom={90}
      minPolarAngle={0.2}
      maxPolarAngle={Math.PI / 2 - 0.08}
      minAzimuthAngle={-Infinity}
      maxAzimuthAngle={Infinity}
      mouseButtons={{
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.PAN,
        RIGHT: THREE.MOUSE.PAN,
      }}
    />
  )
}

