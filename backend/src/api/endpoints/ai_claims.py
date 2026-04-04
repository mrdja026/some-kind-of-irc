"""Backend proxy for Claims AI endpoints with SSE streaming."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, List, Optional

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

router = APIRouter(prefix="/ai/claims", tags=["ai"])


class ClaimQaHistoryEntry(BaseModel):
    question: str
    answer: str


class ClaimQaRequest(BaseModel):
    claim: Any
    question: str
    history: List[ClaimQaHistoryEntry] = []
    question_count: int = Field(0, ge=0, le=5)
    asked_questions: List[str] = []
    tool_history: List[dict] = []
    session_id: Optional[str] = None


class ClaimQaResponse(BaseModel):
    answer: str
    reasoning: str
    done: bool = False
    next_question: Optional[str] = None
    followup_reasoning: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    tool_history: Optional[List[dict]] = None
    flags: Optional[dict] = None
    session_id: Optional[str] = None


async def _stream_claims_qa(
    request: Request,
    payload: dict[str, Any],
    request_id: str,
    correlation_id: str | None,
) -> AsyncIterator[str]:
    """Stream Claims Q&A via SSE."""
    yield await emit_meta(agent="claims_qa_agent", model="claude-3-haiku-20240307")
    yield await emit_progress(stage="truth_check", message="Validating claim data...")
    yield await emit_progress(
        stage="candidate_a", message="Generating candidate answer A..."
    )
    yield await emit_progress(
        stage="candidate_b", message="Generating candidate answer B..."
    )
    yield await emit_progress(stage="judge", message="Evaluating best answer...")

    adk_url = settings.AI_SERVICE_ADK_URL.rstrip("/")
    headers = {"x-request-id": request_id}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id

    try:
        # Claims Q&A can take longer due to multi-step agent flow
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{adk_url}/ai/claims/qa",
                json=payload,
                cookies=dict(request.cookies),
                headers=headers,
            )

        if not response.is_success:
            detail = "Claims Q&A failed"
            try:
                error_body = response.json()
                if isinstance(error_body, dict):
                    detail = str(error_body.get("detail", detail))
                elif response.text:
                    detail = response.text
            except ValueError:
                if response.text:
                    detail = response.text
            yield await emit_error(code="ADK_ERROR", message=detail)
            return

        try:
            result = response.json()
        except ValueError:
            yield await emit_error(
                code="INVALID_RESPONSE",
                message="Claims Q&A returned invalid JSON",
            )
            return
        yield await emit_done(result=result)

    except httpx.TimeoutException:
        yield await emit_error(code="TIMEOUT", message="Claims Q&A request timed out")
    except httpx.RequestError as exc:
        yield await emit_error(code="CONNECTION_ERROR", message=str(exc))


@router.post("/qa")
async def generate_claims_answer(
    request: Request,
    payload: ClaimQaRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate Claims Q&A response via SSE streaming."""
    del current_user  # Auth validated

    correlation_id = request.headers.get("x-correlation-id")
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

    return sse_response(
        _stream_claims_qa(
            request=request,
            payload=payload.model_dump(),
            request_id=request_id,
            correlation_id=correlation_id,
        )
    )
