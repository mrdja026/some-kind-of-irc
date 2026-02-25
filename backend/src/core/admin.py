"""Admin allowlist enforcement utilities."""
import logging
from typing import Set
from functools import lru_cache

from src.core.config import settings

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

