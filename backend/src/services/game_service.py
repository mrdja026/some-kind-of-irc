"""
Game Service Module
Handles game state management, command parsing, and game logic for the #game channel.
"""
import re
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session

from src.models.game_state import GameState
from src.models.game_session import GameSession
from src.models.user import User
from src.models.channel import Channel


# Grid constants
GRID_SIZE = 64
DEFAULT_HEALTH = 100
MAX_HEALTH = 100
ATTACK_DAMAGE = 10
HEAL_AMOUNT = 15


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
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_game_state(self, user_id: int) -> GameState:
        """Get existing game state for user or create a new one."""
        game_state = self.db.query(GameState).filter(GameState.user_id == user_id).first()
        
        if not game_state:
            # Create new game state with random starting position
            import random
            game_state = GameState(
                user_id=user_id,
                position_x=random.randint(0, GRID_SIZE - 1),
                position_y=random.randint(0, GRID_SIZE - 1),
                health=DEFAULT_HEALTH,
                max_health=MAX_HEALTH
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
            game_state = self.get_or_create_game_state(user_id)
            session = GameSession(
                user_id=user_id,
                game_state_id=game_state.id,
                channel_id=channel_id,
                is_active=True
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        
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
        target_username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a game command.
        Returns a dict with the result and updated state.
        """
        # Get the target user (either from mention or self)
        if target_username:
            target_user = self.db.query(User).filter(User.username == target_username).first()
            if not target_user:
                return {
                    "success": False,
                    "error": f"User @{target_username} not found",
                    "game_state": None
                }
            target_id = target_user.id
        else:
            target_id = executor_id
        
        # Get or create game state for the target
        game_state = self.get_or_create_game_state(target_id)
        
        result = {
            "success": True,
            "command": command,
            "executor_id": executor_id,
            "target_id": target_id,
            "message": "",
            "game_state": None
        }
        
        if command == "move up":
            if game_state.position_y > 0:
                game_state.position_y -= 1
                result["message"] = f"Moved up to ({game_state.position_x}, {game_state.position_y})"
            else:
                result["message"] = "Cannot move up - at grid boundary"
                
        elif command == "move down":
            if game_state.position_y < GRID_SIZE - 1:
                game_state.position_y += 1
                result["message"] = f"Moved down to ({game_state.position_x}, {game_state.position_y})"
            else:
                result["message"] = "Cannot move down - at grid boundary"
                
        elif command == "move left":
            if game_state.position_x > 0:
                game_state.position_x -= 1
                result["message"] = f"Moved left to ({game_state.position_x}, {game_state.position_y})"
            else:
                result["message"] = "Cannot move left - at grid boundary"
                
        elif command == "move right":
            if game_state.position_x < GRID_SIZE - 1:
                game_state.position_x += 1
                result["message"] = f"Moved right to ({game_state.position_x}, {game_state.position_y})"
            else:
                result["message"] = "Cannot move right - at grid boundary"
                
        elif command == "attack":
            if target_id == executor_id:
                result["success"] = False
                result["error"] = "Cannot attack yourself! Use @username to target another player."
            else:
                game_state.health = max(0, game_state.health - ATTACK_DAMAGE)
                result["message"] = f"Attacked! Target health: {game_state.health}/{game_state.max_health}"
                if game_state.health == 0:
                    result["message"] += " - Target defeated!"
                    
        elif command == "heal":
            old_health = game_state.health
            game_state.health = min(game_state.max_health, game_state.health + HEAL_AMOUNT)
            healed = game_state.health - old_health
            result["message"] = f"Healed for {healed} HP! Health: {game_state.health}/{game_state.max_health}"
        
        # Commit changes
        self.db.commit()
        self.db.refresh(game_state)
        
        # Add game state to result
        result["game_state"] = {
            "user_id": game_state.user_id,
            "position_x": game_state.position_x,
            "position_y": game_state.position_y,
            "health": game_state.health,
            "max_health": game_state.max_health
        }
        
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
            if game_state and user:
                states.append({
                    "user_id": user.id,
                    "username": user.username,
                    "display_name": user.display_name or user.username,
                    "position_x": game_state.position_x,
                    "position_y": game_state.position_y,
                    "health": game_state.health,
                    "max_health": game_state.max_health
                })
        
        return states
    
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
            session.is_active = False
            self.db.commit()
