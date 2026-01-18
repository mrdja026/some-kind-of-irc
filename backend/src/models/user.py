from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from src.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    status = Column(String, default="online")
    created_at = Column(DateTime, default=datetime.now)
