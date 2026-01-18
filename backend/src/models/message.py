from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from src.core.database import Base

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    sender_id = Column(Integer, ForeignKey("users.id"))
    channel_id = Column(Integer, ForeignKey("channels.id"))
    timestamp = Column(DateTime, default=datetime.now)
