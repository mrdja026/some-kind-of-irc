import * as THREE from 'three'

/**
 * Port of Godot outline.gdshader to Three.js GLSL
 * Creates an outline effect by rendering back faces expanded along normals
 */

export const outlineVertexShader = /* glsl */ `
  uniform float outlineSize;

  void main() {
    vec3 expandedPosition = position + normal * outlineSize;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(expandedPosition, 1.0);
  }
`

export const outlineFragmentShader = /* glsl */ `
  uniform vec3 outlineColor;
  uniform float outlineAlpha;

  void main() {
    gl_FragColor = vec4(outlineColor, outlineAlpha);
  }
`

export function createOutlineMaterial(
  color: THREE.Color = new THREE.Color(0, 0, 0),
  size: number = 0.04,
  alpha: number = 1.0
): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      outlineColor: { value: color },
      outlineSize: { value: size },
      outlineAlpha: { value: alpha },
    },
    vertexShader: outlineVertexShader,
    fragmentShader: outlineFragmentShader,
    side: THREE.BackSide, // Render back faces (cull front)
    transparent: alpha < 1.0,
    depthWrite: true,
  })
}
