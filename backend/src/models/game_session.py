from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base


class GameSession(Base):
    """Links users to their active game session in a #game channel."""
    __tablename__ = "game_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    game_state_id = Column(Integer, ForeignKey("game_states.id"), index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship("User", backref="game_sessions")
    game_state = relationship("GameState", backref="sessions")
    channel = relationship("Channel", backref="game_sessions")
