from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from src.core.database import Base

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(String, default="public")
    created_at = Column(DateTime, default=datetime.now)
