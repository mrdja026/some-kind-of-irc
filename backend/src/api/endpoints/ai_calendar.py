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


async def _stream_calendar_questions(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
) -> AsyncIterator[str]:
    """Stream Calendar question generation via SSE."""
    yield await emit_meta(agent="calendar_agent", model="gemini-2.0-flash")
    yield await emit_progress(stage="planning", message="Analyzing your request...")

    adk_url = settings.AI_SERVICE_ADK_URL.rstrip("/")
    headers = {"x-request-id": request_id}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{adk_url}/ai/calendar/questions",
                json=payload,
                cookies=dict(request.cookies),
                headers=headers,
            )

        if not response.is_success:
            detail = "Calendar questions failed"
            try:
                error_body = response.json()
                detail = error_body.get("detail", detail)
            except Exception:
                if response.text:
                    detail = response.text
            yield await emit_error(code="ADK_ERROR", message=detail)
            return

        result = response.json()
        yield await emit_done(result=result)

    except httpx.TimeoutException:
        yield await emit_error(
            code="TIMEOUT", message="Calendar questions request timed out"
        )
    except httpx.RequestError as exc:
        yield await emit_error(code="CONNECTION_ERROR", message=str(exc))


async def _stream_calendar_create(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
) -> AsyncIterator[str]:
    """Stream Calendar event creation via SSE."""
    yield await emit_meta(agent="calendar_agent", model="gemini-2.0-flash")
    yield await emit_progress(stage="creating", message="Creating calendar event...")

    adk_url = settings.AI_SERVICE_ADK_URL.rstrip("/")
    headers = {"x-request-id": request_id}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{adk_url}/ai/calendar/create",
                json=payload,
                cookies=dict(request.cookies),
                headers=headers,
            )

        if not response.is_success:
            detail = "Calendar create failed"
            try:
                error_body = response.json()
                detail = error_body.get("detail", detail)
            except Exception:
                if response.text:
                    detail = response.text
            yield await emit_error(code="ADK_ERROR", message=detail)
            return

        result = response.json()
        yield await emit_done(result=result)

    except httpx.TimeoutException:
        yield await emit_error(
            code="TIMEOUT", message="Calendar create request timed out"
        )
    except httpx.RequestError as exc:
        yield await emit_error(code="CONNECTION_ERROR", message=str(exc))


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
