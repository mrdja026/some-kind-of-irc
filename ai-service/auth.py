"""JWT cookie validation and AI allowlist enforcement for ai-service.

Mirrors the authentication flow in the monolith:
  - backend/src/api/endpoints/auth.py (get_current_user)
  - backend/src/core/admin.py (allowlist pattern)

Returns HTTP 404 for unauthorized users (security through obscurity).
"""

import logging
from functools import lru_cache
from typing import Optional, Set

from fastapi import HTTPException, Request
from jose import JWTError, jwt

from config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_ai_allowlist() -> Set[str]:
    """Parse AI allowlist env var into set of lowercase usernames.

    Resolution order:
    1) AI_ALLOWLIST
    2) ADMIN_ALLOWLIST (legacy fallback)
    3) hard-coded default
    """
    raw = settings.AI_ALLOWLIST or settings.ADMIN_ALLOWLIST or ""
    if not raw.strip():
        raw = "admina;guest2;guest3"

    allowlist = {
        username.strip().lower()
        for username in raw.split(";")
        if username.strip()
    }
    logger.info("AI allowlist loaded: %s users", len(allowlist))
    return allowlist


def is_user_allowed_for_ai(username: str) -> bool:
    """Check if username is in AI allowlist (case-insensitive)."""
    return username.lower() in get_ai_allowlist()


def get_username_from_token(request: Request) -> str:
    """Extract and verify the JWT token from the access_token cookie.

    Returns the username (sub claim) if valid.
    Raises HTTPException(404) if token is missing or invalid.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=404, detail="Not Found")

    # Strip 'Bearer ' prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return username
    except JWTError:
        raise HTTPException(status_code=404, detail="Not Found")


async def require_ai_access(request: Request) -> str:
    """FastAPI dependency that enforces AI allowlist.

    Returns the username if authorized for AI access.
    Raises HTTPException(404) for unauthorized or unauthenticated users.
    """
    username = get_username_from_token(request)
    if not is_user_allowed_for_ai(username):
        raise HTTPException(status_code=404, detail="Not Found")
    return username
