from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from src.core.database import get_db
from src.models.user import User
from src.models.channel import Channel
from src.models.message import Message
from src.models.membership import Membership
from src.api.endpoints.auth import get_current_user
from src.services.websocket_manager import manager
from src.services.irc_logger import log_join, log_part, log_privmsg

router = APIRouter(prefix="/channels", tags=["channels"])

# Pydantic models
class ChannelCreate(BaseModel):
    name: str
    type: str = "public"

class ChannelResponse(BaseModel):
    id: int
    name: str
    type: str

    model_config = {
        "from_attributes": True
    }

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: int
    content: str
    sender_id: int
    channel_id: int
    timestamp: str

    model_config = {
        "from_attributes": True
    }

# API endpoints
@router.post("/", response_model=ChannelResponse)
async def create_channel(channel: ChannelCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if channel.type == "public" and not channel.name.startswith("#"):
        raise HTTPException(status_code=400, detail="Public channel name must start with #")
    # For private channels/DMs, generate a unique name based on user IDs
    if channel.type == "private":
        channel.name = f"dm-{current_user.id}-{channel.name}"
    db_channel = db.query(Channel).filter(Channel.name == channel.name).first()
    if db_channel:
        raise HTTPException(status_code=400, detail="Channel already exists")
    new_channel = Channel(name=channel.name, type=channel.type)
    db.add(new_channel)
    db.commit()
    db.refresh(new_channel)
    # Add current user to channel
    membership = Membership(user_id=current_user.id, channel_id=new_channel.id)
    db.add(membership)
    # If it's a DM, add the other user to the channel
    if channel.type == "private":
        try:
            other_user_id = int(channel.name.split("-")[2])
            other_user = db.query(User).filter(User.id == other_user_id).first()
            if other_user:
                other_membership = Membership(user_id=other_user.id, channel_id=new_channel.id)
                db.add(other_membership)
        except:
            pass
    db.commit()
    log_join(current_user.id, new_channel.id, new_channel.name)
    return new_channel

@router.get("/", response_model=List[ChannelResponse])
async def get_channels(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get all channels the user is a member of
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    channel_ids = [m.channel_id for m in memberships]
    return db.query(Channel).filter(Channel.id.in_(channel_ids)).all()

@router.get("/search")
async def search_channels(name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Search for channels by name (case-insensitive)
    channels = db.query(Channel).filter(Channel.name.ilike(f"%{name}%")).all()
    return [ChannelResponse(id=ch.id, name=ch.name, type=ch.type) for ch in channels]

@router.get("/dms", response_model=List[ChannelResponse])
async def get_direct_messages(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get all direct message channels the user is a member of
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    channel_ids = [m.channel_id for m in memberships]
    return db.query(Channel).filter(Channel.id.in_(channel_ids), Channel.type == "private").all()

@router.post("/dm/{user_id}", response_model=ChannelResponse)
async def create_direct_message_channel(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot create direct message channel with yourself")
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
            return existing_channel
        else:
            # Add current user to existing DM channel
            membership = Membership(user_id=current_user.id, channel_id=existing_channel.id)
            db.add(membership)
            db.commit()
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
    return new_channel

@router.get("/{channel_id}/messages", response_model=List[MessageResponse])
async def get_messages(channel_id: int, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.channel_id == channel_id).order_by(Message.timestamp).all()
    # Convert datetime to string for response
    return [
        MessageResponse(
            id=msg.id,
            content=msg.content,
            sender_id=msg.sender_id,
            channel_id=msg.channel_id,
            timestamp=msg.timestamp.isoformat()
        ) for msg in messages
    ]

@router.post("/{channel_id}/messages", response_model=MessageResponse)
async def send_message(channel_id: int, message: MessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if user is a member of the channel
    membership = db.query(Membership).filter(Membership.user_id == current_user.id, Membership.channel_id == channel_id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this channel")
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    new_message = Message(content=message.content, sender_id=current_user.id, channel_id=channel_id)
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    # Broadcast message via WebSocket
    await manager.broadcast({
        "type": "message",
        "id": new_message.id,
        "content": new_message.content,
        "sender_id": new_message.sender_id,
        "channel_id": new_message.channel_id,
        "timestamp": new_message.timestamp.isoformat(),
    }, channel_id)
    log_privmsg(current_user.id, channel_id, message.content, channel.name if channel else None)
    return MessageResponse(
        id=new_message.id,
        content=new_message.content,
        sender_id=new_message.sender_id,
        channel_id=new_message.channel_id,
        timestamp=new_message.timestamp.isoformat()
    )

@router.post("/{channel_id}/join")
async def join_channel(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = db.query(Membership).filter(Membership.user_id == current_user.id, Membership.channel_id == channel_id).first()
    if membership:
        raise HTTPException(status_code=400, detail="Already a member of this channel")
    new_membership = Membership(user_id=current_user.id, channel_id=channel_id)
    db.add(new_membership)
    db.commit()
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    await manager.broadcast({
        "type": "join",
        "user_id": current_user.id,
        "username": current_user.username,
        "channel_id": channel_id,
        "channel_name": channel.name,
    }, channel_id)
    log_join(current_user.id, channel_id, channel.name)
    return {"message": f"Joined channel {channel.name}"}

@router.post("/{channel_id}/leave")
async def leave_channel(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = db.query(Membership).filter(Membership.user_id == current_user.id, Membership.channel_id == channel_id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Not a member of this channel")
    db.delete(membership)
    db.commit()
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    await manager.broadcast({
        "type": "leave",
        "user_id": current_user.id,
        "username": current_user.username,
        "channel_id": channel_id,
        "channel_name": channel.name,
    }, channel_id)
    log_part(current_user.id, channel_id, channel.name)
    return {"message": f"Left channel {channel.name}"}
