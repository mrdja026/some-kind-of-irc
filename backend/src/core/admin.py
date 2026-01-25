"""Admin allowlist enforcement utilities."""
import logging
from typing import Set
from functools import lru_cache

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models.user import User
from src.api.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_admin_allowlist() -> Set[str]:
    """Parse ADMIN_ALLOWLIST env var into set of lowercase usernames.
    
    Cached on first call for performance.
    Format: semicolon-separated usernames
    Example: ADMIN_ALLOWLIST=alice;bob;charlie
    Default if empty: admina
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
    allowlist = get_admin_allowlist()
    return username.lower() in allowlist


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that checks if current user is in admin allowlist.
    
    Raises:
        HTTPException: 404 if user not in allowlist (security through obscurity)
    """
    if not is_user_admin(current_user.username):
        raise HTTPException(status_code=404, detail="Not Found")
    
    return current_user
