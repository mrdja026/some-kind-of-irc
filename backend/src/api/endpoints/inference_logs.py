"""API endpoint for reading AI inference events from Redis stream.

Supports the extended event schema with caller attribution, tool_calls,
question(s), reasoning, and plan fields.
"""

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


class CallerInfo(BaseModel):
    """Agent caller attribution metadata."""

    agent: str
    role: str | None = None
    stage: str
    attempt: int | None = None
    model: str | None = None


class ToolCall(BaseModel):
    """Tool invocation record."""

    tool_name: str
    args: Any | None = None
    result: Any | None = None
    error: str | None = None
    elapsed_ms: int | None = None
    reason: str | None = None
    reason_detail: str | None = None
    caller: CallerInfo | None = None


class InferenceLogEvent(BaseModel):
    """A single inference log event."""

    event_id: str
    recorded_at: str
    source: str
    kind: str
    backend: str
    username: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    caller: CallerInfo | None = None
    tool_calls: list[ToolCall] | None = None
    question: str | None = None
    questions: list[str] | None = None
    reasoning: str | None = None
    plan: dict[str, Any] | None = None
    payload: dict[str, Any]


class InferenceLogsResponse(BaseModel):
    """Response containing inference log events."""

    events: list[InferenceLogEvent]
    total: int


AI_EVENT_KINDS = None


def _safe_json_loads(value: str | None) -> Any:
    """Parse JSON string, returning None on failure."""
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


@router.get("/logs", response_model=InferenceLogsResponse)
async def get_inference_logs(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
) -> InferenceLogsResponse:
    """Read AI inference events from Redis stream.

    Returns the most recent inference log events for the current user,
    including caller attribution, tool_calls, and reasoning fields.
    """
    try:
        client = _get_redis_log()
        stream_key = settings.AI_SESSION_STREAM_KEY

        events: list[InferenceLogEvent] = []
        last_id = "+"
        batch_size = min(limit * 3, 500)

        while len(events) < limit:
            rows = client.xrevrange(stream_key, max=last_id, count=batch_size)
            if not rows:
                break

            for msg_id, fields in rows:
                kind = fields.get("kind", "")
                if AI_EVENT_KINDS is not None and kind not in AI_EVENT_KINDS:
                    continue

                # Scope results to the requesting user
                row_username = fields.get("username") or ""
                if row_username != current_user.username:
                    continue

                payload_raw = fields.get("payload", "{}")
                try:
                    payload = json.loads(payload_raw)
                except json.JSONDecodeError:
                    payload = {"raw": payload_raw}

                # Parse new fields
                caller_raw = _safe_json_loads(fields.get("caller"))
                caller = (
                    CallerInfo(**caller_raw) if isinstance(caller_raw, dict) else None
                )

                tool_calls_raw = _safe_json_loads(fields.get("tool_calls"))
                tool_calls = None
                if isinstance(tool_calls_raw, list):
                    tool_calls = [
                        ToolCall(**tc) for tc in tool_calls_raw if isinstance(tc, dict)
                    ]

                questions_raw = _safe_json_loads(fields.get("questions"))
                questions = questions_raw if isinstance(questions_raw, list) else None

                plan_raw = _safe_json_loads(fields.get("plan"))
                plan = plan_raw if isinstance(plan_raw, dict) else None

                event = InferenceLogEvent(
                    event_id=msg_id,
                    recorded_at=fields.get("recorded_at", ""),
                    source=fields.get("source", ""),
                    kind=kind,
                    backend=fields.get("backend", ""),
                    username=row_username or None,
                    session_id=fields.get("session_id") or None,
                    request_id=fields.get("request_id") or None,
                    correlation_id=fields.get("correlation_id") or None,
                    caller=caller,
                    tool_calls=tool_calls,
                    question=fields.get("question") or None,
                    questions=questions,
                    reasoning=fields.get("reasoning") or None,
                    plan=plan,
                    payload=payload
                    if isinstance(payload, dict)
                    else {"value": payload},
                )
                events.append(event)

                if len(events) >= limit:
                    break

            if len(rows) < batch_size:
                # Stream exhausted
                break
            # Advance cursor past the last entry seen
            last_id = "(" + rows[-1][0]

        events.reverse()

        return InferenceLogsResponse(events=events, total=len(events))

    except HTTPException:
        raise
    except redis.RedisError as exc:
        logger.error("Redis error reading inference logs: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Failed to read inference logs from Redis",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error reading inference logs: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from exc
