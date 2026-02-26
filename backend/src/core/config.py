from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
import os


def _read_secret(secret_file: str | None) -> str:
    if not secret_file:
        return ""
    path = Path(secret_file)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _build_database_url() -> str:
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        return explicit

    db_host_env = os.getenv("DB_HOST", "").strip()
    db_port_env = os.getenv("DB_PORT", "").strip()
    db_name_env = os.getenv("DB_NAME", "").strip()
    db_user_env = os.getenv("DB_USER", "").strip()
    db_password_env = os.getenv("DB_PASSWORD", "").strip()
    db_password_file_env = os.getenv("DB_PASSWORD_FILE", "").strip()

    db_password = db_password_env or _read_secret(db_password_file_env)
    if (
        not db_host_env
        and not db_port_env
        and not db_name_env
        and not db_user_env
        and not db_password_env
        and not db_password_file_env
    ):
        # Preserve local non-docker behavior when no DB settings are provided.
        return "sqlite:///./chat.db"

    db_host = db_host_env or "postgres"
    db_port = db_port_env or "5432"
    db_name = db_name_env or "app_db"
    db_user = db_user_env or "app_user"
    if not db_password:
        db_password = "change-me-local-password"

    return (
        "postgresql+psycopg://"
        f"{quote_plus(db_user)}:{quote_plus(db_password)}"
        f"@{db_host}:{db_port}/{db_name}"
    )


class Settings(BaseSettings):
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = _build_database_url()
    MEDIA_STORAGE_URL: str = "http://localhost:9101"

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

    # Frontend URL for Redirects
    FRONTEND_URL: str = "http://localhost:4269"

    # Gmail OAuth Configuration
    GMAIL_OAUTH_CLIENT_ID: str = ""
    GMAIL_OAUTH_CLIENT_SECRET: str = ""
    GMAIL_OAUTH_REDIRECT_URL: str = ""
    GMAIL_OAUTH_SCOPES: str = "https://www.googleapis.com/auth/gmail.readonly"

    @property
    def data_processor_enabled(self) -> bool:
        """Check if data processor feature is enabled."""
        env_value = os.getenv("FEATURE_DATA_PROCESSOR", "").lower()
        if env_value in ("true", "1", "yes"):
            return True
        return self.FEATURE_DATA_PROCESSOR


settings = Settings()
