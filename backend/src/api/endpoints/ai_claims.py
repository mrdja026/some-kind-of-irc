import uuid
from typing import Any, List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.endpoints.auth import get_current_user
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


class ClaimQaResponse(BaseModel):
    answer: str
    reasoning: str
    done: bool = False
    next_question: Optional[str] = None
    followup_reasoning: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    tool_history: Optional[List[dict]] = None
    flags: Optional[dict] = None


@router.post("/qa", response_model=ClaimQaResponse)
def generate_claims_answer(
    request: Request,
    payload: ClaimQaRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    adk_url = settings.AI_SERVICE_ADK_URL.rstrip("/")
    correlation_id = request.headers.get("x-correlation-id")
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

    headers = {"x-request-id": request_id}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id

    try:
        response = requests.post(
            f"{adk_url}/ai/claims/qa",
            json=payload.model_dump(),
            cookies=request.cookies,
            headers=headers,
            timeout=30,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="AI service unavailable")

    if not response.ok:
        detail = "Claims Q&A failed"
        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except ValueError:
            if response.text:
                detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid AI response")
