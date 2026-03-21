"""API endpoint for reading Gmail inference events from Redis stream."""

import json
import logging
from typing import Any

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.core.config import settings
from src.api.endpoints.auth import get_current_user
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["inference"])

_redis_log_client: redis.Redis | None = None


def _get_redis_log() -> redis.Redis:
    """Get or create Redis log client."""
    global _redis_log_client
    if _redis_log_client is None:
        url = settings.REDIS_LOG_URL.strip()
        if not url:
            raise HTTPException(
                status_code=503,
                detail="Redis log URL not configured",
            )
        _redis_log_client = redis.from_url(url, decode_responses=True)
    return _redis_log_client


class InferenceLogEvent(BaseModel):
    """A single inference log event."""

    event_id: str
    recorded_at: str
    source: str
    kind: str
    backend: str
    username: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any]


class InferenceLogsResponse(BaseModel):
    """Response containing inference log events."""

    events: list[InferenceLogEvent]
    total: int


GMAIL_EVENT_KINDS = frozenset({
    "gmail_questions",
    "gmail_summary",
    "gmail_step_questions",
    "gmail_step_summary_action",
    "gmail_step_summary_insight",
    "gmail_step_classification",
    "gmail_step_judge",
})


@router.get("/logs", response_model=InferenceLogsResponse)
async def get_inference_logs(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
) -> InferenceLogsResponse:
    """Read Gmail inference events from Redis stream.

    Returns the most recent inference log events, filtered for Gmail-related events.
    """
    try:
        client = _get_redis_log()
        stream_key = settings.AI_SESSION_STREAM_KEY

        rows = client.xrevrange(stream_key, count=limit * 3)

        events: list[InferenceLogEvent] = []
        for msg_id, fields in rows:
            kind = fields.get("kind", "")
            if kind not in GMAIL_EVENT_KINDS:
                continue

            payload_raw = fields.get("payload", "{}")
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                payload = {"raw": payload_raw}

            event = InferenceLogEvent(
                event_id=msg_id,
                recorded_at=fields.get("recorded_at", ""),
                source=fields.get("source", ""),
                kind=kind,
                backend=fields.get("backend", ""),
                username=fields.get("username") or None,
                request_id=fields.get("request_id") or None,
                correlation_id=fields.get("correlation_id") or None,
                payload=payload if isinstance(payload, dict) else {"value": payload},
            )
            events.append(event)

            if len(events) >= limit:
                break

        events.reverse()

        return InferenceLogsResponse(events=events, total=len(events))

    except redis.RedisError as exc:
        logger.error("Redis error reading inference logs: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Failed to read inference logs from Redis",
        )
    except Exception as exc:
        logger.exception("Unexpected error reading inference logs: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
