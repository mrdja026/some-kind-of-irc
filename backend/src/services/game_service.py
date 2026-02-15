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
from src.services.battlefield_service import BattlefieldService, PLAY_MIN, PLAY_MAX, GRID_SIZE
from src.services.websocket_manager import manager as ws_manager


# Grid constants
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


logger = logging.getLogger(__name__)


# Available game commands
GAME_COMMANDS = [
    "move_n",
    "move_ne",
    "move_se",
    "move_s",
    "move_sw",
    "move_nw",
    "attack",
    "heal",
    "end_turn",
]

LEGACY_COMMAND_ALIASES: Dict[str, str] = {
    "move_up": "move_n",
    "move_down": "move_s",
    "move_left": "move_sw",
    "move_right": "move_se",
}


class GameService:
    """Service for handling game mechanics and state management."""

    _channel_turn_user: Dict[int, int] = {}
    _channel_turn_order: Dict[int, List[int]] = {}
    _channel_priority_turns: Dict[int, deque[int]] = {}
    _channel_priority_resume_from: Dict[int, int] = {}
    _channel_status_history: Dict[int, deque[Dict[str, Any]]] = {}
    _channel_human_user: Dict[int, int] = {}
    _channel_forced_npc_users: Dict[int, Set[int]] = {}
    _channel_turn_budget: Dict[int, Dict[str, int]] = {}
    _channel_turn_context_cache: Dict[int, Dict[str, Any]] = {}
    
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

    def bootstrap_small_arena_join(self, user_id: int, channel_id: int) -> None:
        """Initialize/refresh small-arena state for a successful game_join handshake."""
        self.get_battlefield(channel_id)
        self.get_or_create_game_session(user_id, channel_id)
        self.get_or_create_game_state(user_id, channel_id)
        self._assign_joiner_role(user_id, channel_id)

        if channel_id not in self._channel_turn_user:
            human_id = self._channel_human_user.get(channel_id)
            if human_id is not None and self._is_user_in_channel(human_id, channel_id):
                self._channel_turn_user[channel_id] = human_id
    
    def parse_command(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Parse a game command from a message.
        Returns (command, target_username) or None if not a valid command.
        """
        message_lower = message.lower().strip()
        
        # Pattern: command @username or just command
        # e.g., "move_ne @john" or "move ne"
        mention_pattern = r'@(\w+)'
        mention_match = re.search(mention_pattern, message)
        target_username = mention_match.group(1) if mention_match else None
        
        # Remove the mention to get the command
        command_text = re.sub(mention_pattern, '', message_lower).strip()
        
        normalized_command = re.sub(r"\s+", "_", command_text)
        normalized_command = LEGACY_COMMAND_ALIASES.get(normalized_command, normalized_command)

        # Check if it's a valid command
        if normalized_command in GAME_COMMANDS:
            return (normalized_command, target_username)
        
        return None

    def _build_command_error_result(
        self,
        command: str,
        executor_id: int,
        error: str,
        channel_id: Optional[int],
        executor_username: str = "",
        target_id: Optional[int] = None,
        target_username: str = "",
    ) -> Dict[str, Any]:
        resolved_target_id = target_id if target_id is not None else executor_id
        resolved_target_username = target_username if target_username != "" else executor_username
        return {
            "success": False,
            "command": command,
            "executor_id": executor_id,
            "target_id": resolved_target_id,
            "message": "",
            "error": error,
            "game_state": None,
            "executor_username": executor_username,
            "target_username": resolved_target_username,
            "position": None,
            "target_health": None,
            "target_max_health": None,
            "actor_health": None,
            "actor_max_health": None,
            "npc_actions": [],
            "active_turn_user_id": self.get_active_turn_user_id(channel_id)
            if channel_id is not None
            else None,
        }
    
    def execute_command(
        self,
        command: str,
        executor_id: int,
        target_username: Optional[str] = None,
        channel_id: Optional[int] = None,
        force: bool = False,
        advance_turn: bool = True,
        enforce_turn_budget: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a game command.
        Returns a dict with the result and updated state.
        """
        command_token = str(command)
        if not isinstance(command, str):
            return self._build_command_error_result(
                command=command_token,
                executor_id=executor_id,
                error=f"Invalid command: {command}",
                channel_id=channel_id,
            )

        normalized_command = re.sub(r"\s+", "_", command.lower().strip())
        normalized_command = LEGACY_COMMAND_ALIASES.get(normalized_command, normalized_command)
        command_token = normalized_command

        if normalized_command not in GAME_COMMANDS:
            return self._build_command_error_result(
                command=command_token,
                executor_id=executor_id,
                error=f"Invalid command: {command}",
                channel_id=channel_id,
            )

        command = normalized_command
        previous_turn_user_id = self.get_active_turn_user_id(channel_id) if channel_id is not None else None

        if channel_id is not None and not self._is_user_in_channel(executor_id, channel_id):
            return self._build_command_error_result(
                command=command,
                executor_id=executor_id,
                error="Game session not initialized. Connect WebSocket and send game_join first.",
                channel_id=channel_id,
            )

        executor_user = self.db.query(User).filter(User.id == executor_id).first()
        if not executor_user:
            return self._build_command_error_result(
                command=command,
                executor_id=executor_id,
                error="Executor user not found",
                channel_id=channel_id,
            )
        executor_username = cast(str, executor_user.username)

        if channel_id is not None and force:
            return self._build_command_error_result(
                command=command,
                executor_id=executor_id,
                error="Force commands are disabled in small-arena",
                channel_id=channel_id,
                executor_username=executor_username,
            )

        if channel_id is not None:
            active_turn_user = self.get_active_turn_user_id(channel_id)
            if active_turn_user and active_turn_user != executor_id:
                return self._build_command_error_result(
                    command=command,
                    executor_id=executor_id,
                    error="Not your turn",
                    channel_id=channel_id,
                    executor_username=executor_username,
                )

        if channel_id is not None and enforce_turn_budget:
            turn_budget = self._ensure_turn_budget(channel_id)
            moves_used = int(turn_budget.get("moves_used", 0))
            actions_used = int(turn_budget.get("actions_used", 0))
            if command.startswith("move_") and moves_used >= 2:
                return self._build_command_error_result(
                    command=command,
                    executor_id=executor_id,
                    error="Turn budget exceeded: maximum 2 moves per turn",
                    channel_id=channel_id,
                    executor_username=executor_username,
                )
            if command in ("attack", "heal") and actions_used >= 1:
                return self._build_command_error_result(
                    command=command,
                    executor_id=executor_id,
                    error="Turn budget exceeded: maximum 1 action per turn",
                    channel_id=channel_id,
                    executor_username=executor_username,
                )
        # Get the target user (either from mention or self)
        if target_username:
            target_user = self.db.query(User).filter(User.username == target_username).first()
            if not target_user:
                return self._build_command_error_result(
                    command=command,
                    executor_id=executor_id,
                    error=f"User @{target_username} not found",
                    channel_id=channel_id,
                    executor_username=executor_username,
                    target_username=target_username,
                )
            target_id = cast(int, target_user.id)
            target_username_value = cast(str, target_user.username)
        else:
            target_id = executor_id
            target_username_value = executor_username

        if channel_id is not None and not self._is_user_in_channel(target_id, channel_id):
            return self._build_command_error_result(
                command=command,
                executor_id=executor_id,
                error="Target user is not in the game channel",
                channel_id=channel_id,
                executor_username=executor_username,
                target_id=target_id,
                target_username=target_username_value,
            )
        
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

        if command.startswith("move_"):
            new_position = self._resolve_move_target(
                (cast(int, game_state.position_x), cast(int, game_state.position_y)),
                command,
            )
            if new_position is None:
                result["success"] = False
                result["error"] = f"Invalid movement command: {command}"
            else:
                result = self._try_move(game_state, new_position, channel_id, result)
                
        elif command == "attack":
            if target_id == executor_id:
                result["success"] = False
                result["error"] = "Cannot attack yourself! Use @username to target another player."
            else:
                executor_state = self.get_or_create_game_state(executor_id, channel_id)
                executor_position = (
                    cast(int, executor_state.position_x),
                    cast(int, executor_state.position_y),
                )
                target_position = (
                    cast(int, game_state.position_x),
                    cast(int, game_state.position_y),
                )
                if not self._is_adjacent_position(executor_position, target_position):
                    result["success"] = False
                    result["error"] = "Target out of range (requires 1-hex adjacency)"
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
        elif command == "end_turn":
            result["message"] = "Ended turn"
        
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
            if enforce_turn_budget:
                self._consume_turn_budget(channel_id, command)

            if not advance_turn:
                result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)
            elif command.startswith("move_"):
                result["active_turn_user_id"] = self.get_active_turn_user_id(channel_id)
            else:
                result["active_turn_user_id"] = self._advance_turn_user(channel_id)
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
            is_npc = self._is_npc_user(cast(int, user.id), channel_id)
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
        turn_context = self._build_turn_context(
            channel_id,
            players=players,
            obstacles=obstacles,
            battlefield=battlefield,
        )
        return {
            "type": "game_snapshot",
            "timestamp": None,  # To be filled by websocket manager
            "payload": {
                "map": {
                    "board_type": "staggered_hex",
                    "layout": "odd_r",
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
                "turn_context": turn_context,
                "status_history": self.get_status_history(channel_id),
            }
        }

    def get_game_state_update(self, channel_id: int) -> Dict[str, Any]:
        """Return an incremental update for the game channel.

        Note: Battlefield payload is snapshot-only to keep updates lightweight.
        """
        players = self.get_all_game_states_in_channel(channel_id)
        return {
            "type": "game_state_update",
            "timestamp": None,
            "payload": {
                "active_turn_user_id": self.get_active_turn_user_id(channel_id),
                "players": players,
                "turn_context": self._build_turn_context(channel_id, players=players),
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

        forced_npcs = self._channel_forced_npc_users.get(channel_id)
        if forced_npcs is not None:
            forced_npcs.discard(user_id)

        current_human = self._channel_human_user.get(channel_id)
        if current_human == user_id:
            self._channel_human_user.pop(channel_id, None)

        if channel_id in self._channel_turn_user:
            self._ensure_turn_user(channel_id)

    def is_npc_turn(self, channel_id: int) -> bool:
        active_user_id = self.get_active_turn_user_id(channel_id)
        if active_user_id is None:
            return False
        return self._is_npc_user(active_user_id, channel_id)

    def process_npc_turn_chain(self, channel_id: int) -> List[Dict[str, Any]]:
        npc_steps: List[Dict[str, Any]] = []
        active_ids = self._get_active_user_ids(channel_id)
        if not active_ids:
            return npc_steps

        max_npc_turns = max(1, len(active_ids))
        turns_processed = 0
        while turns_processed < max_npc_turns:
            active_user = self.get_active_turn_user_id(channel_id)
            if active_user is None or not self._is_npc_user(active_user, channel_id):
                break

            step_results = self._run_npc_turn_program(active_user, channel_id)
            if not step_results:
                step_results = [
                    self._build_npc_noop_result(
                        active_user,
                        channel_id,
                        "NPC had no executable turn step",
                    )
                ]

            for index, step_result in enumerate(step_results):
                if index == len(step_results) - 1:
                    step_result["active_turn_user_id"] = self._advance_turn_user(channel_id)
                else:
                    step_result["active_turn_user_id"] = active_user

                if step_result.get("command") == "npc_noop":
                    self._record_status_event(channel_id, step_result, active_user)

                npc_steps.append(
                    {
                        "action_result": step_result,
                        "state_update": self.get_game_state_update(channel_id),
                    }
                )

            turns_processed += 1

        return npc_steps

    async def process_npc_turn_chain_or_apply_results(
        self,
        channel_id: int,
        manager: Any,
    ) -> List[Dict[str, Any]]:
        """Process queued NPC turns and broadcast valid action/state updates."""
        if not self.is_npc_turn(channel_id):
            return []

        npc_steps = self.process_npc_turn_chain(channel_id)
        for step in npc_steps:
            if not isinstance(step, dict):
                continue
            npc_action = step.get("action_result", {})
            npc_update = step.get("state_update", {})
            if not isinstance(npc_action, dict):
                continue
            if not isinstance(npc_update, dict):
                continue

            try:
                npc_executor_id = int(npc_action.get("executor_id", 0))
            except (TypeError, ValueError):
                continue
            if npc_executor_id <= 0:
                continue

            await manager.broadcast_game_action(
                npc_action,
                channel_id,
                npc_executor_id,
                None,
                True,
            )
            await manager.broadcast_game_state(npc_update, channel_id)

        return npc_steps

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
        self._reset_turn_budget(channel_id, user_id)

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
            if self._is_npc_user(candidate_id, channel_id) or not ws_manager.is_client_stale(candidate_id):
                self._channel_turn_user[channel_id] = candidate_id
                self._reset_turn_budget(channel_id, candidate_id)
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
            if self._is_npc_user(candidate_id, channel_id):
                self._channel_turn_user[channel_id] = candidate_id
                self._reset_turn_budget(channel_id, candidate_id)
                return candidate_id
            
            # P6: Skip stale human clients
            if not ws_manager.is_client_stale(candidate_id):
                self._channel_turn_user[channel_id] = candidate_id
                self._reset_turn_budget(channel_id, candidate_id)
                return candidate_id
            
            logger.info(
                "P6: Skipping stale client user_id=%s in channel_id=%s",
                candidate_id,
                channel_id,
            )
        
        # All users are stale - fall back to simple round-robin
        next_user = user_ids[(start_index + 1) % len(user_ids)]
        self._channel_turn_user[channel_id] = next_user
        self._reset_turn_budget(channel_id, next_user)
        return next_user

    def _ensure_turn_user(self, channel_id: int) -> None:
        user_ids = self._get_active_user_ids(channel_id)
        if not user_ids:
            self._channel_turn_user.pop(channel_id, None)
            self._channel_turn_order.pop(channel_id, None)
            self._channel_priority_turns.pop(channel_id, None)
            self._channel_priority_resume_from.pop(channel_id, None)
            self._channel_status_history.pop(channel_id, None)
            self._channel_human_user.pop(channel_id, None)
            self._channel_forced_npc_users.pop(channel_id, None)
            self._channel_turn_budget.pop(channel_id, None)
            self._channel_turn_context_cache.pop(channel_id, None)
            return
        current = self._channel_turn_user.get(channel_id)
        if current not in user_ids:
            self._channel_turn_user[channel_id] = user_ids[0]
            self._reset_turn_budget(channel_id, user_ids[0])

    def _get_active_user_ids_from_sessions(self, channel_id: int) -> List[int]:
        sessions = self.db.query(GameSession).filter(
            GameSession.channel_id == channel_id,
            GameSession.is_active == True,
        ).order_by(GameSession.id.asc()).all()
        user_ids: List[int] = []
        for session in sessions:
            user_ids.append(cast(int, session.user_id))
        return user_ids

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
        while queue:
            x, y = queue.popleft()
            current = (x, y)
            if current not in occupied_positions:
                return current
            for neighbor in self._neighbor_positions(current):
                if neighbor in visited:
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

    def _resolve_move_target(
        self,
        current_position: Tuple[int, int],
        command: str,
    ) -> Optional[Tuple[int, int]]:
        direction_vectors: Dict[str, Tuple[int, int]] = {
            "move_n": (0, -1),
            "move_ne": (1, -1),
            "move_se": (1, 0),
            "move_s": (0, 1),
            "move_sw": (-1, 1),
            "move_nw": (-1, 0),
        }
        direction = direction_vectors.get(command)
        if direction is None:
            return None

        current_axial = self._offset_to_axial(current_position)
        next_axial = (current_axial[0] + direction[0], current_axial[1] + direction[1])
        return self._axial_to_offset(next_axial)

    def _offset_to_axial(self, position: Tuple[int, int]) -> Tuple[int, int]:
        x, y = position
        q = x - ((y - (y & 1)) // 2)
        r = y
        return (q, r)

    def _axial_to_offset(self, axial: Tuple[int, int]) -> Tuple[int, int]:
        q, r = axial
        x = q + ((r - (r & 1)) // 2)
        y = r
        return (x, y)

    def _hex_distance_offset(self, left: Tuple[int, int], right: Tuple[int, int]) -> int:
        left_axial = self._offset_to_axial(left)
        right_axial = self._offset_to_axial(right)
        dq = left_axial[0] - right_axial[0]
        dr = left_axial[1] - right_axial[1]
        ds = -(left_axial[0] + left_axial[1]) + (right_axial[0] + right_axial[1])
        return max(abs(dq), abs(dr), abs(ds))

    def _neighbor_positions(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        base_axial = self._offset_to_axial(position)
        vectors = [(0, -1), (1, -1), (1, 0), (0, 1), (-1, 1), (-1, 0)]
        neighbors: List[Tuple[int, int]] = []
        for vector in vectors:
            axial = (base_axial[0] + vector[0], base_axial[1] + vector[1])
            offset = self._axial_to_offset(axial)
            if BattlefieldService.is_play_zone(offset[0], offset[1]):
                neighbors.append(offset)
        return neighbors

    def _is_npc_user(self, user_id: int, channel_id: Optional[int] = None) -> bool:
        if channel_id is not None:
            human_user_id = self._channel_human_user.get(channel_id)
            if human_user_id == user_id:
                return False
            forced_npcs = self._channel_forced_npc_users.get(channel_id, set())
            if user_id in forced_npcs:
                return True
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        username = cast(str, user.username)
        return self._is_npc_username(username)

    def _is_npc_username(self, username: str) -> bool:
        username_lower = username.lower()
        return username_lower.startswith(NPC_PREFIX)

    def _assign_joiner_role(self, user_id: int, channel_id: int) -> str:
        forced_npcs = self._channel_forced_npc_users.setdefault(channel_id, set())
        current_human = self._channel_human_user.get(channel_id)
        if current_human is not None and not self._is_user_in_channel(current_human, channel_id):
            self._channel_human_user.pop(channel_id, None)
            current_human = None

        if current_human is None:
            self._channel_human_user[channel_id] = user_id
            forced_npcs.discard(user_id)
            return "human"

        if current_human == user_id:
            forced_npcs.discard(user_id)
            return "human"

        forced_npcs.add(user_id)
        return "npc"

    def _ensure_turn_budget(self, channel_id: int) -> Dict[str, int]:
        active_user_id = self.get_active_turn_user_id(channel_id)
        if active_user_id is None:
            self._channel_turn_budget.pop(channel_id, None)
            return {"user_id": 0, "moves_used": 0, "actions_used": 0}

        existing = self._channel_turn_budget.get(channel_id)
        if existing is None or int(existing.get("user_id", 0)) != active_user_id:
            refreshed = {
                "user_id": active_user_id,
                "moves_used": 0,
                "actions_used": 0,
            }
            self._channel_turn_budget[channel_id] = refreshed
            return refreshed
        return existing

    def _reset_turn_budget(self, channel_id: int, user_id: int) -> None:
        self._channel_turn_budget[channel_id] = {
            "user_id": user_id,
            "moves_used": 0,
            "actions_used": 0,
        }

    def _consume_turn_budget(self, channel_id: int, command: str) -> None:
        turn_budget = self._ensure_turn_budget(channel_id)
        if command.startswith("move_"):
            turn_budget["moves_used"] = int(turn_budget.get("moves_used", 0)) + 1
        elif command in ("attack", "heal"):
            turn_budget["actions_used"] = int(turn_budget.get("actions_used", 0)) + 1

    def _build_turn_context(
        self,
        channel_id: int,
        players: Optional[List[Dict[str, Any]]] = None,
        obstacles: Optional[List[Dict[str, Any]]] = None,
        battlefield: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        active_turn_user_id = self.get_active_turn_user_id(channel_id)
        if active_turn_user_id is None:
            self._channel_turn_context_cache.pop(channel_id, None)
            return {
                "actor_user_id": None,
                "attackable_target_ids": [],
                "surroundings": [],
                "surroundings_diff": {
                    "revision": 0,
                    "added": [],
                    "removed": [],
                    "changed": [],
                },
            }

        player_rows = players if players is not None else self.get_all_game_states_in_channel(channel_id)
        actor_state: Optional[Dict[str, Any]] = None
        for entry in player_rows:
            if int(entry.get("user_id", 0)) == active_turn_user_id:
                actor_state = entry
                break

        if actor_state is None:
            self._channel_turn_context_cache.pop(channel_id, None)
            return {
                "actor_user_id": active_turn_user_id,
                "attackable_target_ids": [],
                "surroundings": [],
                "surroundings_diff": {
                    "revision": 0,
                    "added": [],
                    "removed": [],
                    "changed": [],
                },
            }

        actor_position_data = cast(Dict[str, Any], actor_state.get("position", {}))
        actor_position = (
            int(actor_position_data.get("x", 0)),
            int(actor_position_data.get("y", 0)),
        )

        attackable_target_ids: List[int] = []
        surroundings: List[Dict[str, Any]] = []

        for entry in player_rows:
            user_id = int(entry.get("user_id", 0))
            if user_id <= 0 or user_id == active_turn_user_id:
                continue
            position_data = entry.get("position")
            if not isinstance(position_data, dict):
                continue
            target_position = (
                int(position_data.get("x", 0)),
                int(position_data.get("y", 0)),
            )
            if not self._is_adjacent_position(actor_position, target_position):
                continue
            target_health = int(entry.get("health", 0))
            if target_health > 0:
                attackable_target_ids.append(user_id)
            surroundings.append(
                {
                    "entity_id": f"player:{user_id}",
                    "entity_type": "player",
                    "distance": 1,
                    "position": {
                        "x": target_position[0],
                        "y": target_position[1],
                    },
                    "user_id": user_id,
                    "username": str(entry.get("username", "")),
                    "display_name": str(entry.get("display_name", "")),
                    "is_npc": bool(entry.get("is_npc", False)),
                    "health": target_health,
                    "max_health": int(entry.get("max_health", 0)),
                }
            )

        obstacle_rows = obstacles if obstacles is not None else self.get_obstacles(channel_id)
        for obstacle in obstacle_rows:
            position_data = obstacle.get("position")
            if not isinstance(position_data, dict):
                continue
            obstacle_position = (
                int(position_data.get("x", 0)),
                int(position_data.get("y", 0)),
            )
            if not self._is_adjacent_position(actor_position, obstacle_position):
                continue
            obstacle_id = str(obstacle.get("id", ""))
            if obstacle_id == "":
                obstacle_id = f"{str(obstacle.get('type', 'obstacle'))}:{obstacle_position[0]}:{obstacle_position[1]}"
            surroundings.append(
                {
                    "entity_id": f"obstacle:{obstacle_id}",
                    "entity_type": "obstacle",
                    "distance": 1,
                    "position": {
                        "x": obstacle_position[0],
                        "y": obstacle_position[1],
                    },
                    "obstacle_type": str(obstacle.get("type", "obstacle")),
                }
            )

        battlefield_payload = battlefield if battlefield is not None else self.get_battlefield(channel_id)
        props_raw = battlefield_payload.get("props", [])
        if isinstance(props_raw, list):
            for raw_prop in props_raw:
                if not isinstance(raw_prop, dict):
                    continue
                prop = cast(Dict[str, Any], raw_prop)
                position_data = prop.get("position")
                if not isinstance(position_data, dict):
                    continue
                prop_position = (
                    int(position_data.get("x", 0)),
                    int(position_data.get("y", 0)),
                )
                if not self._is_adjacent_position(actor_position, prop_position):
                    continue
                prop_id = str(prop.get("id", ""))
                if prop_id == "":
                    prop_id = f"{str(prop.get('type', 'prop'))}:{prop_position[0]}:{prop_position[1]}"
                surroundings.append(
                    {
                        "entity_id": f"prop:{prop_id}",
                        "entity_type": "prop",
                        "distance": 1,
                        "position": {
                            "x": prop_position[0],
                            "y": prop_position[1],
                        },
                        "prop_type": str(prop.get("type", "prop")),
                        "is_blocking": bool(prop.get("is_blocking", True)),
                        "zone": str(prop.get("zone", "play")),
                    }
                )

        attackable_target_ids = sorted(set(attackable_target_ids))
        surroundings.sort(key=lambda item: str(item.get("entity_id", "")))
        return {
            "actor_user_id": active_turn_user_id,
            "attackable_target_ids": attackable_target_ids,
            "surroundings": surroundings,
            "surroundings_diff": self._build_turn_context_diff(
                channel_id,
                active_turn_user_id,
                surroundings,
            ),
        }

    def _build_turn_context_diff(
        self,
        channel_id: int,
        actor_user_id: int,
        surroundings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        current_by_id: Dict[str, Dict[str, Any]] = {}
        for entry in surroundings:
            entity_id = str(entry.get("entity_id", ""))
            if entity_id == "":
                continue
            current_by_id[entity_id] = entry

        cache = self._channel_turn_context_cache.get(channel_id)
        previous_actor_id = int(cache.get("actor_user_id", -1)) if cache is not None else -1
        previous_revision = int(cache.get("revision", 0)) if cache is not None else 0
        revision = previous_revision + 1

        added: List[Dict[str, Any]] = []
        removed: List[Dict[str, Any]] = []
        changed: List[Dict[str, Any]] = []

        previous_by_id_raw = cache.get("surroundings_by_id", {}) if cache is not None else {}
        previous_by_id = previous_by_id_raw if isinstance(previous_by_id_raw, dict) else {}

        if previous_actor_id == actor_user_id:
            for entity_id, current_entry in current_by_id.items():
                previous_entry = previous_by_id.get(entity_id)
                if not isinstance(previous_entry, dict):
                    added.append(current_entry)
                    continue
                if previous_entry != current_entry:
                    changed.append(current_entry)
            for entity_id, previous_entry in previous_by_id.items():
                if entity_id in current_by_id:
                    continue
                if isinstance(previous_entry, dict):
                    removed.append(cast(Dict[str, Any], previous_entry))
        else:
            added = list(current_by_id.values())

        added.sort(key=lambda item: str(item.get("entity_id", "")))
        removed.sort(key=lambda item: str(item.get("entity_id", "")))
        changed.sort(key=lambda item: str(item.get("entity_id", "")))

        self._channel_turn_context_cache[channel_id] = {
            "actor_user_id": actor_user_id,
            "revision": revision,
            "surroundings_by_id": current_by_id,
        }
        return {
            "revision": revision,
            "added": added,
            "removed": removed,
            "changed": changed,
        }

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

    def _choose_adjacent_human_target(
        self,
        user_id: int,
        channel_id: int,
    ) -> Optional[str]:
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
            return random.choice(adjacent_targets)

        return None

    def _build_npc_noop_result(
        self,
        user_id: int,
        channel_id: int,
        message: str,
    ) -> Dict[str, Any]:
        user = self.db.query(User).filter(User.id == user_id).first()
        username = cast(str, user.username) if user else "npc"
        state = self.get_or_create_game_state(user_id, channel_id)
        return {
            "success": True,
            "command": "npc_noop",
            "executor_id": user_id,
            "target_id": user_id,
            "message": message,
            "game_state": {
                "user_id": user_id,
                "position": {
                    "x": cast(int, state.position_x),
                    "y": cast(int, state.position_y),
                },
                "position_x": cast(int, state.position_x),
                "position_y": cast(int, state.position_y),
                "health": cast(int, state.health),
                "max_health": cast(int, state.max_health),
            },
            "executor_username": username,
            "target_username": username,
            "position": None,
            "target_health": cast(int, state.health),
            "target_max_health": cast(int, state.max_health),
            "actor_health": cast(int, state.health),
            "actor_max_health": cast(int, state.max_health),
            "npc_actions": [],
            "error": None,
            "active_turn_user_id": self.get_active_turn_user_id(channel_id),
        }

    def _run_npc_turn_program(
        self,
        user_id: int,
        channel_id: int,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        directions = ["move_n", "move_ne", "move_se", "move_s", "move_sw", "move_nw"]

        for _ in range(2):
            command = random.choice(directions)
            move_result = self.execute_command(
                command,
                user_id,
                channel_id=channel_id,
                force=False,
                advance_turn=False,
                enforce_turn_budget=False,
            )
            results.append(move_result)

        target_username = self._choose_adjacent_human_target(user_id, channel_id)
        if target_username is not None:
            attack_result = self.execute_command(
                "attack",
                user_id,
                target_username=target_username,
                channel_id=channel_id,
                force=False,
                advance_turn=False,
                enforce_turn_budget=False,
            )
            results.append(attack_result)
            return results

        game_state = self.get_or_create_game_state(user_id, channel_id)
        should_heal = (
            cast(int, game_state.health) < cast(int, game_state.max_health)
            and random.choice([True, False])
        )
        if should_heal:
            heal_result = self.execute_command(
                "heal",
                user_id,
                channel_id=channel_id,
                force=False,
                advance_turn=False,
                enforce_turn_budget=False,
            )
            results.append(heal_result)
        else:
            results.append(
                self._build_npc_noop_result(
                    user_id,
                    channel_id,
                    "NPC had no valid attack target and skipped action",
                )
            )

        return results

    def _is_adjacent_position(
        self,
        left: Tuple[int, int],
        right: Tuple[int, int],
    ) -> bool:
        return self._hex_distance_offset(left, right) == 1

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
        """Backward-compatible wrapper returning only action-result payloads."""
        chained = self.process_npc_turn_chain(channel_id)
        return [cast(Dict[str, Any], item.get("action_result", {})) for item in chained]
