import logging
import random
from typing import Any, Dict, List, Set, Tuple


GRID_SIZE = 10
BUFFER_THICKNESS = 0
PLAY_MIN = 0
PLAY_MAX = GRID_SIZE - 1
TREE_CLUSTER_COUNT = 2
ROCK_CLUSTER_COUNT = 2
CLUSTER_MIN_SIZE = 2
CLUSTER_MAX_SIZE = 3
BLOCKING_TREE_COUNT = 6
BLOCKING_ROCK_COUNT = 4

# TODO(TD-Buffer): Revisit optional buffer-ring generation after spawn/move consistency issues are fully resolved.


logger = logging.getLogger(__name__)


class BattlefieldService:
    _channel_cache: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def get_or_create(cls, channel_id: int) -> Dict[str, Any]:
        cached = cls._channel_cache.get(channel_id)
        if cached is not None:
            return cached

        seed = channel_id * 1009 + 17
        rng = random.Random(seed)

        blocking_props, _used_positions = cls._build_blocking_props(rng)
        props = blocking_props
        obstacles = [
            {
                "id": prop["id"],
                "type": prop["type"],
                "position": dict(prop["position"]),
            }
            for prop in blocking_props
        ]
        buffer_tiles: List[Dict[str, int]] = []

        # P2/P3: Precompute static obstacle positions for O(1) collision checks
        obstacle_positions: Set[Tuple[int, int]] = {
            (prop["position"]["x"], prop["position"]["y"])
            for prop in blocking_props
        }

        generated = {
            "battlefield": {
                "seed": seed,
                "props": props,
                "buffer": {
                    "thickness": BUFFER_THICKNESS,
                    "tiles": buffer_tiles,
                },
            },
            "obstacles": obstacles,
            "obstacle_positions": obstacle_positions,  # P2/P3: Static set for fast lookup
        }

        cls._channel_cache[channel_id] = generated
        logger.info(
            "Generated battlefield channel_id=%s props=%s obstacles=%s buffer_tiles=%s",
            channel_id,
            len(props),
            len(obstacles),
            len(buffer_tiles),
        )
        return generated

    @classmethod
    def _build_blocking_props(
        cls,
        rng: random.Random,
    ) -> Tuple[List[Dict[str, Any]], Set[Tuple[int, int]]]:
        props: List[Dict[str, Any]] = []
        used: Set[Tuple[int, int]] = set()

        tree_positions = cls._build_clump_positions(
            rng,
            used,
            TREE_CLUSTER_COUNT,
            BLOCKING_TREE_COUNT,
        )
        for index, pos in enumerate(tree_positions):
            props.append(
                {
                    "id": f"tree-{index + 1}",
                    "type": "tree",
                    "position": {"x": pos[0], "y": pos[1]},
                    "is_blocking": True,
                    "zone": "play",
                }
            )

        rock_positions = cls._build_clump_positions(
            rng,
            used,
            ROCK_CLUSTER_COUNT,
            BLOCKING_ROCK_COUNT,
        )
        for index, pos in enumerate(rock_positions):
            props.append(
                {
                    "id": f"rock-{index + 1}",
                    "type": "rock",
                    "position": {"x": pos[0], "y": pos[1]},
                    "is_blocking": True,
                    "zone": "play",
                }
            )

        return props, used

    @classmethod
    def _build_clump_positions(
        cls,
        rng: random.Random,
        used: Set[Tuple[int, int]],
        cluster_count: int,
        total_target: int,
    ) -> List[Tuple[int, int]]:
        positions: List[Tuple[int, int]] = []
        if total_target <= 0:
            return positions

        for _ in range(cluster_count):
            if len(positions) >= total_target:
                break
            center = cls._pick_unique_play_position(rng, used)
            positions.append(center)
            remaining = total_target - len(positions)
            if remaining <= 0:
                break
            target_size = min(remaining + 1, rng.randint(CLUSTER_MIN_SIZE, CLUSTER_MAX_SIZE))
            cluster_count_now = 1
            frontier: List[Tuple[int, int]] = [center]
            while frontier and len(positions) < total_target and cluster_count_now < target_size:
                base = frontier.pop(0)
                neighbors = cls._shuffle_neighbors(rng, base)
                for candidate in neighbors:
                    if len(positions) >= total_target:
                        break
                    if candidate in used:
                        continue
                    if not cls._is_play_zone(candidate[0], candidate[1]):
                        continue
                    used.add(candidate)
                    positions.append(candidate)
                    frontier.append(candidate)
                    cluster_count_now += 1
                    if cluster_count_now >= target_size:
                        break

        while len(positions) < total_target:
            positions.append(cls._pick_unique_play_position(rng, used))
        return positions

    @classmethod
    def _shuffle_neighbors(
        cls,
        rng: random.Random,
        position: Tuple[int, int],
    ) -> List[Tuple[int, int]]:
        x, y = position
        candidates = [
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
            (x + 1, y - 1),
            (x - 1, y + 1),
        ]
        rng.shuffle(candidates)
        return candidates

    @classmethod
    def _pick_unique_play_position(
        cls,
        rng: random.Random,
        used: Set[Tuple[int, int]],
    ) -> Tuple[int, int]:
        for _ in range(300):
            x = rng.randint(PLAY_MIN, PLAY_MAX)
            y = rng.randint(PLAY_MIN, PLAY_MAX)
            position = (x, y)
            if position in used:
                continue
            used.add(position)
            return position
        fallback = (GRID_SIZE // 2, GRID_SIZE // 2)
        used.add(fallback)
        return fallback

    @staticmethod
    def _is_play_zone(x: int, y: int) -> bool:
        return PLAY_MIN <= x <= PLAY_MAX and PLAY_MIN <= y <= PLAY_MAX

    @classmethod
    def is_play_zone(cls, x: int, y: int) -> bool:
        return cls._is_play_zone(x, y)

    @classmethod
    def get_obstacle_positions(cls, channel_id: int) -> Set[Tuple[int, int]]:
        """P2/P3: Return precomputed static obstacle positions for O(1) collision checks.
        
        This is cached and never changes after generation (static obstacles only).
        """
        cached = cls.get_or_create(channel_id)
        return cached.get("obstacle_positions", set())
