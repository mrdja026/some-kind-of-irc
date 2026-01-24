from datetime import timedelta
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = "sqlite:///./chat.db"
    MEDIA_STORAGE_URL: str = "http://localhost:9101"

settings = Settings()
