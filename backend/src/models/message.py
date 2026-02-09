from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from src.core.database import Base

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    image_url = Column(String, nullable=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.now)
