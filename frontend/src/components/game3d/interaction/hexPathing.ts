import type { Position } from '../../../types'

export type MoveCommand = 'move_n' | 'move_ne' | 'move_se' | 'move_s' | 'move_sw' | 'move_nw'

const COMMAND_VECTORS: Record<MoveCommand, [number, number]> = {
  move_n: [0, -1],
  move_ne: [1, -1],
  move_se: [1, 0],
  move_s: [0, 1],
  move_sw: [-1, 1],
  move_nw: [-1, 0],
}

type Axial = { q: number; r: number }

function toKey(pos: Position): string {
  return `${pos.x}:${pos.y}`
}

function offsetToAxial(position: Position): Axial {
  const q = position.x - ((position.y - (position.y & 1)) >> 1)
  const r = position.y
  return { q, r }
}

function axialToOffset(axial: Axial): Position {
  const x = axial.q + ((axial.r - (axial.r & 1)) >> 1)
  const y = axial.r
  return { x, y }
}

export function neighborsWithCommands(position: Position): Array<{ position: Position; command: MoveCommand }> {
  const base = offsetToAxial(position)
  return (Object.entries(COMMAND_VECTORS) as Array<[MoveCommand, [number, number]]>).map(([command, [dq, dr]]) => {
    const next = axialToOffset({ q: base.q + dq, r: base.r + dr })
    return { position: next, command }
  })
}

export function commandFromStep(from: Position, to: Position): MoveCommand | null {
  const neighbor = neighborsWithCommands(from).find(
    ({ position }) => position.x === to.x && position.y === to.y
  )
  return neighbor?.command ?? null
}

export function hexDistanceOffset(left: Position, right: Position): number {
  const a = offsetToAxial(left)
  const b = offsetToAxial(right)
  const dq = a.q - b.q
  const dr = a.r - b.r
  const ds = -(a.q + a.r) + (b.q + b.r)
  return Math.max(Math.abs(dq), Math.abs(dr), Math.abs(ds))
}

interface FindPathOptions {
  width: number
  height: number
  blocked: Set<string>
}

export function findPathBfs(start: Position, target: Position, options: FindPathOptions): Array<Position> | null {
  if (start.x === target.x && start.y === target.y) {
    return [start]
  }

  const queue: Array<Position> = [start]
  const prev = new Map<string, string | null>()
  const byKey = new Map<string, Position>()
  const startKey = toKey(start)
  prev.set(startKey, null)
  byKey.set(startKey, start)

  while (queue.length > 0) {
    const current = queue.shift()
    if (!current) break

    for (const { position } of neighborsWithCommands(current)) {
      if (position.x < 0 || position.x >= options.width || position.y < 0 || position.y >= options.height) {
        continue
      }
      const key = toKey(position)
      if (prev.has(key)) continue
      if (options.blocked.has(key) && key !== toKey(target)) continue

      prev.set(key, toKey(current))
      byKey.set(key, position)
      if (position.x === target.x && position.y === target.y) {
        const path: Array<Position> = []
        let cursor: string | null = key
        while (cursor) {
          const pos = byKey.get(cursor)
          if (pos) path.push(pos)
          cursor = prev.get(cursor) ?? null
        }
        path.reverse()
        return path
      }
      queue.push(position)
    }
  }

  return null
}

export function pathToCommands(path: Array<Position>): Array<MoveCommand> {
  const commands: Array<MoveCommand> = []
  for (let i = 0; i < path.length - 1; i++) {
    const command = commandFromStep(path[i], path[i + 1])
    if (!command) return []
    commands.push(command)
  }
  return commands
}

