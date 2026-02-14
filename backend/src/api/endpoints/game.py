"""
Game API Endpoints
Handles game-related HTTP endpoints for the #game channel.
"""
from typing import List, Optional, Dict, Any, cast
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.api.endpoints.auth import get_current_user
from src.models.game_state import GameState
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
    is_npc: Optional[bool] = None


class GameCommandRequest(BaseModel):
    command: str
    target_username: Optional[str] = None
    channel_id: Optional[int] = None
    force: bool = False


class GameCommandResponse(BaseModel):
    success: bool
    command: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    game_state: Optional[GameStateResponse] = None
    snapshot: Optional[Dict[str, Any]] = None
    active_turn_user_id: Optional[int] = None


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
    game_state = db.query(GameState).filter(GameState.user_id == cast(int, current_user.id)).first()
    if game_state is None:
        raise HTTPException(status_code=404, detail="Game state not initialized. Connect WebSocket and send game_join first.")
    is_npc = bool(cast(str, current_user.username).lower().startswith("npc_"))
    
    return GameStateResponse(
        user_id=cast(int, game_state.user_id),
        username=cast(str, current_user.username),
        display_name=cast(Optional[str], current_user.display_name or current_user.username),
        position_x=cast(int, game_state.position_x),
        position_y=cast(int, game_state.position_y),
        health=cast(int, game_state.health),
        max_health=cast(int, game_state.max_health),
        is_npc=is_npc,
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
    if not game_service.is_game_channel(cast(str, channel.name)):
        raise HTTPException(status_code=400, detail="Not a game channel")
    
    states = game_service.get_all_game_states_in_channel(channel_id)
    response_items: List[GameStateResponse] = []
    for state in states:
        position = cast(Dict[str, int], state.get("position", {}))
        response_items.append(
            GameStateResponse(
                user_id=cast(int, state.get("user_id", 0)),
                username=cast(Optional[str], state.get("username")),
                display_name=cast(Optional[str], state.get("display_name")),
                position_x=int(position.get("x", 0)),
                position_y=int(position.get("y", 0)),
                health=cast(int, state.get("health", 0)),
                max_health=cast(int, state.get("max_health", 0)),
                is_npc=cast(Optional[bool], state.get("is_npc")),
            )
        )
    return response_items


@router.get("/channel/{channel_id}/snapshot")
async def get_channel_game_snapshot(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    game_service = GameService(db)
    if not game_service.is_game_channel(cast(str, channel.name)):
        raise HTTPException(status_code=400, detail="Not a game channel")

    raise HTTPException(
        status_code=410,
        detail="HTTP game snapshots are disabled. Use WebSocket push events.",
    )


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
    result = game_service.execute_command(
        command,
        cast(int, current_user.id),
        target_username,
        request.channel_id,
        force=request.force,
    )
    
    if result["success"]:
        game_state = result.get("game_state")
        
        # Broadcast game action to channel if channel_id provided
        snapshot = None
        if request.channel_id:
            snapshot = game_service.get_game_state_update(request.channel_id)
            await manager.broadcast_game_action(result, request.channel_id, cast(int, current_user.id), None)
            await manager.broadcast_game_state(snapshot, request.channel_id)

            if game_service.is_npc_turn(request.channel_id):
                npc_steps = game_service.process_npc_turn_chain(request.channel_id)
                for step in npc_steps:
                    if not isinstance(step, dict):
                        continue
                    npc_action = step.get("action_result", {})
                    npc_update = step.get("state_update", {})
                    if not isinstance(npc_action, dict):
                        continue
                    if not isinstance(npc_update, dict):
                        continue
                    npc_executor_id = int(npc_action.get("executor_id", 0))
                    if npc_executor_id <= 0:
                        continue
                    await manager.broadcast_game_action(
                        npc_action,
                        request.channel_id,
                        npc_executor_id,
                        None,
                        True,
                    )
                    await manager.broadcast_game_state(npc_update, request.channel_id)
        
        return GameCommandResponse(
            success=True,
            command=result["command"],
            message=result["message"],
            game_state=GameStateResponse(**game_state) if game_state else None,
            snapshot=snapshot,
            active_turn_user_id=result.get("active_turn_user_id"),
        )
    else:
        return GameCommandResponse(
            success=False,
            error=result.get("error", "Unknown error"),
            active_turn_user_id=result.get("active_turn_user_id"),
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
    if not game_service.is_game_channel(cast(str, channel.name)):
        raise HTTPException(status_code=400, detail="Not a game channel")
    
    # HTTP join no longer initializes game state/session.
    # Initialization happens via WebSocket game_join handshake.
    manager.add_client_to_channel(cast(int, current_user.id), channel_id)

    return {
        "message": f"Joined game channel #{channel.name}; awaiting WebSocket game_join handshake",
        "channel_id": channel_id,
        "game_ready": False,
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
    game_service.deactivate_session(cast(int, current_user.id), channel_id)
    manager.remove_client_from_channel(cast(int, current_user.id), channel_id)

    update = game_service.get_game_state_update(channel_id)
    await manager.broadcast_game_state(update, channel_id)
    
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
    if not game_service.is_game_channel(cast(str, channel.name)):
        raise HTTPException(status_code=400, detail="Not a game channel")
    
    matrix = game_service.get_ascii_matrix(channel_id, grid_size)
    return {"matrix": matrix}
