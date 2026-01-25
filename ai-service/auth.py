"""JWT cookie validation and admin allowlist enforcement for ai-service.

Mirrors the authentication flow in the monolith:
  - backend/src/api/endpoints/auth.py (get_current_user)
  - backend/src/core/admin.py (require_admin)

Returns HTTP 404 for non-admin users (security through obscurity).
"""

import logging
from functools import lru_cache
from typing import Set

from fastapi import HTTPException, Request
from jose import JWTError, jwt

from config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_admin_allowlist() -> Set[str]:
    """Parse ADMIN_ALLOWLIST env var into set of lowercase usernames.

    Format: semicolon-separated usernames (e.g. 'alice;bob;charlie')
    Default: 'admina' if empty
    """
    raw = settings.ADMIN_ALLOWLIST or ""
    if not raw.strip():
        raw = "admina"

    allowlist = {
        username.strip().lower()
        for username in raw.split(";")
        if username.strip()
    }
    logger.info(f"Admin allowlist loaded: {len(allowlist)} users")
    return allowlist


def is_user_admin(username: str) -> bool:
    """Check if username is in admin allowlist (case-insensitive)."""
    return username.lower() in get_admin_allowlist()


def get_username_from_token(request: Request) -> str:
    """Extract and verify the JWT token from the access_token cookie.

    Returns the username (sub claim) if valid.
    Raises HTTPException(404) if token is missing, invalid, or user is not admin.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=404, detail="Not Found")

    # Strip 'Bearer ' prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return username
    except JWTError:
        raise HTTPException(status_code=404, detail="Not Found")


async def require_admin(request: Request) -> str:
    """FastAPI dependency that enforces admin allowlist.

    Returns the admin username if authorized.
    Raises HTTPException(404) for non-admin or unauthenticated users.
    """
    username = get_username_from_token(request)
    if not is_user_admin(username):
        raise HTTPException(status_code=404, detail="Not Found")
    return username
