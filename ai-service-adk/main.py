"""AI Service ADK — standalone FastAPI application using Google ADK.

Parallel implementation to ai-service (CrewAI) for A/B testing.

Endpoints:
  /healthz                — ungated K8s probe (liveness + readiness)
  /ai/status              — Rate limit status + AI availability (AI allowlist)
  /ai/calendar/questions  — Calendar clarification/confirmation
  /ai/calendar/create     — Create calendar event
  /ai/gmail/questions     — Gmail agent quiz generation
  /ai/gmail/summary       — Gmail agent summarization
"""

import logging
from typing import Literal, Optional, List, Dict, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import require_ai_access
from config import settings
from rate_limiter import enforce_rate_limit, remaining_requests
from calendar_agent import CalendarAgentADK
from gmail_agent import GmailAgentADK

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

calendar_agent = CalendarAgentADK(
    api_key=settings.ANTHROPIC_API_KEY,
    backend_url=settings.BACKEND_URL,
)

gmail_agent = GmailAgentADK(api_key=settings.ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# Pydantic Models (matching ai-service/main.py)
# ---------------------------------------------------------------------------


class CalendarEventPayload(BaseModel):
    title: str
    start_datetime: str
    end_datetime: str
    timezone: str = "UTC"
    attendees: List[str] = []


class CalendarQuestionRequest(BaseModel):
    request: str
    previous_answers: List[str] = []


class CalendarQuestionResponse(BaseModel):
    status: Literal["clarify", "confirm"]
    question: str
    event: CalendarEventPayload


class CalendarCreateRequest(BaseModel):
    event: CalendarEventPayload


class CalendarCreateResponse(BaseModel):
    event_id: Optional[str] = None
    html_link: Optional[str] = None
    summary: Optional[str] = None


# Gmail Pydantic Models (matching ai-service/main.py)
class GmailSummaryRequest(BaseModel):
    emails: List[Dict[str, Any]]
    interest: str
    answers: List[str] = []


class GmailQuestionsRequest(BaseModel):
    emails: List[Dict[str, Any]]
    interest: str = ""
    previous_answers: List[str] = []
    question_count: int = 2


class GmailSummaryResponse(BaseModel):
    final_summary: str
    top_email_ids: List[str]
    reasoning: str


class GmailQuestionsResponse(BaseModel):
    questions: List[str]


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(title="AI Service ADK", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    """K8s probe endpoint."""
    return {"status": "ok", "service": "ai-service-adk"}


@app.get("/ai/status")
async def get_ai_status(username: str = Depends(require_ai_access)):
    """Check rate limit status and availability."""
    remaining = await remaining_requests(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    return {
        "available": True,
        "remaining_requests": remaining,
        "max_requests_per_hour": settings.AI_RATE_LIMIT_PER_HOUR,
    }


@app.post("/ai/calendar/questions", response_model=CalendarQuestionResponse)
async def generate_calendar_question(
    request: CalendarQuestionRequest,
    username: str = Depends(require_ai_access),
):
    """Generate calendar clarification or confirmation question."""
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    result = await calendar_agent.plan_event(
        request_text=request.request,
        previous_answers=request.previous_answers,
    )
    status = "clarify" if result.get("needs_clarification") else "confirm"
    event_payload = result.get("event") or {
        "title": "",
        "start_datetime": "",
        "end_datetime": "",
        "timezone": "UTC",
        "attendees": [],
    }
    return CalendarQuestionResponse(
        status=status,
        question=result.get("question", ""),
        event=event_payload,
    )


@app.post("/ai/calendar/create", response_model=CalendarCreateResponse)
async def create_calendar_event_endpoint(
    request: CalendarCreateRequest,
    http_request: Request,
    username: str = Depends(require_ai_access),
):
    """Create a calendar event after confirmation."""
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    auth_token = http_request.cookies.get("access_token")
    if not auth_token:
        raise HTTPException(status_code=400, detail="Missing session token")

    result = await calendar_agent.create_event(
        event=request.event.model_dump(),
        auth_token=auth_token,
    )
    return CalendarCreateResponse(
        event_id=result.get("event_id"),
        html_link=result.get("html_link"),
        summary=result.get("summary"),
    )


@app.post("/ai/gmail/questions", response_model=GmailQuestionsResponse)
async def generate_gmail_questions(
    request: GmailQuestionsRequest,
    username: str = Depends(require_ai_access),
):
    """Generate follow-up questions for Gmail agent."""
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    questions = await gmail_agent.generate_followup_questions(
        emails=request.emails,
        interest=request.interest,
        previous_answers=request.previous_answers,
        question_count=request.question_count,
    )

    return GmailQuestionsResponse(questions=questions)


@app.post("/ai/gmail/summary", response_model=GmailSummaryResponse)
async def generate_gmail_summary(
    request: GmailSummaryRequest,
    username: str = Depends(require_ai_access),
):
    """Generate prioritized Gmail summary."""
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    summaries = await gmail_agent.generate_summaries(
        emails=request.emails,
        interest=request.interest,
        answers=request.answers,
    )

    result = await gmail_agent.judge_and_rank(
        emails=request.emails,
        summary_a=summaries.get("summary_a", ""),
        summary_b=summaries.get("summary_b", ""),
        interest=request.interest,
        answers=request.answers,
    )

    return GmailSummaryResponse(
        final_summary=result.get("final_summary", ""),
        top_email_ids=result.get("top_email_ids", []),
        reasoning=result.get("reasoning", ""),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
