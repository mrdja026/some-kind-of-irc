from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from src.core.database import Base

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(String, default="public")
    is_data_processor = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
