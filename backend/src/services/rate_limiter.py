"""Shared Redis-backed rate limiter for API endpoints."""

import time
from typing import Optional, Tuple

import redis.asyncio as redis
from fastapi import HTTPException

from src.core.config import settings

# Singleton Redis client (lazy)
_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Return a cached Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,
        )
    return _redis_client


async def check_rate_limit(user_id: int, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
    """
    Sliding-window rate limit using a Redis sorted set per user.

    Returns (allowed, retry_after_seconds).
    Fail-open if Redis is unavailable.
    """
    redis_client = _get_redis()
    now = int(time.time())
    window_start = now - window_seconds
    key = f"rate:{user_id}"

    try:
        # Remove entries outside window
        await redis_client.zremrangebyscore(key, 0, window_start)

        current = await redis_client.zcard(key)
        if current >= max_requests:
            # Oldest timestamp determines retry-after
            oldest = await redis_client.zrange(key, 0, 0, withscores=True)
            oldest_ts = int(oldest[0][1]) if oldest else now
            retry_after = max(1, window_seconds - (now - oldest_ts))
            return False, retry_after

        # Record this request and set TTL to bound memory
        await redis_client.zadd(key, {str(now): now})
        await redis_client.expire(key, window_seconds)
        return True, 0
    except Exception:
        # Fail-open to avoid hard outages if Redis is down
        return True, 0


async def remaining_requests(user_id: int, max_requests: int, window_seconds: int) -> int:
    """Return remaining requests in the current window (best effort)."""
    redis_client = _get_redis()
    now = int(time.time())
    window_start = now - window_seconds
    try:
        await redis_client.zremrangebyscore(f"rate:{user_id}", 0, window_start)
        used = await redis_client.zcard(f"rate:{user_id}")
        return max(0, max_requests - used)
    except Exception:
        return max_requests


async def enforce_rate_limit(user_id: int, max_requests: int, window_seconds: int):
    """Raise HTTP 429 if user exceeds rate limit."""
    allowed, retry_after = await check_rate_limit(user_id, max_requests, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit",
                "retry_after_seconds": retry_after,
            },
        )
