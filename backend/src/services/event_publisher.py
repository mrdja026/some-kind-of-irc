"""Redis event publisher for user lifecycle events."""
import json
import logging
from datetime import datetime
from typing import Optional

import redis

from src.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Lazy initialization of Redis client with connection pooling."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
    return _redis_client


def publish_user_registered(user_id: int, username: str) -> bool:
    """Publish user.registered event.
    
    Fire-and-forget: Registration succeeds even if Redis is unavailable.
    """
    try:
        client = get_redis_client()
        event = {
            "event_type": "user.registered",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow().isoformat(),
        }
        client.publish("user.events", json.dumps(event))
        return True
    except Exception as e:
        logger.warning(f"Failed to publish user.registered event: {e}")
        return False
