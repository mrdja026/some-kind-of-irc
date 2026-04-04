"""Backend proxy for Gmail AI endpoints with SSE streaming."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, List

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

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

router = APIRouter(prefix="/ai/gmail", tags=["ai"])

MAX_GMAIL_EMAILS = 10


class GmailQuestionsRequest(BaseModel):
    emails: List[dict] = Field(max_length=MAX_GMAIL_EMAILS)
    interest: str = ""
    previous_answers: List[str] = []
    question_count: int = 2


class GmailSummaryRequest(BaseModel):
    emails: List[dict] = Field(max_length=MAX_GMAIL_EMAILS)
    interest: str
    answers: List[str] = []


async def _stream_gmail_questions(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
) -> AsyncIterator[str]:
    """Stream Gmail questions generation via SSE."""
    yield await emit_meta(
        agent="gmail_follow_up_interviewer", model="claude-3-haiku-20240307"
    )
    yield await emit_progress(
        stage="interviewer", message="Generating follow-up questions..."
    )

    adk_url = settings.AI_SERVICE_ADK_URL.rstrip("/")
    headers = {"x-request-id": request_id}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{adk_url}/ai/gmail/questions",
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
            detail = "Gmail questions failed"
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
            code="TIMEOUT", message="Gmail questions request timed out"
        )
    except httpx.RequestError as exc:
        yield await emit_error(code="CONNECTION_ERROR", message=str(exc))


async def _stream_gmail_summary(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
) -> AsyncIterator[str]:
    """Stream Gmail summary generation via SSE."""
    yield await emit_meta(agent="gmail_summary_judge", model="claude-3-haiku-20240307")
    yield await emit_progress(
        stage="action_summary", message="Analyzing emails for action items..."
    )
    yield await emit_progress(
        stage="insight_summary", message="Extracting key insights..."
    )
    yield await emit_progress(stage="triage", message="Prioritizing emails...")
    yield await emit_progress(stage="judge", message="Generating final summary...")

    adk_url = settings.AI_SERVICE_ADK_URL.rstrip("/")
    headers = {"x-request-id": request_id}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{adk_url}/ai/gmail/summary",
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
            detail = "Gmail summary failed"
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
            code="TIMEOUT", message="Gmail summary request timed out"
        )
    except httpx.RequestError as exc:
        yield await emit_error(code="CONNECTION_ERROR", message=str(exc))


@router.post("/questions")
async def generate_gmail_questions(
    request: Request,
    payload: GmailQuestionsRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate Gmail follow-up questions via SSE streaming."""
    del current_user  # Auth validated, user context available if needed

    correlation_id = request.headers.get("x-correlation-id")
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

    return sse_response(
        _stream_gmail_questions(
            request=request,
            payload=payload.model_dump(),
            request_id=request_id,
            correlation_id=correlation_id,
        )
    )


@router.post("/summary")
async def generate_gmail_summary(
    request: Request,
    payload: GmailSummaryRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate Gmail summary via SSE streaming."""
    del current_user  # Auth validated

    correlation_id = request.headers.get("x-correlation-id")
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

    return sse_response(
        _stream_gmail_summary(
            request=request,
            payload=payload.model_dump(),
            request_id=request_id,
            correlation_id=correlation_id,
        )
    )
