"""Append annotated Gmail AI events to redis-log stream (ADK service)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis_async

from config import settings

LOG = logging.getLogger(__name__)

_ai_log: Optional[redis_async.Redis] = None


def _client() -> Optional[redis_async.Redis]:
    global _ai_log
    url = settings.REDIS_LOG_URL.strip()
    if not url:
        return None
    if _ai_log is None:
        _ai_log = redis_async.from_url(url, encoding="utf-8", decode_responses=True)
    return _ai_log


async def append_ai_session_event(
    *,
    kind: str,
    username: str,
    payload: dict[str, Any],
    source: str = "ai_service_adk",
    backend: str = "google_adk",
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    client = _client()
    if client is None:
        return

    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    fields: dict[str, str] = {
        "recorded_at": recorded_at,
        "source": source,
        "kind": kind,
        "backend": backend,
        "username": username or "",
        "payload": json.dumps(payload, default=str),
    }
    if correlation_id:
        fields["correlation_id"] = correlation_id
    if request_id:
        fields["request_id"] = request_id

    try:
        await client.xadd(
            settings.AI_SESSION_STREAM_KEY,
            fields,
            maxlen=settings.AI_SESSION_STREAM_MAXLEN,
            approximate=True,
        )
    except Exception:
        LOG.warning("Failed to XADD AI session event (kind=%s)", kind, exc_info=True)


def new_request_id() -> str:
    return uuid.uuid4().hex
