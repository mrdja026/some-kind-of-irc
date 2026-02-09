from datetime import timedelta
from typing import Optional
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = "sqlite:///./chat.db"
    MEDIA_STORAGE_URL: str = "http://localhost:9101"
    
    # Anthropic Claude Configuration
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-3-haiku-20240307"
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"
    
    # AI Rate Limiting
    AI_RATE_LIMIT_PER_HOUR: int = 10
    
    # Data Processor Microservice Configuration
    DATA_PROCESSOR_URL: str = "http://data-processor:8003"
    FEATURE_DATA_PROCESSOR: bool = False
    
    # Redis Configuration (for pub/sub events)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Admin Allowlist Configuration (semicolon-separated usernames)
    # Example: ADMIN_ALLOWLIST=alice;bob;charlie
    ADMIN_ALLOWLIST: str = ""
    
    # Audit Logger Microservice URL
    AUDIT_LOGGER_URL: str = "http://localhost:8004"
    
    @property
    def data_processor_enabled(self) -> bool:
        """Check if data processor feature is enabled."""
        # Can be enabled via environment variable or settings
        env_value = os.getenv("FEATURE_DATA_PROCESSOR", "").lower()
        if env_value in ("true", "1", "yes"):
            return True
        return self.FEATURE_DATA_PROCESSOR

settings = Settings()
