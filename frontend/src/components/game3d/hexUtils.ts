/**
 * Hex coordinate utilities for pointy-top hexagonal grid
 * Matches Godot's hex coordinate system
 */

// Hex size (outer radius - center to vertex)
export const HEX_SIZE = 1.0

// Pointy-top hex dimensions
export const HEX_WIDTH = Math.sqrt(3) * HEX_SIZE
export const HEX_HEIGHT = 2 * HEX_SIZE

/**
 * Convert axial hex coordinates (q, r) to world position (x, z)
 * Uses pointy-top orientation matching Godot
 */
export function axialToWorld(q: number, r: number): { x: number; z: number } {
  const x = HEX_SIZE * (Math.sqrt(3) * q + (Math.sqrt(3) / 2) * r)
  const z = HEX_SIZE * ((3 / 2) * r)
  return { x, z }
}

/**
 * Convert world position to axial hex coordinates
 * Inverse of axialToWorld
 */
export function worldToAxial(x: number, z: number): { q: number; r: number } {
  const r = (2 / 3) * z / HEX_SIZE
  const q = (x / HEX_SIZE - (Math.sqrt(3) / 2) * r) / Math.sqrt(3)
  return { q: Math.round(q), r: Math.round(r) }
}

/**
 * Generate all hex positions for a grid of given size
 * Creates a rectangular grid in axial coordinates
 */
export function generateHexGrid(width: number, height: number): Array<{ q: number; r: number }> {
  const hexes: Array<{ q: number; r: number }> = []
  
  for (let r = 0; r < height; r++) {
    for (let q = 0; q < width; q++) {
      hexes.push({ q, r })
    }
  }
  
  return hexes
}

/**
 * Get the center position of the grid for camera targeting
 */
export function getGridCenter(width: number, height: number): { x: number; z: number } {
  const centerQ = (width - 1) / 2
  const centerR = (height - 1) / 2
  return axialToWorld(centerQ, centerR)
}

/**
 * Check if a position is within the grid bounds
 */
export function isInBounds(q: number, r: number, width: number, height: number): boolean {
  return q >= 0 && q < width && r >= 0 && r < height
}
