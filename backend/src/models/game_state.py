from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base


class GameState(Base):
    """Stores individual player game data on the 64x64 grid."""
    __tablename__ = "game_states"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    position_x = Column(Integer, default=32)  # Starting position center-ish
    position_y = Column(Integer, default=32)
    health = Column(Integer, default=100)
    max_health = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship to user
    user = relationship("User", backref="game_state")
