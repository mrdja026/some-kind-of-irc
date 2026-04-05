"""Backend proxy for Calendar AI endpoints with SSE streaming."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, List

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.api.endpoints.auth import get_current_user
from src.api.utils.sse import (
    emit_done,
    emit_error,
    emit_meta,
    emit_progress,
    sse_response,
)
from src.core.config import settings
from src.models.user import User

router = APIRouter(prefix="/ai/calendar", tags=["ai"])


class CalendarEventPayload(BaseModel):
    title: str
    start_datetime: str
    end_datetime: str
    timezone: str = "UTC"
    attendees: List[str] = []


class CalendarQuestionRequest(BaseModel):
    request: str
    previous_answers: List[str] = []


class CalendarCreateRequest(BaseModel):
    event: CalendarEventPayload


async def _create_sse_proxy_stream(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
    endpoint_path: str,
    agent: str,
    model: str,
    progress_stage: str,
    progress_message: str,
    error_prefix: str,
    timeout: float = 30.0,
) -> AsyncIterator[str]:
    """Reusable SSE proxy stream factory for ADK calendar endpoints."""
    yield await emit_meta(agent=agent, model=model)
    yield await emit_progress(stage=progress_stage, message=progress_message)

    adk_url = settings.AI_SERVICE_ADK_URL.rstrip("/")
    headers = {"x-request-id": request_id}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{adk_url}{endpoint_path}",
                json=payload,
                cookies=dict(request.cookies),
                headers=headers,
            )
            is_success = response.is_success
            try:
                response_data: Any = response.json()
            except Exception:
                response_data = None
            response_text = response.text

        if not is_success:
            detail = error_prefix
            if isinstance(response_data, dict):
                detail = response_data.get("detail", detail)
            elif response_text:
                detail = response_text
            yield await emit_error(code="ADK_ERROR", message=detail)
            return

        if response_data is None:
            yield await emit_error(
                code="ADK_ERROR", message="Invalid JSON response from ADK service"
            )
            return
        yield await emit_done(result=response_data)

    except httpx.TimeoutException:
        yield await emit_error(
            code="TIMEOUT", message=f"{error_prefix} request timed out"
        )
    except httpx.RequestError as exc:
        yield await emit_error(code="CONNECTION_ERROR", message=str(exc))


async def _stream_calendar_questions(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
) -> AsyncIterator[str]:
    """Stream Calendar question generation via SSE."""
    async for chunk in _create_sse_proxy_stream(
        request=request,
        payload=payload,
        request_id=request_id,
        correlation_id=correlation_id,
        endpoint_path="/ai/calendar/questions",
        agent="calendar_agent",
        model="gemini-2.0-flash",
        progress_stage="planning",
        progress_message="Analyzing your request...",
        error_prefix="Calendar questions failed",
    ):
        yield chunk


async def _stream_calendar_create(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
) -> AsyncIterator[str]:
    """Stream Calendar event creation via SSE."""
    async for chunk in _create_sse_proxy_stream(
        request=request,
        payload=payload,
        request_id=request_id,
        correlation_id=correlation_id,
        endpoint_path="/ai/calendar/create",
        agent="calendar_agent",
        model="gemini-2.0-flash",
        progress_stage="creating",
        progress_message="Creating calendar event...",
        error_prefix="Calendar create failed",
    ):
        yield chunk


@router.post("/questions")
async def generate_calendar_question(
    request: Request,
    payload: CalendarQuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate Calendar clarification/confirmation via SSE streaming."""
    del current_user  # Auth validated

    correlation_id = request.headers.get("x-correlation-id")
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

    return sse_response(
        _stream_calendar_questions(
            request=request,
            payload=payload.model_dump(),
            request_id=request_id,
            correlation_id=correlation_id,
        )
    )


@router.post("/create")
async def create_calendar_event(
    request: Request,
    payload: CalendarCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """Create Calendar event via SSE streaming."""
    del current_user  # Auth validated

    correlation_id = request.headers.get("x-correlation-id")
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

    return sse_response(
        _stream_calendar_create(
            request=request,
            payload=payload.model_dump(),
            request_id=request_id,
            correlation_id=correlation_id,
        )
    )
