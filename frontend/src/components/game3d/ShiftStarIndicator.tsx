import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

interface ShiftStarIndicatorProps {
  position: [number, number, number]
}

export function ShiftStarIndicator({ position }: ShiftStarIndicatorProps) {
  const materialRef = useRef<THREE.ShaderMaterial | null>(null)

  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0.0 },
      },
      vertexShader: `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec2 vUv;
        uniform float uTime;

        void main() {
          vec2 uv = vUv * 2.0 - 1.0;
          float r = length(uv);
          float a = atan(uv.y, uv.x);

          float raysA = pow(abs(cos(a * 18.0 + uTime * 4.0)), 18.0);
          float raysB = pow(abs(cos(a * 31.0 - uTime * 3.2)), 24.0);
          float rays = max(raysA * 0.75, raysB);

          float core = smoothstep(0.38, 0.0, r);
          float ring = smoothstep(0.72, 0.28, r) * smoothstep(0.22, 0.26, r);
          float pulse = 0.85 + 0.15 * sin(uTime * 8.0);
          float glow = (core * 1.2 + ring * 0.8 + rays * (1.0 - r)) * pulse;

          vec3 gold = vec3(1.0, 0.82, 0.25);
          vec3 hot = vec3(1.0, 0.95, 0.6);
          vec3 color = mix(gold, hot, core + rays * 0.25);
          float alpha = clamp(glow, 0.0, 1.0);

          gl_FragColor = vec4(color * glow, alpha);
        }
      `,
    })
  }, [])

  useFrame((state) => {
    if (!materialRef.current) return
    materialRef.current.uniforms.uTime.value = state.clock.getElapsedTime()
  })

  return (
    <group position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[6.0, 6.0, 1, 1]} />
        <primitive object={material} ref={materialRef} attach="material" />
      </mesh>
      <mesh position={[0, 0.35, 0]}>
        <sphereGeometry args={[0.09, 16, 16]} />
        <meshBasicMaterial color={0xffdf55} />
      </mesh>
    </group>
  )
}

