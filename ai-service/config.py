"""Configuration for ai-service, loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT verification (shared with monolith)
    SECRET_KEY: str = "T)mat)P)OtatTo#)92"
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
    LOCAL_QA_RATE_LIMIT_PER_HOUR: int = 20

    # Development diagnostics
    AI_DEBUG_LOG: bool = False

    # Anthropic Claude configuration
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-3-haiku-20240307"
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"

    # Local Q&A configuration (CrewAI + local vLLM)
    FEATURE_LOCAL_QA: bool = True
    LOCAL_QA_VLLM_BASE_URL: str = "http://host.docker.internal:8000/v1"
    LOCAL_QA_MODEL_NAME: str = "katanemo/Arch-Function-3B"
    LOCAL_QA_API_KEY: str = "NA"


settings = Settings()
