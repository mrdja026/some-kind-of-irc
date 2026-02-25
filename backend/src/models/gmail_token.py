from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from src.core.database import Base


class GmailToken(Base):
    __tablename__ = "gmail_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=False)
    token_type = Column(String, nullable=True)
    scope = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
