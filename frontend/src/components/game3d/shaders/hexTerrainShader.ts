import * as THREE from 'three'

/**
 * Port of Godot hex_terrain.gdshader to Three.js GLSL
 * Creates a wave/detail color blending effect on hex terrain
 */

export const hexTerrainVertexShader = /* glsl */ `
  varying vec3 vWorldPos;

  void main() {
    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
    vWorldPos = worldPosition.xyz;
    gl_Position = projectionMatrix * viewMatrix * worldPosition;
  }
`

export const hexTerrainFragmentShader = /* glsl */ `
  uniform vec3 baseColor;
  uniform vec3 highlightColor;
  uniform float blendScale;
  uniform float detailScale;
  uniform float detailStrength;

  varying vec3 vWorldPos;

  void main() {
    float wave = sin(vWorldPos.x * blendScale) + sin(vWorldPos.z * blendScale);
    float detail = sin(vWorldPos.x * detailScale + vWorldPos.z * detailScale);
    detail += sin(vWorldPos.x * detailScale * 0.5 - vWorldPos.z * detailScale * 0.8);
    detail *= 0.5;
    float t = clamp(wave * 0.25 + 0.5 + detail * detailStrength, 0.0, 1.0);
    vec3 color = mix(baseColor, highlightColor, t);
    gl_FragColor = vec4(color, 1.0);
  }
`

export const hexTerrainUniforms = {
  baseColor: { value: new THREE.Color(0.18, 0.45, 0.2) },
  highlightColor: { value: new THREE.Color(0.12, 0.32, 0.16) },
  blendScale: { value: 0.6 },
  detailScale: { value: 1.2 },
  detailStrength: { value: 0.18 },
}

export function createHexTerrainMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      baseColor: { value: new THREE.Color(0.18, 0.45, 0.2) },
      highlightColor: { value: new THREE.Color(0.12, 0.32, 0.16) },
      blendScale: { value: 0.6 },
      detailScale: { value: 1.2 },
      detailStrength: { value: 0.18 },
    },
    vertexShader: hexTerrainVertexShader,
    fragmentShader: hexTerrainFragmentShader,
    side: THREE.FrontSide,
  })
}

// Buffer zone variant - gray/muted colors
export function createBufferTerrainMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      baseColor: { value: new THREE.Color(0.35, 0.35, 0.38) },
      highlightColor: { value: new THREE.Color(0.28, 0.28, 0.32) },
      blendScale: { value: 0.6 },
      detailScale: { value: 1.2 },
      detailStrength: { value: 0.12 },
    },
    vertexShader: hexTerrainVertexShader,
    fragmentShader: hexTerrainFragmentShader,
    side: THREE.FrontSide,
  })
}
