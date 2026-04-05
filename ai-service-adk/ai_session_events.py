"""Append annotated AI events to redis-log stream (ADK service).

Supports AI inference logging with caller attribution, tool_calls, and
reason taxonomy per the ai-inference-events schema.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

import redis.asyncio as redis_async

from config import settings

LOG = logging.getLogger(__name__)

_ai_log: Optional[redis_async.Redis] = None


class CallerInfo(TypedDict, total=False):
    """Agent caller attribution metadata."""

    agent: (
        str  # Logical agent identifier (candidate_a, judge, gmail_summary_judge, etc.)
    )
    role: str  # Human-readable role name
    stage: str  # Stage label (candidate_a, followup_judge, etc.)
    attempt: int  # Attempt number for followup loops
    model: str  # Model identifier, if available


class ToolCall(TypedDict, total=False):
    """Tool invocation record."""

    tool_name: str
    args: Any
    result: Any
    error: str
    elapsed_ms: int
    reason: str  # clarity, factual, consistency, coverage, timeline, financial, policy, other
    reason_detail: str  # Required when reason=other
    caller: CallerInfo  # Optional per-call caller override


def _client() -> Optional[redis_async.Redis]:
    global _ai_log
    url = settings.REDIS_LOG_URL.strip()
    if not url:
        return None
    if _ai_log is None:
        _ai_log = redis_async.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
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
    session_id: Optional[str] = None,
    caller: Optional[CallerInfo] = None,
    tool_calls: Optional[list[ToolCall]] = None,
    question: Optional[str] = None,
    questions: Optional[list[str]] = None,
    reasoning: Optional[str] = None,
    plan: Optional[dict[str, Any]] = None,
) -> None:
    """Append an AI inference event to the Redis stream.

    Args:
        kind: Event type (claims_candidate, gmail_step_judge, tool_invoked, etc.)
        username: Authenticated user who triggered the request
        payload: Full event payload (raw or structured request/response data)
        source: Service that emitted the event (ai_service_adk, backend, etc.)
        backend: AI backend (google_adk, crewai, local_vllm, n/a)
        correlation_id: Optional correlation ID from request headers
        request_id: Optional request ID for tracing
        session_id: Session ID for multi-step correlation
        caller: Agent caller attribution (agent, role, stage, attempt, model)
        tool_calls: List of tool invocations with args/results/reason taxonomy
        question: Single question string (for followup events)
        questions: List of question strings (for multi-question events)
        reasoning: Agent reasoning string
        plan: Agent plan or step list
    """
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
    if session_id:
        fields["session_id"] = session_id

    # New fields for AI inference logging
    if caller is not None:
        fields["caller"] = json.dumps(caller, default=str)
    if tool_calls is not None:
        fields["tool_calls"] = json.dumps(tool_calls, default=str)
    if question is not None:
        fields["question"] = question
    if questions is not None:
        fields["questions"] = json.dumps(questions)
    if reasoning is not None:
        fields["reasoning"] = reasoning
    if plan is not None:
        fields["plan"] = json.dumps(plan, default=str)

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
