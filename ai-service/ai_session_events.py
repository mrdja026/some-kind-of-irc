"""Append annotated Gmail (and optional generic) AI events to redis-log stream."""

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
    source: str,
    backend: str,
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


GMAIL_STEP_KINDS = frozenset({
    "gmail_step_questions",
    "gmail_step_summary_action",
    "gmail_step_summary_insight",
    "gmail_step_classification",
    "gmail_step_judge",
})


async def append_gmail_step_event(
    *,
    stage: str,
    username: str,
    input_preview: str,
    output: dict[str, Any],
    model: str,
    request_id: str,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit a granular Gmail inference step event for timeline visualization.

    Args:
        stage: Step name (questions, summary_action, summary_insight, classification, judge)
        username: User who triggered the request
        input_preview: Truncated input context (max 500 chars)
        output: Structured result from this step
        model: LLM model name used
        request_id: Unique request identifier
        correlation_id: Optional correlation ID for request tracing
    """
    kind = f"gmail_step_{stage}"
    if kind not in GMAIL_STEP_KINDS:
        LOG.warning("Unknown gmail step stage: %s", stage)
        return

    payload = {
        "stage": stage,
        "input_preview": input_preview[:500] if input_preview else "",
        "output": output,
        "model": model,
    }

    await append_ai_session_event(
        kind=kind,
        username=username,
        payload=payload,
        source="ai_service",
        backend="crewai",
        correlation_id=correlation_id,
        request_id=request_id,
    )
