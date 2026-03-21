"""Configuration for ai-service-adk, loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT verification (shared with monolith)
    SECRET_KEY: str = "T)mat)P)OtatTo#)92"
    ALGORITHM: str = "HS256"

    # AI allowlist (semicolon-separated, case-insensitive)
    AI_ALLOWLIST: str = "admina;guest;guest2;guest3"
    ADMIN_ALLOWLIST: str = "admina"

    # Browser origins allowed to call ai-service-adk directly.
    ALLOWED_ORIGINS: str = (
        "http://localhost:4269,http://127.0.0.1:4269,http://localhost"
    )

    # Redis (shared with monolith for rate limiting)
    REDIS_URL: str = "redis://redis:6379/0"

    # Ephemeral redis-log: AI session events (XADD). Empty REDIS_LOG_URL disables emission.
    REDIS_LOG_URL: str = ""
    AI_SESSION_STREAM_KEY: str = "ai:session_events"
    AI_SESSION_STREAM_MAXLEN: int = 500

    # AI rate limiting
    AI_RATE_LIMIT_PER_HOUR: int = 10

    # Development diagnostics
    AI_DEBUG_LOG: bool = False

    # Google ADK with LiteLLM model configuration
    # LiteLLM format: provider/model (e.g., anthropic/claude-3-haiku-20240307)
    ADK_MODEL: str = "anthropic/claude-3-haiku-20240307"

    # Anthropic API key (used by LiteLLM)
    ANTHROPIC_API_KEY: str = ""

    # Backend integration (calendar tool calls)
    BACKEND_URL: str = "http://backend:8002"

    # Service port
    PORT: int = 8004


settings = Settings()
