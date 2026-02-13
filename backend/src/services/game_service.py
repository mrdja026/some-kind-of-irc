"""
Game Service Module
Handles game state management, command parsing, and game logic for the #game channel.
"""
import logging
import random
import re
from collections import deque
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List, Set, cast
from sqlalchemy.orm import Session

from src.models.game_state import GameState
from src.models.game_session import GameSession
from src.models.user import User
from src.models.channel import Channel
from src.services.battlefield_service import BattlefieldService, PLAY_MIN, PLAY_MAX
from src.services.websocket_manager import manager as ws_manager


# Grid constants
GRID_SIZE = 64
GRID_CENTER = GRID_SIZE // 2
DEFAULT_HEALTH = 100
MAX_HEALTH = 100
ATTACK_DAMAGE = 10
HEAL_AMOUNT = 15

DEFAULT_OBSTACLES = [
    {"id": "rock-1", "type": "rock", "x": 12, "y": 12},
    {"id": "rock-2", "type": "rock", "x": 20, "y": 18},
    {"id": "rock-3", "type": "rock", "x": 42, "y": 40},
    {"id": "rock-4", "type": "rock", "x": 50, "y": 24},
    {"id": "tree-1", "type": "tree", "x": 16, "y": 44},
    {"id": "tree-2", "type": "tree", "x": 28, "y": 10},
    {"id": "tree-3", "type": "tree", "x": 36, "y": 30},
    {"id": "tree-4", "type": "tree", "x": 48, "y": 52},
]

NPC_PREFIX = "npc_"
GUEST_PREFIX = "guest_"
GUEST_USERNAME = "guest2"
ADMIN_NPC_USERNAME = "admina"


logger = logging.getLogger(__name__)


# Available game commands
GAME_COMMANDS = [
    "move_up",
    "move_down",
    "move_left",
    "move_right",
    "attack",
    "heal"
]


class GameService:
    """Service for handling game mechanics and state management."""

    _channel_turn_user: Dict[int, int] = {}
    _channel_turn_order: Dict[int, List[int]] = {}
    _channel_priority_turns: Dict[int, deque[int]] = {}
    _channel_priority_resume_from: Dict[int, int] = {}
    _channel_status_history: Dict[int, deque[Dict[str, Any]]] = {}
    
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
        elif channel_id is not None:
            current_position = (
                cast(int, game_state.position_x),
                cast(int, game_state.position_y),
            )
            if (
                not BattlefieldService.is_play_zone(current_position[0], current_position[1])
                or self._is_blocked_position(current_position, channel_id, user_id)
            ):
                safe_position = self._get_random_spawn_position(channel_id)
                setattr(game_state, "position_x", safe_position[0])
                setattr(game_state, "position_y", safe_position[1])
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
        created = False
        
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
            created = True

        self._ensure_turn_user(channel_id)
        if created and self._is_admina_user(user_id):
            self._enqueue_priority_turns(channel_id, user_id, 2)
            self._record_status_note(
                channel_id,
                "turn_priority_inserted",
                "admina joined: queued 2 bonus turns",
                user_id,
            )
        
        return session
    
    def parse_command(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Parse a game command from a message.
        Returns (command, target_username) or None if not a valid command.
        """
        message_lower = message.lower().strip()
        
        # Pattern: command @username or just command
        # e.g., "move_up @john" or "move up"
        mention_pattern = r'@(\w+)'
        mention_match = re.search(mention_pattern, message)
        target_username = mention_match.group(1) if mention_match else None
        
        # Remove the mention to get the command
        command_text = re.sub(mention_pattern, '', message_lower).strip()
        
        normalized_command = re.sub(r"\s+", "_", command_text)

        # Check if it's a valid command
        if normalized_command in GAME_COMMANDS:
            return (normalized_command, target_username)
        
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
        if not isinstance(command, str):
            return {
                "success": False,
                "error": f"Invalid command: {command}",
                "game_state": None,
                "active_turn_user_id": self.get_active_turn_user_id(channel_id)
                if channel_id is not None
                else None,
            }

        normalized_command = re.sub(r"\s+", "_", command.lower().strip())

        if normalized_command not in GAME_COMMANDS:
            return {
                "success": False,
                "error": f"Invalid command: {command}",
                "game_state": None,
                "active_turn_user_id": self.get_active_turn_user_id(channel_id)
                if channel_id is not None
                else None,
            }

        command = normalized_command
        previous_turn_user_id = self.get_active_turn_user_id(channel_id) if channel_id is not None else None

        if channel_id is not None and not self._is_user_in_channel(executor_id, channel_id):
            return {
                "success": False,
                "error": "Game session not initialized. Connect WebSocket and send game_join first.",
                "game_state": None,
                "active_turn_user_id": self.get_active_turn_user_id(channel_id),
            }

        executor_user = self.db.query(User).filter(User.id == executor_id).first()
        if not executor_user:
            return {
                "success": False,
                "error": "Executor user not found",
                "game_state": None,
                "active_turn_user_id": self.get_active_turn_user_id(channel_id)
                if channel_id is not None
                else None,
            }
        executor_username = cast(str, executor_user.username)

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
            target_username_value = cast(str, target_user.username)
        else:
            target_id = executor_id
            target_username_value = executor_username

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
            "game_state": None,
            "executor_username": executor_username,
            "target_username": target_username_value,
            "position": None,
            "target_health": None,
            "target_max_health": None,
            "actor_health": None,
            "actor_max_health": None,
            "npc_actions": [],
        }
        
        current_x = cast(int, game_state.position_x)
        current_y = cast(int, game_state.position_y)
        if command == "move_up":
            new_position = (current_x, current_y - 1)
            result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "move_down":
            new_position = (current_x, current_y + 1)
            result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "move_left":
            new_position = (current_x - 1, current_y)
            result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "move_right":
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
                result["target_health"] = new_health
                result["target_max_health"] = cast(int, game_state.max_health)
                if new_health == 0:
                    result["message"] += " - Target defeated!"
                    
        elif command == "heal":
            old_health = cast(int, game_state.health)
            max_health = cast(int, game_state.max_health)
            new_health = min(max_health, old_health + HEAL_AMOUNT)
            setattr(game_state, "health", new_health)
            healed = new_health - old_health
            result["message"] = f"Healed for {healed} HP! Health: {new_health}/{max_health}"
            result["target_health"] = new_health
            result["target_max_health"] = max_health
        
        if result["success"]:
            self.db.commit()
            self.db.refresh(game_state)
        else:
            self.db.rollback()
        
        # Add game state to result
        if result["success"]:
            result["game_state"] = {
                "user_id": game_state_user_id,
                "position": {
                    "x": cast(int, game_state.position_x),
                    "y": cast(int, game_state.position_y),
                },
                "position_x": cast(int, game_state.position_x),
                "position_y": cast(int, game_state.position_y),
                "health": cast(int, game_state.health),
                "max_health": cast(int, game_state.max_health),
            }
            if command.startswith("move_"):
                result["position"] = {
                    "x": cast(int, game_state.position_x),
                    "y": cast(int, game_state.position_y),
                }
            executor_state = self.get_or_create_game_state(executor_id, channel_id)
            result["actor_health"] = cast(int, executor_state.health)
            result["actor_max_health"] = cast(int, executor_state.max_health)
        else:
            result["game_state"] = None

        if result["success"] and channel_id is not None:
            if force:
                result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)
            else:
                result["active_turn_user_id"] = self._advance_turn_user(channel_id)
                if not skip_npc:
                    result["npc_actions"] = self._process_npc_turns(channel_id)
                    result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)
        elif channel_id is not None:
            result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)

        if channel_id is not None:
            self._record_status_event(channel_id, result, previous_turn_user_id)
        
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
            is_npc = self._is_npc_username(username_value)
            states.append({
                "user_id": cast(int, user.id),
                "username": user.username,
                "display_name": user.display_name or user.username,
                "position": {
                    "x": cast(int, game_state.position_x),
                    "y": cast(int, game_state.position_y)
                },
                "health": cast(int, game_state.health),
                "max_health": cast(int, game_state.max_health),
                "is_active": True,
                "is_npc": is_npc,
            })
        
        return states

    def get_game_snapshot(self, channel_id: int) -> Dict[str, Any]:
        """Return a snapshot for the #game channel."""
        self._normalize_channel_positions(channel_id)
        players = self.get_all_game_states_in_channel(channel_id)
        battlefield = self.get_battlefield(channel_id)
        obstacles = self.get_obstacles(channel_id)
        buffer = cast(Dict[str, Any], battlefield.get("buffer", {}))
        props = cast(List[Dict[str, Any]], battlefield.get("props", []))
        buffer_tiles = cast(List[Dict[str, int]], buffer.get("tiles", []))
        logger.info(
            "Snapshot channel_id=%s players=%s obstacles=%s props=%s buffer_tiles=%s",
            channel_id,
            len(players),
            len(obstacles),
            len(props),
            len(buffer_tiles),
        )
        return {
            "type": "game_snapshot",
            "timestamp": None,  # To be filled by websocket manager
            "payload": {
                "map": {
                    "width": GRID_SIZE,
                    "height": GRID_SIZE,
                    "grid_max_index": GRID_SIZE - 1,
                    "play_min": PLAY_MIN,
                    "play_max": PLAY_MAX,
                },
                "players": players,
                "obstacles": obstacles,
                "battlefield": battlefield,
                "active_turn_user_id": self.get_active_turn_user_id(channel_id),
                "status_history": self.get_status_history(channel_id),
            }
        }

    def get_game_state_update(self, channel_id: int) -> Dict[str, Any]:
        """Return an incremental update for the game channel.

        Note: Battlefield payload is snapshot-only to keep updates lightweight.
        """
        return {
            "type": "game_state_update",
            "timestamp": None,
            "payload": {
                "active_turn_user_id": self.get_active_turn_user_id(channel_id),
                "players": self.get_all_game_states_in_channel(channel_id),
                "status_history": self.get_status_history(channel_id),
            }
        }

    def get_status_history(self, channel_id: int) -> List[Dict[str, Any]]:
        history = self._channel_status_history.get(channel_id)
        if history is None:
            return []
        return list(history)
    
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
            avg_x = sum(int(cast(Dict[str, Any], s["position"])["x"]) for s in states) // len(states)
            avg_y = sum(int(cast(Dict[str, Any], s["position"])["y"]) for s in states) // len(states)
        else:
            avg_x, avg_y = GRID_SIZE // 2, GRID_SIZE // 2
        
        # Calculate bounds
        half_grid = grid_size // 2
        start_x = max(0, avg_x - half_grid)
        end_x = min(GRID_SIZE, start_x + grid_size)
        start_y = max(0, avg_y - half_grid)
        end_y = min(GRID_SIZE, start_y + grid_size)
        
        obstacles = self.get_obstacles(channel_id)
        obstacle_map = {
            (o["position"]["x"], o["position"]["y"]): o["type"]
            for o in obstacles
        }

        # Build player position map
        player_map = {}
        for state in states:
            position = cast(Dict[str, Any], state["position"])
            x = int(position["x"])
            y = int(position["y"])
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
            position = cast(Dict[str, Any], state["position"])
            lines.append(
                f"  {state['username'][0].upper()} = {state['username']} "
                f"({position['x']},{position['y']}) HP: [{hp_bar}] {state['health']}/100"
            )
        
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
        if channel_id is not None:
            generated = BattlefieldService.get_or_create(channel_id)
            return cast(List[Dict[str, Any]], generated.get("obstacles", []))
        return [
            {
                "id": obstacle["id"],
                "type": obstacle["type"],
                "position": {"x": obstacle["x"], "y": obstacle["y"]}
            }
            for obstacle in DEFAULT_OBSTACLES
        ]

    def get_battlefield(self, channel_id: int) -> Dict[str, Any]:
        generated = BattlefieldService.get_or_create(channel_id)
        return cast(Dict[str, Any], generated.get("battlefield", {}))

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
        """Advance to the next active user, consuming priority turns first."""
        user_ids = self._get_active_user_ids(channel_id)
        if not user_ids:
            return None

        current = self.get_active_turn_user_id(channel_id)
        if current not in user_ids:
            current = user_ids[0]

        priority_queue = self._channel_priority_turns.get(channel_id)
        while priority_queue and len(priority_queue) > 0:
            if channel_id not in self._channel_priority_resume_from and current in user_ids:
                self._channel_priority_resume_from[channel_id] = current
            candidate_id = int(priority_queue.popleft())
            if candidate_id not in user_ids:
                continue
            if self._is_npc_user(candidate_id) or not ws_manager.is_client_stale(candidate_id):
                self._channel_turn_user[channel_id] = candidate_id
                return candidate_id

        resume_from = self._channel_priority_resume_from.pop(channel_id, None)
        if resume_from in user_ids:
            current = cast(int, resume_from)

        # P6: Find next non-stale user, skipping stale clients
        start_index = user_ids.index(current)
        for offset in range(1, len(user_ids) + 1):
            candidate_index = (start_index + offset) % len(user_ids)
            candidate_id = user_ids[candidate_index]
            
            # NPCs are never stale (they don't have WebSocket connections)
            if self._is_npc_user(candidate_id):
                self._channel_turn_user[channel_id] = candidate_id
                return candidate_id
            
            # P6: Skip stale human clients
            if not ws_manager.is_client_stale(candidate_id):
                self._channel_turn_user[channel_id] = candidate_id
                return candidate_id
            
            logger.info(
                "P6: Skipping stale client user_id=%s in channel_id=%s",
                candidate_id,
                channel_id,
            )
        
        # All users are stale - fall back to simple round-robin
        next_user = user_ids[(start_index + 1) % len(user_ids)]
        self._channel_turn_user[channel_id] = next_user
        return next_user

    def _ensure_turn_user(self, channel_id: int) -> None:
        user_ids = self._get_active_user_ids(channel_id)
        if not user_ids:
            self._channel_turn_user.pop(channel_id, None)
            self._channel_turn_order.pop(channel_id, None)
            self._channel_priority_turns.pop(channel_id, None)
            self._channel_priority_resume_from.pop(channel_id, None)
            self._channel_status_history.pop(channel_id, None)
            return
        current = self._channel_turn_user.get(channel_id)
        if current not in user_ids:
            self._channel_turn_user[channel_id] = user_ids[0]

    def _get_active_user_ids_from_sessions(self, channel_id: int) -> List[int]:
        sessions = self.db.query(GameSession).filter(
            GameSession.channel_id == channel_id,
            GameSession.is_active == True,
        ).all()
        user_ids: List[int] = []
        for session in sessions:
            user_ids.append(cast(int, session.user_id))
        return sorted(user_ids)

    def _get_active_user_ids(self, channel_id: int) -> List[int]:
        active_user_ids = self._get_active_user_ids_from_sessions(channel_id)
        active_set: Set[int] = set(active_user_ids)
        previous_order = self._channel_turn_order.get(channel_id, [])
        turn_order: List[int] = []
        for user_id in previous_order:
            if user_id in active_set:
                turn_order.append(user_id)
        for user_id in active_user_ids:
            if user_id not in turn_order:
                turn_order.append(user_id)
        self._channel_turn_order[channel_id] = turn_order
        return turn_order

    def _is_user_in_channel(self, user_id: int, channel_id: int) -> bool:
        session = self.db.query(GameSession).filter(
            GameSession.user_id == user_id,
            GameSession.channel_id == channel_id,
            GameSession.is_active == True,
        ).first()
        return session is not None

    def _get_obstacle_positions(self, channel_id: Optional[int]) -> Set[Tuple[int, int]]:
        """P2/P3: Use cached static obstacle positions for O(1) lookup."""
        if channel_id is not None:
            return BattlefieldService.get_obstacle_positions(channel_id)
        # Fallback for no channel (shouldn't happen in normal flow)
        return {
            (obstacle["position"]["x"], obstacle["position"]["y"])
            for obstacle in self.get_obstacles(channel_id)
        }

    def _get_random_spawn_position(self, channel_id: Optional[int]) -> Tuple[int, int]:
        """Get a random spawn position that avoids obstacles and other players.
        """
        obstacle_positions = self._get_obstacle_positions(channel_id)
        occupied_positions = obstacle_positions.copy()
        if channel_id is not None:
            for state in self.get_all_game_states_in_channel(channel_id):
                position = cast(Dict[str, Any], state["position"])
                occupied_positions.add((int(position["x"]), int(position["y"])))

        for _ in range(50):
            candidate = (random.randint(PLAY_MIN, PLAY_MAX), random.randint(PLAY_MIN, PLAY_MAX))
            nearest = self._find_nearest_free_spawn(candidate, occupied_positions)
            if nearest is not None:
                return nearest

        start = (GRID_CENTER, GRID_CENTER)
        nearest_center = self._find_nearest_free_spawn(start, occupied_positions)
        if nearest_center is not None:
            return nearest_center

        first_free = self._find_first_free_cell(occupied_positions)
        if first_free is not None:
            return first_free

        logger.warning(
            "No free spawn position found in channel_id=%s (obstacles=%s, occupied=%s), using fallback center",
            channel_id,
            len(obstacle_positions),
            len(occupied_positions)
        )
        return (GRID_CENTER, GRID_CENTER)

    def _find_nearest_free_spawn(
        self,
        start: Tuple[int, int],
        occupied_positions: Set[Tuple[int, int]],
    ) -> Optional[Tuple[int, int]]:
        sx, sy = start
        if not BattlefieldService.is_play_zone(sx, sy):
            return None
        queue: deque[Tuple[int, int]] = deque([start])
        visited: Set[Tuple[int, int]] = {start}
        directions: Tuple[Tuple[int, int], ...] = ((0, -1), (0, 1), (-1, 0), (1, 0))
        while queue:
            x, y = queue.popleft()
            current = (x, y)
            if current not in occupied_positions:
                return current
            for dx, dy in directions:
                nx = x + dx
                ny = y + dy
                neighbor = (nx, ny)
                if neighbor in visited:
                    continue
                if not BattlefieldService.is_play_zone(nx, ny):
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        return None

    def _find_first_free_cell(self, occupied_positions: Set[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        for y in range(PLAY_MIN, PLAY_MAX + 1):
            for x in range(PLAY_MIN, PLAY_MAX + 1):
                candidate = (x, y)
                if candidate in occupied_positions:
                    continue
                if not BattlefieldService.is_play_zone(x, y):
                    continue
                return candidate
        return None

    def _get_player_positions(self, channel_id: int, exclude_user_id: Optional[int] = None) -> Set[Tuple[int, int]]:
        """P2: Build player position set for O(1) collision lookup.
        
        Only called during active player's turn - not every frame.
        """
        positions: Set[Tuple[int, int]] = set()
        for state in self.get_all_game_states_in_channel(channel_id):
            if exclude_user_id is not None and state["user_id"] == exclude_user_id:
                continue
            state_position = cast(Dict[str, Any], state["position"])
            positions.add((int(state_position["x"]), int(state_position["y"])))
        return positions

    def _is_blocked_position(
        self,
        position: Tuple[int, int],
        channel_id: Optional[int],
        exclude_user_id: Optional[int] = None,
    ) -> bool:
        """P2/P3: Optimized collision check using cached obstacle positions.
        
        Static obstacles use O(1) cached set lookup.
        Player positions checked only when needed (during move validation).
        """
        if channel_id is None:
            return False
        # P3: Static obstacles - O(1) lookup from cached set
        if position in self._get_obstacle_positions(channel_id):
            return True
        # P2: Dynamic player positions - only check when validating a move
        if position in self._get_player_positions(channel_id, exclude_user_id):
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
        if not BattlefieldService.is_play_zone(new_x, new_y):
            result["success"] = False
            result["error"] = "Cannot move - outside battle zone"
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
        return self._is_npc_username(username)

    def _is_npc_username(self, username: str) -> bool:
        username_lower = username.lower()
        return username_lower.startswith(NPC_PREFIX) or username_lower == ADMIN_NPC_USERNAME

    def _is_admina_user(self, user_id: int) -> bool:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        username = cast(str, user.username)
        return username.lower() == ADMIN_NPC_USERNAME

    def _enqueue_priority_turns(self, channel_id: int, user_id: int, turns: int) -> None:
        if turns <= 0:
            return
        queue = self._channel_priority_turns.get(channel_id)
        if queue is None:
            queue = deque()
            self._channel_priority_turns[channel_id] = queue
        for _ in range(turns):
            queue.append(user_id)

    def _status_history_queue(self, channel_id: int) -> deque[Dict[str, Any]]:
        history = self._channel_status_history.get(channel_id)
        if history is None:
            history = deque(maxlen=10)
            self._channel_status_history[channel_id] = history
        return history

    def _record_status_note(
        self,
        channel_id: int,
        event_type: str,
        message: str,
        executor_id: Optional[int] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "message": message,
            "executor_id": executor_id,
        }
        self._status_history_queue(channel_id).append(event)

    def _record_status_event(
        self,
        channel_id: int,
        result: Dict[str, Any],
        before_turn_user_id: Optional[int],
    ) -> None:
        message = str(result.get("message", ""))
        if message == "" and result.get("error") is not None:
            message = str(result.get("error", ""))
        event: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "action_result",
            "success": bool(result.get("success", False)),
            "action_type": str(result.get("command", "")),
            "executor_id": int(result.get("executor_id", 0)),
            "executor_username": result.get("executor_username"),
            "target_id": result.get("target_id"),
            "target_username": result.get("target_username"),
            "message": message,
            "before_turn_user_id": before_turn_user_id,
            "after_turn_user_id": result.get("active_turn_user_id"),
            "position": result.get("position"),
            "target_health": result.get("target_health"),
            "target_max_health": result.get("target_max_health"),
            "actor_health": result.get("actor_health"),
            "actor_max_health": result.get("actor_max_health"),
        }
        self._status_history_queue(channel_id).append(event)

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
            position = state.get("position")
            if not isinstance(position, dict):
                continue
            position_x = position.get("x")
            position_y = position.get("y")
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
            ("move_up", (0, -1)),
            ("move_down", (0, 1)),
            ("move_left", (-1, 0)),
            ("move_right", (1, 0)),
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

    def _normalize_channel_positions(self, channel_id: int) -> None:
        """Ensure all active players are inside play zone and not on blocked cells.

        Placement strategy is two-pass:
        1) Keep deterministic blocked set from generated obstacle clusters.
        2) Place/repair each active player's spawn against that blocked set,
           using BFS from current position to the nearest free cell.
        """
        sessions = self.db.query(GameSession).filter(
            GameSession.channel_id == channel_id,
            GameSession.is_active == True,
        ).order_by(GameSession.id.asc()).all()
        obstacle_positions: Set[Tuple[int, int]] = self._get_obstacle_positions(channel_id)
        occupied_positions: Set[Tuple[int, int]] = set(obstacle_positions)
        changed = False
        for session in sessions:
            game_state = session.game_state
            if game_state is None:
                continue
            current_x = cast(int, game_state.position_x)
            current_y = cast(int, game_state.position_y)
            position = (current_x, current_y)
            if BattlefieldService.is_play_zone(current_x, current_y) and position not in occupied_positions:
                occupied_positions.add(position)
                continue

            seed_position = position
            if not BattlefieldService.is_play_zone(current_x, current_y):
                seed_position = (GRID_CENTER, GRID_CENTER)

            nearest = self._find_nearest_free_spawn(seed_position, occupied_positions)
            if nearest is None:
                nearest = self._find_first_free_cell(occupied_positions)
            if nearest is None:
                logger.warning("Failed to normalize spawn for user_id=%s in channel_id=%s", session.user_id, channel_id)
                continue
            new_x, new_y = nearest
            setattr(game_state, "position_x", new_x)
            setattr(game_state, "position_y", new_y)
            occupied_positions.add((new_x, new_y))
            changed = True
        if changed:
            self.db.commit()

    def _process_npc_turns(self, channel_id: int) -> List[Dict[str, Any]]:
        npc_actions: List[Dict[str, Any]] = []
        active_ids = self._get_active_user_ids(channel_id)
        priority_queue = self._channel_priority_turns.get(channel_id)
        priority_count = len(priority_queue) if priority_queue is not None else 0
        max_steps = max(1, len(active_ids) + priority_count)
        steps = 0
        while steps < max_steps:
            active_user = self.get_active_turn_user_id(channel_id)
            if active_user is None:
                return npc_actions
            if not self._is_npc_user(active_user):
                return npc_actions
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
            else:
                npc_actions.append(result)
            steps += 1
        return npc_actions
