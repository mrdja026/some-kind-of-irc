"""
Game Service Module
Handles game state management, command parsing, and game logic for the #game channel.
"""
import random
import re
from typing import Optional, Tuple, Dict, Any, List, Set, cast
from sqlalchemy.orm import Session

from src.models.game_state import GameState
from src.models.game_session import GameSession
from src.models.user import User
from src.models.channel import Channel


# Grid constants
GRID_SIZE = 64
GRID_CENTER = GRID_SIZE // 2
DEFAULT_HEALTH = 100
MAX_HEALTH = 100
ATTACK_DAMAGE = 10
HEAL_AMOUNT = 15

OBSTACLES = [
    {"id": "stone-1", "type": "stone", "x": 12, "y": 12},
    {"id": "stone-2", "type": "stone", "x": 20, "y": 18},
    {"id": "stone-3", "type": "stone", "x": 42, "y": 40},
    {"id": "stone-4", "type": "stone", "x": 50, "y": 24},
    {"id": "tree-1", "type": "tree", "x": 16, "y": 44},
    {"id": "tree-2", "type": "tree", "x": 28, "y": 10},
    {"id": "tree-3", "type": "tree", "x": 36, "y": 30},
    {"id": "tree-4", "type": "tree", "x": 48, "y": 52},
]

NPC_PREFIX = "npc_"
GUEST_PREFIX = "guest_"
GUEST_USERNAME = "guest2"
ADMIN_NPC_USERNAME = "admina"


# Available game commands
GAME_COMMANDS = [
    "move up",
    "move down", 
    "move left",
    "move right",
    "attack",
    "heal"
]


class GameService:
    """Service for handling game mechanics and state management."""

    _channel_turn_user: Dict[int, int] = {}
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_game_state(self, user_id: int, channel_id: Optional[int] = None) -> GameState:
        """Get existing game state for user or create a new one."""
        game_state = self.db.query(GameState).filter(GameState.user_id == user_id).first()
        
        if not game_state:
            position = self._get_random_spawn_position(channel_id)
            game_state = GameState(
                user_id=user_id,
                position_x=position[0],
                position_y=position[1],
                health=DEFAULT_HEALTH,
                max_health=MAX_HEALTH,
            )
            self.db.add(game_state)
            self.db.commit()
            self.db.refresh(game_state)
        
        return game_state
    
    def get_or_create_game_session(self, user_id: int, channel_id: int) -> GameSession:
        """Get or create a game session linking user to game channel."""
        session = self.db.query(GameSession).filter(
            GameSession.user_id == user_id,
            GameSession.channel_id == channel_id,
            GameSession.is_active == True
        ).first()
        
        if not session:
            game_state = self.get_or_create_game_state(user_id, channel_id)
            session = GameSession(
                user_id=user_id,
                game_state_id=game_state.id,
                channel_id=channel_id,
                is_active=True
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

        self._ensure_turn_user(channel_id)
        
        return session
    
    def parse_command(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Parse a game command from a message.
        Returns (command, target_username) or None if not a valid command.
        """
        message_lower = message.lower().strip()
        
        # Pattern: command @username or just command
        # e.g., "move up @john" or "move up"
        mention_pattern = r'@(\w+)'
        mention_match = re.search(mention_pattern, message)
        target_username = mention_match.group(1) if mention_match else None
        
        # Remove the mention to get the command
        command_text = re.sub(mention_pattern, '', message_lower).strip()
        
        # Check if it's a valid command
        for cmd in GAME_COMMANDS:
            if command_text == cmd:
                return (cmd, target_username)
        
        return None
    
    def execute_command(
        self,
        command: str,
        executor_id: int,
        target_username: Optional[str] = None,
        channel_id: Optional[int] = None,
        force: bool = False,
        skip_npc: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a game command.
        Returns a dict with the result and updated state.
        """
        if channel_id is not None and not force:
            active_turn_user = self.get_active_turn_user_id(channel_id)
            if active_turn_user and active_turn_user != executor_id:
                return {
                    "success": False,
                    "error": "Not your turn",
                    "active_turn_user_id": active_turn_user,
                    "game_state": None,
                }
        # Get the target user (either from mention or self)
        if target_username:
            target_user = self.db.query(User).filter(User.username == target_username).first()
            if not target_user:
                return {
                    "success": False,
                    "error": f"User @{target_username} not found",
                    "game_state": None
                }
            target_id = cast(int, target_user.id)
        else:
            target_id = executor_id

        if channel_id is not None and not self._is_user_in_channel(target_id, channel_id):
            return {
                "success": False,
                "error": "Target user is not in the game channel",
                "game_state": None,
            }
        
        # Get or create game state for the target
        game_state = self.get_or_create_game_state(target_id, channel_id)
        game_state_user_id = cast(int, game_state.user_id)
        
        result = {
            "success": True,
            "command": command,
            "executor_id": executor_id,
            "target_id": target_id,
            "message": "",
            "game_state": None
        }
        
        current_x = cast(int, game_state.position_x)
        current_y = cast(int, game_state.position_y)
        if command == "move up":
            new_position = (current_x, current_y - 1)
            result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "move down":
            new_position = (current_x, current_y + 1)
            result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "move left":
            new_position = (current_x - 1, current_y)
            result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "move right":
            new_position = (current_x + 1, current_y)
            result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "attack":
            if target_id == executor_id:
                result["success"] = False
                result["error"] = "Cannot attack yourself! Use @username to target another player."
            else:
                current_health = cast(int, game_state.health)
                new_health = max(0, current_health - ATTACK_DAMAGE)
                setattr(game_state, "health", new_health)
                result["message"] = f"Attacked! Target health: {new_health}/{game_state.max_health}"
                if new_health == 0:
                    result["message"] += " - Target defeated!"
                    
        elif command == "heal":
            old_health = cast(int, game_state.health)
            max_health = cast(int, game_state.max_health)
            new_health = min(max_health, old_health + HEAL_AMOUNT)
            setattr(game_state, "health", new_health)
            healed = new_health - old_health
            result["message"] = f"Healed for {healed} HP! Health: {new_health}/{max_health}"
        
        if result["success"]:
            self.db.commit()
            self.db.refresh(game_state)
        else:
            self.db.rollback()
        
        # Add game state to result
        if result["success"]:
            result["game_state"] = {
                "user_id": game_state_user_id,
                "position_x": cast(int, game_state.position_x),
                "position_y": cast(int, game_state.position_y),
                "health": cast(int, game_state.health),
                "max_health": cast(int, game_state.max_health),
            }
        else:
            result["game_state"] = None

        if result["success"] and channel_id is not None:
            if force:
                result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)
            else:
                result["active_turn_user_id"] = self._advance_turn_user(channel_id)
                if not skip_npc:
                    self._process_npc_turns(channel_id)
                    result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)
        elif channel_id is not None:
            result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)
        
        return result
    
    def get_all_game_states_in_channel(self, channel_id: int) -> List[Dict[str, Any]]:
        """Get all game states for users in a specific game channel."""
        sessions = self.db.query(GameSession).filter(
            GameSession.channel_id == channel_id,
            GameSession.is_active == True
        ).all()
        
        states = []
        for session in sessions:
            user = self.db.query(User).filter(User.id == session.user_id).first()
            game_state = session.game_state
            if not game_state or not user:
                continue
            username = user.username
            username_value = str(username) if username is not None else ""
            username_lower = username_value.lower()
            if not (
                username_lower == GUEST_USERNAME
                or username_lower.startswith(NPC_PREFIX)
                or username_lower == ADMIN_NPC_USERNAME
            ):
                continue
            is_npc = bool(
                username_lower.startswith(NPC_PREFIX)
                or username_lower == ADMIN_NPC_USERNAME
            )
            states.append({
                "user_id": cast(int, user.id),
                "username": user.username,
                "display_name": user.display_name or user.username,
                "position_x": cast(int, game_state.position_x),
                "position_y": cast(int, game_state.position_y),
                "health": cast(int, game_state.health),
                "max_health": cast(int, game_state.max_health),
                "is_npc": is_npc,
            })
        
        return states

    def get_game_snapshot(self, channel_id: int) -> Dict[str, Any]:
        """Return a snapshot for the #game channel."""
        return {
            "map": {"width": GRID_SIZE, "height": GRID_SIZE, "center": GRID_CENTER},
            "players": self.get_all_game_states_in_channel(channel_id),
            "obstacles": self.get_obstacles(channel_id),
            "active_turn_user_id": self.get_active_turn_user_id(channel_id),
        }
    
    def get_available_commands(self) -> List[str]:
        """Return the list of available game commands."""
        return GAME_COMMANDS.copy()
    
    def is_game_channel(self, channel_name: str) -> bool:
        """Check if a channel is a game channel."""
        return channel_name.lower() == "#game" or channel_name.lower() == "game"
    
    def get_ascii_matrix(self, channel_id: int, grid_size: int = 20) -> str:
        """
        Generate an ASCII matrix representation of the game state.
        Shows a grid_size x grid_size portion of the map centered on players.
        """
        # Get all active players
        states = self.get_all_game_states_in_channel(channel_id)
        
        if not states:
            return "No players in game"
        
        # Find center of all players
        if len(states) > 0:
            avg_x = sum(s["position_x"] for s in states) // len(states)
            avg_y = sum(s["position_y"] for s in states) // len(states)
        else:
            avg_x, avg_y = GRID_SIZE // 2, GRID_SIZE // 2
        
        # Calculate bounds
        half_grid = grid_size // 2
        start_x = max(0, avg_x - half_grid)
        end_x = min(GRID_SIZE, start_x + grid_size)
        start_y = max(0, avg_y - half_grid)
        end_y = min(GRID_SIZE, start_y + grid_size)
        
        obstacles = self.get_obstacles(channel_id)
        obstacle_map = {(o["x"], o["y"]): o["type"] for o in obstacles}

        # Build player position map
        player_map = {}
        for state in states:
            x, y = state["position_x"], state["position_y"]
            if start_x <= x < end_x and start_y <= y < end_y:
                # Use first letter of username
                symbol = state["username"][0].upper()
                player_map[(x, y)] = f"{symbol}"
        
        # Build ASCII matrix
        lines = []
        lines.append(f"=== Game Map ({start_x},{start_y}) to ({end_x-1},{end_y-1}) ===")
        lines.append("   " + "".join(f"{x%10}" for x in range(start_x, end_x)))
        lines.append("  +" + "-" * (end_x - start_x) + "+")
        
        for y in range(start_y, end_y):
            row = f"{y:2}|"
            for x in range(start_x, end_x):
                if (x, y) in player_map:
                    row += player_map[(x, y)]
                elif (x, y) in obstacle_map:
                    row += "T" if obstacle_map[(x, y)] == "tree" else "S"
                else:
                    row += "."
            row += "|"
            lines.append(row)
        
        lines.append("  +" + "-" * (end_x - start_x) + "+")
        
        # Add legend
        lines.append("\nPlayers:")
        for state in states:
            hp_bar = "█" * (state["health"] // 10) + "░" * ((100 - state["health"]) // 10)
            lines.append(f"  {state['username'][0].upper()} = {state['username']} ({state['position_x']},{state['position_y']}) HP: [{hp_bar}] {state['health']}/100")
        
        return "\n".join(lines)
    
    def deactivate_session(self, user_id: int, channel_id: int) -> None:
        """Deactivate a user's game session when leaving the channel."""
        session = self.db.query(GameSession).filter(
            GameSession.user_id == user_id,
            GameSession.channel_id == channel_id,
            GameSession.is_active == True
        ).first()
        
        if session:
            setattr(session, "is_active", False)
            self.db.commit()

        if channel_id in self._channel_turn_user:
            self._ensure_turn_user(channel_id)

    def get_obstacles(self, channel_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return the obstacle list for a channel."""
        return [obstacle.copy() for obstacle in OBSTACLES]

    def get_active_turn_user_id(self, channel_id: int) -> Optional[int]:
        """Return the active turn user ID for a channel."""
        user_ids = self._get_active_user_ids(channel_id)
        if not user_ids:
            return None
        current = self._channel_turn_user.get(channel_id)
        if current not in user_ids:
            current = user_ids[0]
            self._channel_turn_user[channel_id] = current
        return current

    def set_active_turn_user(self, channel_id: int, user_id: int) -> None:
        user_ids = self._get_active_user_ids(channel_id)
        if not user_ids:
            return
        if user_id not in user_ids:
            return
        self._channel_turn_user[channel_id] = user_id

    def deactivate_other_guests(self, channel_id: int, keep_user_id: int) -> None:
        sessions = self.db.query(GameSession).filter(
            GameSession.channel_id == channel_id,
            GameSession.is_active == True,
        ).all()
        changed = False
        for session in sessions:
            session_user_id = cast(int, session.user_id)
            if session_user_id == keep_user_id:
                continue
            user = self.db.query(User).filter(User.id == session_user_id).first()
            if not user:
                continue
            username = cast(str, user.username)
            if username.lower().startswith(GUEST_PREFIX) and username.lower() != GUEST_USERNAME:
                setattr(session, "is_active", False)
                changed = True
        if changed:
            self.db.commit()

    def _advance_turn_user(self, channel_id: int) -> Optional[int]:
        user_ids = self._get_active_user_ids(channel_id)
        if not user_ids:
            return None
        current = self.get_active_turn_user_id(channel_id)
        if current not in user_ids:
            current = user_ids[0]
        index = user_ids.index(current)
        next_user = user_ids[(index + 1) % len(user_ids)]
        self._channel_turn_user[channel_id] = next_user
        return next_user

    def _ensure_turn_user(self, channel_id: int) -> None:
        if self.get_active_turn_user_id(channel_id) is None:
            self._channel_turn_user.pop(channel_id, None)

    def _get_active_user_ids(self, channel_id: int) -> List[int]:
        sessions = self.db.query(GameSession).filter(
            GameSession.channel_id == channel_id,
            GameSession.is_active == True,
        ).all()
        user_ids: List[int] = []
        for session in sessions:
            user = self.db.query(User).filter(User.id == session.user_id).first()
            if not user:
                continue
            username = cast(str, user.username)
            username_lower = username.lower()
            if username_lower == GUEST_USERNAME or username_lower.startswith(NPC_PREFIX):
                user_ids.append(cast(int, session.user_id))
        return sorted(user_ids)

    def _is_user_in_channel(self, user_id: int, channel_id: int) -> bool:
        session = self.db.query(GameSession).filter(
            GameSession.user_id == user_id,
            GameSession.channel_id == channel_id,
            GameSession.is_active == True,
        ).first()
        return session is not None

    def _get_obstacle_positions(self, channel_id: Optional[int]) -> Set[Tuple[int, int]]:
        return {(obstacle["x"], obstacle["y"]) for obstacle in self.get_obstacles(channel_id)}

    def _get_random_spawn_position(self, channel_id: Optional[int]) -> Tuple[int, int]:
        obstacle_positions = self._get_obstacle_positions(channel_id)
        occupied_positions = set()
        if channel_id is not None:
            for state in self.get_all_game_states_in_channel(channel_id):
                occupied_positions.add((state["position_x"], state["position_y"]))

        for _ in range(50):
            candidate = (random.randint(0, GRID_SIZE - 1), random.randint(0, GRID_SIZE - 1))
            if candidate in obstacle_positions or candidate in occupied_positions:
                continue
            return candidate
        return (GRID_CENTER, GRID_CENTER)

    def _is_blocked_position(
        self,
        position: Tuple[int, int],
        channel_id: Optional[int],
        exclude_user_id: Optional[int] = None,
    ) -> bool:
        if channel_id is None:
            return False
        if position in self._get_obstacle_positions(channel_id):
            return True
        for state in self.get_all_game_states_in_channel(channel_id):
            if exclude_user_id is not None and state["user_id"] == exclude_user_id:
                continue
            if (state["position_x"], state["position_y"]) == position:
                return True
        return False

    def _try_move(
        self,
        game_state: GameState,
        new_position: Tuple[int, int],
        channel_id: Optional[int],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        new_x, new_y = new_position
        if new_x < 0 or new_x >= GRID_SIZE or new_y < 0 or new_y >= GRID_SIZE:
            result["success"] = False
            result["error"] = "Cannot move - at grid boundary"
            return result
        if self._is_blocked_position(new_position, channel_id, cast(int, game_state.user_id)):
            result["success"] = False
            result["error"] = "Cannot move - blocked by obstacle or player"
            return result
        setattr(game_state, "position_x", new_x)
        setattr(game_state, "position_y", new_y)
        result["message"] = f"Moved to ({new_x}, {new_y})"
        return result

    def _is_npc_user(self, user_id: int) -> bool:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        username = cast(str, user.username)
        return username.lower().startswith(NPC_PREFIX)

    def _choose_npc_action(
        self,
        user_id: int,
        channel_id: int,
    ) -> Tuple[Optional[str], Optional[str]]:
        game_state = self.get_or_create_game_state(user_id, channel_id)
        npc_x = cast(int, game_state.position_x)
        npc_y = cast(int, game_state.position_y)

        adjacent_targets: List[str] = []
        for state in self.get_all_game_states_in_channel(channel_id):
            if state.get("user_id") == user_id:
                continue
            if state.get("is_npc", False):
                continue
            position_x = state.get("position_x")
            position_y = state.get("position_y")
            if position_x is None or position_y is None:
                continue
            if self._is_adjacent_position(
                (npc_x, npc_y),
                (int(position_x), int(position_y)),
            ):
                username = state.get("username")
                if username:
                    adjacent_targets.append(str(username))

        if adjacent_targets:
            return ("attack", random.choice(adjacent_targets))

        directions = [
            ("move up", (0, -1)),
            ("move down", (0, 1)),
            ("move left", (-1, 0)),
            ("move right", (1, 0)),
        ]
        valid_moves: List[str] = []
        for command, offset in directions:
            new_x = npc_x + offset[0]
            new_y = npc_y + offset[1]
            if new_x < 0 or new_x >= GRID_SIZE or new_y < 0 or new_y >= GRID_SIZE:
                continue
            if self._is_blocked_position((new_x, new_y), channel_id, user_id):
                continue
            valid_moves.append(command)

        if valid_moves:
            return (random.choice(valid_moves), None)

        if cast(int, game_state.health) < cast(int, game_state.max_health):
            return ("heal", None)

        return (None, None)

    def _is_adjacent_position(
        self,
        left: Tuple[int, int],
        right: Tuple[int, int],
    ) -> bool:
        return abs(left[0] - right[0]) + abs(left[1] - right[1]) == 1

    def _process_npc_turns(self, channel_id: int) -> None:
        active_ids = self._get_active_user_ids(channel_id)
        max_steps = max(1, len(active_ids))
        steps = 0
        while steps < max_steps:
            active_user = self.get_active_turn_user_id(channel_id)
            if active_user is None:
                return
            if not self._is_npc_user(active_user):
                return
            command, target_username = self._choose_npc_action(active_user, channel_id)
            if not command:
                self._advance_turn_user(channel_id)
                steps += 1
                continue
            result = self.execute_command(
                command,
                active_user,
                target_username,
                channel_id,
                force=False,
                skip_npc=True,
            )
            if not result.get("success"):
                self._advance_turn_user(channel_id)
            steps += 1
