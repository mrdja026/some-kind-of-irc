"""
Game API Endpoints
Handles game-related HTTP endpoints for the #game channel.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.api.endpoints.auth import get_current_user
from src.models.user import User
from src.models.channel import Channel
from src.services.game_service import GameService
from src.services.websocket_manager import manager


router = APIRouter(prefix="/game", tags=["game"])


# Pydantic models for request/response
class GameStateResponse(BaseModel):
    user_id: int
    username: Optional[str] = None
    display_name: Optional[str] = None
    position_x: int
    position_y: int
    health: int
    max_health: int


class GameCommandRequest(BaseModel):
    command: str
    target_username: Optional[str] = None
    channel_id: Optional[int] = None


class GameCommandResponse(BaseModel):
    success: bool
    command: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    game_state: Optional[GameStateResponse] = None


class AvailableCommandsResponse(BaseModel):
    commands: List[str]


@router.get("/commands", response_model=AvailableCommandsResponse)
async def get_available_commands(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the list of available game commands."""
    game_service = GameService(db)
    return AvailableCommandsResponse(commands=game_service.get_available_commands())


@router.get("/state", response_model=GameStateResponse)
async def get_my_game_state(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the current user's game state."""
    game_service = GameService(db)
    game_state = game_service.get_or_create_game_state(current_user.id)
    
    return GameStateResponse(
        user_id=game_state.user_id,
        username=current_user.username,
        display_name=current_user.display_name or current_user.username,
        position_x=game_state.position_x,
        position_y=game_state.position_y,
        health=game_state.health,
        max_health=game_state.max_health
    )


@router.get("/channel/{channel_id}/states", response_model=List[GameStateResponse])
async def get_channel_game_states(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all game states for users in a specific game channel."""
    # Verify channel exists and is a game channel
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    game_service = GameService(db)
    if not game_service.is_game_channel(channel.name):
        raise HTTPException(status_code=400, detail="Not a game channel")
    
    states = game_service.get_all_game_states_in_channel(channel_id)
    return [GameStateResponse(**state) for state in states]


@router.post("/command", response_model=GameCommandResponse)
async def execute_game_command(
    request: GameCommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a game command and broadcast the result via WebSocket."""
    game_service = GameService(db)
    
    # Parse and validate the command
    parsed = game_service.parse_command(request.command)
    if not parsed:
        return GameCommandResponse(
            success=False,
            error=f"Invalid command: {request.command}. Available commands: {', '.join(game_service.get_available_commands())}"
        )
    
    command, target_from_message = parsed
    
    # Use target from request if provided, otherwise from parsed message
    target_username = request.target_username or target_from_message
    
    # Execute the command
    result = game_service.execute_command(command, current_user.id, target_username)
    
    if result["success"]:
        game_state = result.get("game_state")
        
        # Broadcast game action to channel if channel_id provided
        if request.channel_id:
            await manager.broadcast_game_action(result, request.channel_id, current_user.id)
        
        return GameCommandResponse(
            success=True,
            command=result["command"],
            message=result["message"],
            game_state=GameStateResponse(**game_state) if game_state else None
        )
    else:
        return GameCommandResponse(
            success=False,
            error=result.get("error", "Unknown error")
        )


@router.post("/join/{channel_id}")
async def join_game_channel(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Join a game channel and initialize game session."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    game_service = GameService(db)
    if not game_service.is_game_channel(channel.name):
        raise HTTPException(status_code=400, detail="Not a game channel")
    
    # Create or get game session
    session = game_service.get_or_create_game_session(current_user.id, channel_id)
    game_state = game_service.get_or_create_game_state(current_user.id)
    
    return {
        "message": f"Joined game channel #{channel.name}",
        "game_state": {
            "user_id": game_state.user_id,
            "position_x": game_state.position_x,
            "position_y": game_state.position_y,
            "health": game_state.health,
            "max_health": game_state.max_health
        }
    }


@router.post("/leave/{channel_id}")
async def leave_game_channel(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Leave a game channel and deactivate game session."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    game_service = GameService(db)
    game_service.deactivate_session(current_user.id, channel_id)
    
    return {"message": f"Left game channel #{channel.name}"}


@router.get("/channel/{channel_id}/matrix")
async def get_game_matrix(
    channel_id: int,
    grid_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get ASCII matrix representation of the game state."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    game_service = GameService(db)
    if not game_service.is_game_channel(channel.name):
        raise HTTPException(status_code=400, detail="Not a game channel")
    
    matrix = game_service.get_ascii_matrix(channel_id, grid_size)
    return {"matrix": matrix}
