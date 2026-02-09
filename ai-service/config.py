"""Configuration for ai-service, loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT verification (shared with monolith)
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"

    # Admin allowlist (semicolon-separated, case-insensitive)
    ADMIN_ALLOWLIST: str = "admina"

    # Redis (shared with monolith for rate limiting)
    REDIS_URL: str = "redis://redis:6379/0"

    # AI rate limiting
    AI_RATE_LIMIT_PER_HOUR: int = 10

    # Anthropic Claude configuration
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-3-haiku-20240307"
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"


settings = Settings()
