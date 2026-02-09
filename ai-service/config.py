"""Configuration for ai-service, loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT verification (shared with monolith)
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"

    # AI allowlist (semicolon-separated, case-insensitive)
    # This is intentionally separate from monolith ADMIN_ALLOWLIST.
    AI_ALLOWLIST: str = "admina;guest2;guest3"
    ADMIN_ALLOWLIST: str = "admina"

    # Browser origins allowed to call ai-service directly.
    ALLOWED_ORIGINS: str = "http://localhost:4269,http://127.0.0.1:4269,http://localhost"

    # Redis (shared with monolith for rate limiting)
    REDIS_URL: str = "redis://redis:6379/0"

    # AI rate limiting
    AI_RATE_LIMIT_PER_HOUR: int = 10

    # Development diagnostics
    AI_DEBUG_LOG: bool = False

    # Anthropic Claude configuration
    ANTHROPIC_API_KEY: str = "CHANGE_ME"
    CLAUDE_MODEL: str = "claude-3-haiku-20240307"
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"


settings = Settings()
