"""
Django settings for data-processor service.

This is a standalone Django REST framework microservice for document
processing, OCR extraction, and template management.

Environment variables are provided via docker-compose.yml with defaults
for local development. No additional .env.local entries required.
"""

import os
from pathlib import Path
from urllib.parse import quote_plus, unquote, urlparse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# For production, set DJANGO_SECRET_KEY environment variable
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-change-in-production-abc123xyz789"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# Feature flag for data processor
DATA_PROCESSOR_ENABLED = os.getenv("DATA_PROCESSOR_ENABLED", "true").lower() in ("true", "1", "yes")

# JWT shared secret (same as monolith, for admin allowlist enforcement)
JWT_SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
JWT_ALGORITHM = os.getenv("ALGORITHM", "HS256")
ADMIN_ALLOWLIST = os.getenv("ADMIN_ALLOWLIST", "admina")

# Application definition
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "middleware.jwt_auth.AdminAllowlistMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

def _read_secret(secret_file: str | None) -> str:
    if not secret_file:
        return ""
    path = Path(secret_file)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _build_database_url() -> str:
    explicit = os.getenv("DATABASE_URL", "").strip() or os.getenv(
        "DATA_PROCESSOR_DATABASE_URL",
        "",
    ).strip()
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
        return "sqlite:///:memory:"

    db_host = db_host_env or "postgres"
    db_port = db_port_env or "5432"
    db_name = db_name_env or "app_db"
    db_user = db_user_env or "app_user"
    if not db_password:
        db_password = "change-me-local-password"

    return (
        "postgresql://"
        f"{quote_plus(db_user)}:{quote_plus(db_password)}"
        f"@{db_host}:{db_port}/{db_name}"
    )


def _database_settings_from_url(database_url: str) -> dict:
    parsed = urlparse(database_url)
    scheme = parsed.scheme.split("+", 1)[0]
    if scheme.startswith("sqlite"):
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": parsed.path or os.getenv("DATA_PROCESSOR_DB", ":memory:"),
        }

    db_name = (parsed.path or "/app_db").lstrip("/")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": unquote(parsed.username or "app_user"),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "postgres",
        "PORT": str(parsed.port or "5432"),
    }


DATABASE_URL = _build_database_url()
DATABASES = {"default": _database_settings_from_url(DATABASE_URL)}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"

# Django REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "DEFAULT_PAGINATION_CLASS": None,
}

# CORS settings - uses existing ALLOWED_ORIGINS from docker-compose
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# MinIO/S3 configuration - uses existing env vars from docker-compose.yml
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "media")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# Backend FastAPI URL for inter-service communication
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8002")

# Image processing constraints
MAX_IMAGE_WIDTH = int(os.getenv("MAX_IMAGE_WIDTH", "1024"))
MAX_IMAGE_HEIGHT = int(os.getenv("MAX_IMAGE_HEIGHT", "1024"))

# OCR configuration
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
OCR_LANG = os.getenv("OCR_LANG", "eng")

# Preprocessing defaults
PREPROCESSING_NOISE_REDUCTION = os.getenv("PREPROCESSING_NOISE_REDUCTION", "true").lower() in ("true", "1", "yes")
PREPROCESSING_GAUSSIAN_SIGMA = float(os.getenv("PREPROCESSING_GAUSSIAN_SIGMA", "1.0"))
PREPROCESSING_BILATERAL_D = int(os.getenv("PREPROCESSING_BILATERAL_D", "9"))
PREPROCESSING_DESKEW_ENABLED = os.getenv("PREPROCESSING_DESKEW_ENABLED", "true").lower() in ("true", "1", "yes")
PREPROCESSING_DESKEW_MAX_ANGLE = float(os.getenv("PREPROCESSING_DESKEW_MAX_ANGLE", "15.0"))

# Template matching configuration
TEMPLATE_MATCH_MIN_CONFIDENCE = float(os.getenv("TEMPLATE_MATCH_MIN_CONFIDENCE", "0.6"))
TEMPLATE_MATCH_LOWE_RATIO = float(os.getenv("TEMPLATE_MATCH_LOWE_RATIO", "0.75"))

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        "api": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "services": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
