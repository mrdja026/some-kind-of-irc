from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from src.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    display_name = Column(String, nullable=True)
    password_hash = Column(String)
    status = Column(String, default="online")
    profile_picture_url = Column(String, nullable=True)
    display_name_updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)