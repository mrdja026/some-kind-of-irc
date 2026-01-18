from sqlalchemy import Column, Integer, DateTime, ForeignKey
from datetime import datetime
from src.core.database import Base

class Membership(Base):
    __tablename__ = "memberships"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), primary_key=True)
    joined_at = Column(DateTime, default=datetime.now)
