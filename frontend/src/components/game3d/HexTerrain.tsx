import { useMemo } from 'react'
import { HexTile } from './HexTile'
import { generateHexGrid } from './hexUtils'
import type { Position } from '../../types'

interface HexTerrainProps {
  width?: number
  height?: number
  bufferTiles?: Position[]
  highlightedTiles?: Position[]
  onTileClick?: (position: Position) => void
}

/**
 * Renders a grid of hex tiles
 * Default 10x10 grid matching the game specification
 */
export function HexTerrain({
  width = 10,
  height = 10,
  bufferTiles = [],
  highlightedTiles = [],
  onTileClick,
}: HexTerrainProps) {
  const hexPositions = useMemo(() => generateHexGrid(width, height), [width, height])
  
  // Create a set for O(1) buffer tile lookup
  const bufferSet = useMemo(() => {
    const set = new Set<string>()
    for (const tile of bufferTiles) {
      set.add(`${tile.x}:${tile.y}`)
    }
    return set
  }, [bufferTiles])

  const highlightedSet = useMemo(() => {
    const set = new Set<string>()
    for (const tile of highlightedTiles) {
      set.add(`${tile.x}:${tile.y}`)
    }
    return set
  }, [highlightedTiles])

  return (
    <group name="hex-terrain">
      {hexPositions.map(({ q, r }) => (
        <HexTile
          key={`${q}-${r}`}
          q={q}
          r={r}
          isBuffer={bufferSet.has(`${q}:${r}`)}
          isHighlighted={highlightedSet.has(`${q}:${r}`)}
          onClick={(x, y) => onTileClick?.({ x, y })}
        />
      ))}
    </group>
  )
}
