# pyright: ignore

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import List, Optional, cast, Any

from src.core.database import get_db
from src.core.config import settings
from src.models.user import User
from src.models.channel import Channel
from src.models.message import Message
from src.models.membership import Membership
from src.api.endpoints.auth import get_current_user
from src.services.websocket_manager import manager
from src.services.irc_logger import log_join, log_part, log_privmsg
from src.services.game_service import GameService

router = APIRouter(prefix="/channels", tags=["channels"])


def _as_int(value: Any) -> int:
    return int(value)  # type: ignore[arg-type]


def _as_opt_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)  # type: ignore[arg-type]


def _as_str(value: Any) -> str:
    return str(value)


def _as_opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)

# Pydantic models
class ChannelCreate(BaseModel):
    name: str
    type: str = "public"
    is_data_processor: bool = False

class ChannelResponse(BaseModel):
    id: int
    name: str
    type: str
    is_data_processor: bool = False

    model_config = {
        "from_attributes": True
    }

class MessageCreate(BaseModel):
    content: str
    image_url: Optional[str] = None

class MessageResponse(BaseModel):
    id: int
    content: str
    sender_id: Optional[int]
    channel_id: int
    timestamp: str
    image_url: Optional[str] = None
    target_user_id: Optional[int] = None

    model_config = {
        "from_attributes": True
    }

# API endpoints
@router.post("/", response_model=ChannelResponse)
async def create_channel(channel: ChannelCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user_id = _as_int(current_user.id)
    if channel.type == "public" and not channel.name.startswith("#"):
        raise HTTPException(status_code=400, detail="Public channel name must start with #")
    
    # Check if data processor feature is enabled when creating data processor channel
    if channel.is_data_processor and not settings.data_processor_enabled:
        raise HTTPException(
            status_code=400,
            detail="Data processor feature is not enabled"
        )
    
    # For private channels/DMs, generate a unique name based on user IDs
    if channel.type == "private":
        channel.name = f"dm-{current_user_id}-{channel.name}"
    db_channel = db.query(Channel).filter(Channel.name == channel.name).first()
    if db_channel:
        raise HTTPException(status_code=400, detail="Channel already exists")
    new_channel = Channel(name=channel.name, type=channel.type, is_data_processor=channel.is_data_processor)
    db.add(new_channel)
    db.commit()
    db.refresh(new_channel)
    # Add current user to channel
    new_channel_id = _as_int(new_channel.id)
    new_channel_name = _as_str(new_channel.name)
    membership = Membership(user_id=current_user_id, channel_id=new_channel_id)
    db.add(membership)
    # Update WebSocket manager to include creator in this channel
    manager.add_client_to_channel(current_user_id, new_channel_id)
    # If it's a DM, add the other user to the channel
    if channel.type == "private":
        try:
                other_user_id = int(channel.name.split("-")[2])
                other_user = db.query(User).filter(User.id == other_user_id).first()
                if other_user:
                    other_membership = Membership(user_id=_as_int(other_user.id), channel_id=new_channel_id)
                    db.add(other_membership)
                    # Update WebSocket manager for the other user too
                    manager.add_client_to_channel(_as_int(other_user.id), new_channel_id)
        except:
            pass
    db.commit()
    
    # Create welcome message for the channel creator
    welcome_message = Message(
        content=f"Welcome to {new_channel_name}!",
        sender_id=None,  # System/admin message
        channel_id=new_channel_id,
        target_user_id=current_user_id,  # Only visible to the creator
    )
    db.add(welcome_message)
    db.commit()
    db.refresh(welcome_message)
    
    # Send welcome message via WebSocket directly to the creator
    await manager.send_personal_message({
        "type": "message",
        "id": _as_int(welcome_message.id),
        "content": _as_str(welcome_message.content),
        "image_url": _as_opt_str(welcome_message.image_url),
        "sender_id": None,
        "channel_id": _as_int(welcome_message.channel_id),
        "timestamp": welcome_message.timestamp.isoformat(),
        "target_user_id": _as_opt_int(welcome_message.target_user_id),
    }, current_user_id)
    
    log_join(current_user_id, new_channel_id, new_channel_name)
    return new_channel

@router.get("/", response_model=List[ChannelResponse])
async def get_channels(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get all public channels (visible to all logged-in users)
    public_channels = db.query(Channel).filter(Channel.type == "public").all()
    
    # Get private channels the user is a member of
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    private_channel_ids = [m.channel_id for m in memberships]
    private_channels = db.query(Channel).filter(
        Channel.id.in_(private_channel_ids),
        Channel.type == "private"
    ).all() if private_channel_ids else []
    
    # Combine public and private channels
    all_channels = public_channels + private_channels
    
    # Remove duplicates (in case user is a member of a public channel)
    seen_ids = set()
    unique_channels = []
    for channel in all_channels:
        if channel.id not in seen_ids:
            seen_ids.add(channel.id)
            unique_channels.append(channel)
    
    return unique_channels

@router.get("/search")
async def search_channels(name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Search for channels by name (case-insensitive)
    channels = db.query(Channel).filter(Channel.name.ilike(f"%{name}%")).all()
    return [
        ChannelResponse(
            id=cast(int, ch.id),
            name=cast(str, ch.name),
            type=cast(str, ch.type),
            is_data_processor=cast(bool, ch.is_data_processor),
        )
        for ch in channels
    ]

@router.get("/dms", response_model=List[ChannelResponse])
async def get_direct_messages(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get all direct message channels the user is a member of
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    channel_ids = [m.channel_id for m in memberships]
    return db.query(Channel).filter(Channel.id.in_(channel_ids), Channel.type == "private").all()

@router.post("/dm/{user_id}", response_model=ChannelResponse)
async def create_direct_message_channel(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user_id == current_user.id:
        self_dm_name = f"dm-{current_user.id}-{current_user.id}"
        existing_self_dm = db.query(Channel).filter(Channel.name == self_dm_name).first()
        if existing_self_dm:
            existing_membership = db.query(Membership).filter(
                Membership.user_id == current_user.id,
                Membership.channel_id == existing_self_dm.id,
            ).first()
            if not existing_membership:
                db.add(Membership(user_id=current_user.id, channel_id=existing_self_dm.id))
                db.commit()
            manager.add_client_to_channel(current_user.id, existing_self_dm.id)
            return existing_self_dm

        new_self_dm = Channel(name=self_dm_name, type="private")
        db.add(new_self_dm)
        db.commit()
        db.refresh(new_self_dm)
        db.add(Membership(user_id=current_user.id, channel_id=new_self_dm.id))
        db.commit()
        manager.add_client_to_channel(current_user.id, new_self_dm.id)
        return new_self_dm
    # Check if DM channel already exists
    dm_name1 = f"dm-{current_user.id}-{user_id}"
    dm_name2 = f"dm-{user_id}-{current_user.id}"
    existing_channel = db.query(Channel).filter(
        (Channel.name == dm_name1) | (Channel.name == dm_name2)
    ).first()
    if existing_channel:
        # Check if user is already a member
        existing_membership = db.query(Membership).filter(
            Membership.user_id == current_user.id,
            Membership.channel_id == existing_channel.id
        ).first()
        if existing_membership:
            # Update WebSocket manager for both users
            manager.add_client_to_channel(current_user.id, existing_channel.id)
            manager.add_client_to_channel(user_id, existing_channel.id)
            return existing_channel
        else:
            # Add current user to existing DM channel
            membership = Membership(user_id=current_user.id, channel_id=existing_channel.id)
            db.add(membership)
            db.commit()
            # Update WebSocket manager for both users
            manager.add_client_to_channel(current_user.id, existing_channel.id)
            manager.add_client_to_channel(user_id, existing_channel.id)
            return existing_channel
    # Create new DM channel
    new_channel = Channel(name=dm_name1, type="private")
    db.add(new_channel)
    db.commit()
    db.refresh(new_channel)
    # Add both users to the DM channel
    membership1 = Membership(user_id=current_user.id, channel_id=new_channel.id)
    membership2 = Membership(user_id=user_id, channel_id=new_channel.id)
    db.add(membership1)
    db.add(membership2)
    db.commit()
    # Update WebSocket manager for both users
    manager.add_client_to_channel(current_user.id, new_channel.id)
    manager.add_client_to_channel(user_id, new_channel.id)
    return new_channel

@router.get("/{channel_id}/messages", response_model=List[MessageResponse])
async def get_messages(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if channel exists
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel_type = _as_str(channel.type)
    # For private channels, check if user is a member
    if channel_type == "private":
        membership = db.query(Membership).filter(
            Membership.user_id == _as_int(current_user.id),
            Membership.channel_id == channel_id
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="You are not a member of this channel")
    
    # Get all messages for the channel, but filter system messages (sender_id is None)
    # to only show them to the target user
    # Public channels: all logged-in users can view messages
    # Private channels: only members can view (already checked above)
    messages = db.query(Message).filter(
        Message.channel_id == channel_id,
        # Show regular messages (sender_id is not None) OR system messages targeted to current user
        or_(
            Message.sender_id.isnot(None),
            Message.target_user_id == _as_int(current_user.id)
        )
    ).order_by(Message.timestamp).all()
    # Convert datetime to string for response
    return [
        MessageResponse(
            id=_as_int(msg.id),
            content=_as_str(msg.content),
            sender_id=_as_opt_int(msg.sender_id),
            channel_id=_as_int(msg.channel_id),
            timestamp=msg.timestamp.isoformat(),
            image_url=_as_opt_str(msg.image_url),
            target_user_id=_as_opt_int(msg.target_user_id),
        ) for msg in messages
    ]

@router.post("/{channel_id}/messages", response_model=MessageResponse)
async def send_message(channel_id: int, message: MessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if user is a member of the channel
    current_user_id = _as_int(current_user.id)
    membership = db.query(Membership).filter(
        Membership.user_id == current_user_id,
        Membership.channel_id == channel_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this channel")
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    new_message = Message(
        content=message.content,
        image_url=message.image_url,
        sender_id=current_user_id,
        channel_id=channel_id,
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    # Broadcast message via WebSocket
    await manager.broadcast({
        "type": "message",
        "id": _as_int(new_message.id),
        "content": _as_str(new_message.content),
        "image_url": _as_opt_str(new_message.image_url),
        "sender_id": _as_opt_int(new_message.sender_id),
        "username": _as_str(current_user.username),
        "display_name": _as_opt_str(current_user.display_name),
        "channel_id": _as_int(new_message.channel_id),
        "timestamp": new_message.timestamp.isoformat(),
    }, channel_id)
    log_privmsg(current_user_id, channel_id, message.content, _as_opt_str(channel.name))
    return MessageResponse(
        id=_as_int(new_message.id),
        content=_as_str(new_message.content),
        sender_id=_as_opt_int(new_message.sender_id),
        channel_id=_as_int(new_message.channel_id),
        timestamp=new_message.timestamp.isoformat(),
        image_url=_as_opt_str(new_message.image_url),
        target_user_id=_as_opt_int(new_message.target_user_id),
    )

@router.post("/{channel_id}/join")
async def join_channel(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user_id = _as_int(current_user.id)
    membership = db.query(Membership).filter(
        Membership.user_id == current_user_id,
        Membership.channel_id == channel_id,
    ).first()
    if membership:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        name = _as_str(channel.name) if channel else str(channel_id)
        return {"message": f"Already a member of channel {name}"}
    new_membership = Membership(user_id=current_user_id, channel_id=channel_id)
    db.add(new_membership)
    db.commit()
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel_name = _as_str(channel.name)
    game_service = GameService(db)

    # Update WebSocket manager to include user in this channel
    manager.add_client_to_channel(current_user_id, channel_id)

    if game_service.is_game_channel(channel_name):
        # Game state/session initialization is WS-first via game_join handshake.
        pass

    # Create welcome message for the joining user (system message with sender_id=None)
    welcome_message = Message(
        content=f"Welcome to {channel_name}!",
        sender_id=None,  # System/admin message
        channel_id=channel_id,
        target_user_id=current_user_id,  # Only visible to this user
    )
    db.add(welcome_message)
    db.commit()
    db.refresh(welcome_message)

    # Send welcome message via WebSocket directly to the joining user
    await manager.send_personal_message({
        "type": "message",
        "id": welcome_message.id,
        "content": welcome_message.content,
        "image_url": welcome_message.image_url,
        "sender_id": None,
        "channel_id": welcome_message.channel_id,
        "timestamp": welcome_message.timestamp.isoformat(),
        "target_user_id": welcome_message.target_user_id,
    }, current_user_id)

    await manager.broadcast({
        "type": "join",
        "user_id": current_user_id,
        "username": _as_str(current_user.username),
        "display_name": _as_opt_str(current_user.display_name),
        "channel_id": channel_id,
        "channel_name": channel_name,
    }, channel_id)
    log_join(current_user_id, channel_id, channel_name)
    return {"message": f"Joined channel {channel_name}"}

@router.post("/{channel_id}/leave")
async def leave_channel(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user_id = _as_int(current_user.id)
    membership = db.query(Membership).filter(
        Membership.user_id == current_user_id,
        Membership.channel_id == channel_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Not a member of this channel")
    db.delete(membership)
    db.commit()
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel_name = _as_str(channel.name)
    # Update WebSocket manager to remove user from this channel
    manager.remove_client_from_channel(current_user_id, channel_id)
    await manager.broadcast({
        "type": "leave",
        "user_id": current_user_id,
        "username": _as_str(current_user.username),
        "display_name": _as_opt_str(current_user.display_name),
        "channel_id": channel_id,
        "channel_name": channel_name,
    }, channel_id)
    log_part(current_user_id, channel_id, channel_name)
    return {"message": f"Left channel {channel_name}"}

class AddMemberRequest(BaseModel):
    username: str

class ChannelMemberResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

@router.get("/{channel_id}/members", response_model=List[ChannelMemberResponse])
async def get_channel_members(
    channel_id: int,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if current user is a member of the channel
    current_membership = db.query(Membership).filter(
        Membership.user_id == _as_int(current_user.id),
        Membership.channel_id == channel_id
    ).first()
    if not current_membership:
        raise HTTPException(status_code=403, detail="You are not a member of this channel")
    
    # Get all members of the channel by joining Membership with User
    query = db.query(User).join(
        Membership, User.id == Membership.user_id
    ).filter(
        Membership.channel_id == channel_id
    )
    
    # Apply search filter if provided
    if search:
        search_lower = search.lower().strip()
        # Try to parse as integer for ID search
        try:
            search_id = int(search_lower)
            query = query.filter(
                or_(
                    User.id == search_id,
                    User.username.ilike(f"%{search_lower}%"),
                    User.display_name.ilike(f"%{search_lower}%")
                )
            )
        except ValueError:
            # Not a number, search by username and display_name
            query = query.filter(
                or_(
                    User.username.ilike(f"%{search_lower}%"),
                    User.display_name.ilike(f"%{search_lower}%")
                )
            )
    
    # Get all users first
    users = query.all()
    
    # Sort by display_name ascending (nulls last), then by username
    def sort_key(user: User):
        # Return a tuple: (display_name or empty string for nulls, username)
        # Empty string sorts before other strings, so we use a large string for nulls
        display_name_value = _as_opt_str(user.display_name)
        username_value = _as_str(user.username)
        display_name = display_name_value.lower() if display_name_value else "zzzzzzzzzz"
        return (display_name, username_value.lower())
    
    sorted_users = sorted(users, key=sort_key)
    
    return [
        ChannelMemberResponse(
            id=_as_int(user.id),
            username=_as_str(user.username),
            display_name=_as_opt_str(user.display_name),
        ) for user in sorted_users
    ]

@router.post("/{channel_id}/members")
async def add_member_to_channel(
    channel_id: int,
    member_request: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if current user is a member of the channel
    current_membership = db.query(Membership).filter(
        Membership.user_id == _as_int(current_user.id),
        Membership.channel_id == channel_id
    ).first()
    if not current_membership:
        raise HTTPException(status_code=403, detail="You are not a member of this channel")
    
    # Find user by username
    user_to_add = db.query(User).filter(User.username == member_request.username).first()
    if not user_to_add:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is already a member
    user_to_add_id = _as_int(user_to_add.id)
    existing_membership = db.query(Membership).filter(
        Membership.user_id == user_to_add_id,
        Membership.channel_id == channel_id
    ).first()
    if existing_membership:
        raise HTTPException(status_code=400, detail="User is already a member of this channel")
    
    # Add user to channel
    new_membership = Membership(user_id=user_to_add_id, channel_id=channel_id)
    db.add(new_membership)
    db.commit()
    # Update WebSocket manager to include the added user in this channel
    manager.add_client_to_channel(user_to_add_id, channel_id)
    
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel_name = _as_str(channel.name)
    await manager.broadcast({
        "type": "join",
        "user_id": user_to_add_id,
        "username": _as_str(user_to_add.username),
        "display_name": _as_opt_str(user_to_add.display_name),
        "channel_id": channel_id,
        "channel_name": channel_name,
    }, channel_id)
    log_join(user_to_add_id, channel_id, channel_name)
    return {"message": f"Added {_as_str(user_to_add.username)} to channel {channel_name}"}
