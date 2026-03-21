"""AI Service — standalone FastAPI application.

Extracted from the monolith's AI endpoints to run as an independent
microservice in the K3s strangler pattern architecture.

Endpoints:
  /healthz            — ungated K8s probe (liveness + readiness)
  /ai/status          — Rate limit status + AI availability (AI allowlist)
  /ai/local/status    — Local vLLM availability for Q&A local channel
  /ai/local/query     — Non-streaming local CrewAI query for Q&A local channel
  /ai/local/query/stream — SSE streaming local Q&A response for Q&A local channel
  /ai/gmail/questions — Gmail agent quiz generation
  /ai/gmail/summary   — Gmail agent summarization
  /ai/calendar/questions — Calendar clarification/confirmation
  /ai/calendar/create — Create calendar event
"""

import json
import logging
from typing import Literal, Optional, List, Dict, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth import require_ai_access, require_local_ai_access
from config import settings
from rate_limiter import enforce_rate_limit, remaining_requests
from ai_session_events import append_ai_session_event, new_request_id
from gmail_agent import GmailAgent
from calendar_agent import CalendarAgent
from local_qa_orchestrator import local_qa_orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

gmail_agent = GmailAgent(api_key=settings.ANTHROPIC_API_KEY)
calendar_agent = CalendarAgent(
    api_key=settings.ANTHROPIC_API_KEY,
    backend_url=settings.BACKEND_URL,
)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


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


class LocalAIMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class LocalAIQueryRequest(BaseModel):
    query: str = Field(default="", max_length=2000)
    mode: Literal["chat", "greeting"] = "chat"
    history: List[LocalAIMessage] = []


class LocalAIQueryResponse(BaseModel):
    status: Literal["ok", "rejected", "fallback"]
    message: str
    agent: str
    rejected: bool = False


app = FastAPI(title="AI Service", version="1.0.0")

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
    return {"status": "ok", "service": "ai-service"}


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


@app.get("/ai/local/status")
async def get_local_ai_status(username: str = Depends(require_local_ai_access)):
    """Check local vLLM + CrewAI availability for Q&A local channel."""
    if not settings.FEATURE_LOCAL_QA:
        raise HTTPException(status_code=404, detail="Not Found")

    max_requests = (
        settings.LOCAL_QA_RATE_LIMIT_PER_HOUR or settings.AI_RATE_LIMIT_PER_HOUR
    )
    remaining = await remaining_requests(
        user_id=f"local:{username}",
        max_requests=max_requests,
        window_seconds=3600,
    )
    online = await local_qa_orchestrator.is_local_ai_online()

    return {
        "enabled": True,
        "online": online,
        "available": online,
        "remaining_requests": remaining,
        "max_requests_per_hour": max_requests,
    }


@app.post("/ai/local/query", response_model=LocalAIQueryResponse)
async def query_local_ai(
    request: LocalAIQueryRequest,
    http_request: Request,
    username: str = Depends(require_local_ai_access),
):
    """Run local non-streaming CrewAI query for art/photography assistant."""
    if not settings.FEATURE_LOCAL_QA:
        raise HTTPException(status_code=404, detail="Not Found")

    max_requests = (
        settings.LOCAL_QA_RATE_LIMIT_PER_HOUR or settings.AI_RATE_LIMIT_PER_HOUR
    )
    await enforce_rate_limit(
        user_id=f"local:{username}",
        max_requests=max_requests,
        window_seconds=3600,
    )

    if request.mode == "greeting":
        message, agent = await local_qa_orchestrator.generate_greeting()
        status = (
            "fallback" if message == local_qa_orchestrator.fallback_message() else "ok"
        )
        resp = LocalAIQueryResponse(
            status=status, message=message, agent=agent, rejected=False
        )
        rid = http_request.headers.get("x-request-id") or new_request_id()
        await append_ai_session_event(
            kind="local_qa_greeting",
            username=username,
            source="ai_service",
            backend="local_vllm",
            correlation_id=http_request.headers.get("x-correlation-id"),
            request_id=rid,
            payload={
                "route": "/ai/local/query",
                "request": {"mode": request.mode},
                "response": {"status": resp.status, "agent": resp.agent},
            },
        )
        return resp

    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not local_qa_orchestrator.is_supported_topic(query_text):
        resp = LocalAIQueryResponse(
            status="rejected",
            message=(
                "I can only help with art and photography topics in Q&A local. "
                "Please ask about composition, lighting, camera settings, editing, or visual style."
            ),
            agent="Scope Guard",
            rejected=True,
        )
        rid = http_request.headers.get("x-request-id") or new_request_id()
        await append_ai_session_event(
            kind="local_qa_rejected",
            username=username,
            source="ai_service",
            backend="local_vllm",
            correlation_id=http_request.headers.get("x-correlation-id"),
            request_id=rid,
            payload={
                "route": "/ai/local/query",
                "request": {"mode": request.mode},
                "response": {"status": "rejected", "agent": "Scope Guard"},
            },
        )
        return resp

    history_payload = [
        {"role": item.role, "content": item.content}
        for item in request.history
        if item.content.strip()
    ]
    message, agent = await local_qa_orchestrator.answer_query(
        query_text, history_payload
    )
    status = "fallback" if message == local_qa_orchestrator.fallback_message() else "ok"
    resp = LocalAIQueryResponse(
        status=status, message=message, agent=agent, rejected=False
    )
    rid = http_request.headers.get("x-request-id") or new_request_id()
    await append_ai_session_event(
        kind="local_qa_answer",
        username=username,
        source="ai_service",
        backend="local_vllm",
        correlation_id=http_request.headers.get("x-correlation-id"),
        request_id=rid,
        payload={
            "route": "/ai/local/query",
            "request": {"mode": request.mode},
            "response": {"status": resp.status, "agent": resp.agent},
        },
    )
    return resp


@app.post("/ai/local/query/stream")
async def query_local_ai_stream(
    request: LocalAIQueryRequest,
    http_request: Request,
    username: str = Depends(require_local_ai_access),
):
    """Stream local Q&A response (SSE) for art/photography assistant."""
    if not settings.FEATURE_LOCAL_QA:
        raise HTTPException(status_code=404, detail="Not Found")

    if request.mode != "chat":
        raise HTTPException(
            status_code=400,
            detail="Streaming is only available for chat mode. Use /ai/local/query for greeting mode.",
        )

    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    max_requests = (
        settings.LOCAL_QA_RATE_LIMIT_PER_HOUR or settings.AI_RATE_LIMIT_PER_HOUR
    )
    await enforce_rate_limit(
        user_id=f"local:{username}",
        max_requests=max_requests,
        window_seconds=3600,
    )

    history_payload = [
        {"role": item.role, "content": item.content}
        for item in request.history
        if item.content.strip()
    ]

    async def event_generator():
        def sse(event: dict) -> str:
            return f"data: {json.dumps(event)}\n\n"

        assistant_agent = "Photography & Art Consultant"
        yield sse(
            {
                "type": "meta",
                "mode": "chat",
                "agent": assistant_agent,
                "disclaimer": (
                    "AI responses are for informational purposes only. "
                    "Always verify important decisions with qualified professionals."
                ),
            }
        )

        if not local_qa_orchestrator.is_supported_topic(query_text):
            yield sse(
                {
                    "type": "rejected",
                    "message": (
                        "I can only help with art and photography topics in Q&A local. "
                        "Please ask about composition, lighting, camera settings, editing, or visual style."
                    ),
                    "agent": "Scope Guard",
                }
            )
            yield sse({"type": "done", "mode": "chat"})
            return

        model_name = await local_qa_orchestrator.resolve_model_name()
        if not model_name:
            yield sse(
                {
                    "type": "fallback",
                    "message": local_qa_orchestrator.fallback_message(),
                    "agent": "System",
                }
            )
            yield sse({"type": "done", "mode": "chat"})
            return

        token_sent = False
        try:
            async for token in local_qa_orchestrator.stream_answer_query_tokens(
                query_text,
                history_payload,
                model_name=model_name,
            ):
                if await http_request.is_disconnected():
                    logger.info("Client disconnected from /ai/local/query/stream")
                    return
                token_sent = True
                yield sse({"type": "delta", "text": token, "agent": assistant_agent})
        except Exception:
            logger.exception("Local AI streaming failed for /ai/local/query/stream")
            if token_sent:
                yield sse(
                    {
                        "type": "error",
                        "message": "Local AI stream interrupted. Please retry.",
                    }
                )
            else:
                yield sse(
                    {
                        "type": "fallback",
                        "message": local_qa_orchestrator.fallback_message(),
                        "agent": "System",
                    }
                )
            yield sse({"type": "done", "mode": "chat"})
            return

        if not token_sent:
            yield sse({"type": "error", "message": "Local AI returned no content."})
        yield sse({"type": "done", "mode": "chat"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/ai/gmail/questions", response_model=GmailQuestionsResponse)
async def generate_gmail_questions(
    http_request: Request,
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

    resp = GmailQuestionsResponse(questions=questions)
    rid = http_request.headers.get("x-request-id") or new_request_id()
    await append_ai_session_event(
        kind="gmail_questions",
        username=username,
        source="ai_service",
        backend="crewai",
        correlation_id=http_request.headers.get("x-correlation-id"),
        request_id=rid,
        payload={
            "route": "/ai/gmail/questions",
            "request": {
                "interest": request.interest,
                "question_count": request.question_count,
                "previous_answers": request.previous_answers,
                "email_count": len(request.emails),
                "emails": [
                    {"id": e.get("id"), "subject": e.get("subject")}
                    for e in request.emails[:100]
                ],
            },
            "response": {"questions": resp.questions},
        },
    )
    return resp


@app.post("/ai/gmail/summary", response_model=GmailSummaryResponse)
async def generate_gmail_summary(
    http_request: Request,
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

    # Defensive check: ensure result is a dict
    if not isinstance(result, dict):
        result = {
            "final_summary": summaries.get("summary_a", "")
            + "\n\n"
            + summaries.get("summary_b", ""),
            "top_email_ids": [],
            "reasoning": "Fallback due to unexpected response format.",
        }

    resp = GmailSummaryResponse(
        final_summary=result.get("final_summary", ""),
        top_email_ids=result.get("top_email_ids", []),
        reasoning=result.get("reasoning", ""),
    )
    rid = http_request.headers.get("x-request-id") or new_request_id()
    await append_ai_session_event(
        kind="gmail_summary",
        username=username,
        source="ai_service",
        backend="crewai",
        correlation_id=http_request.headers.get("x-correlation-id"),
        request_id=rid,
        payload={
            "route": "/ai/gmail/summary",
            "request": {
                "interest": request.interest,
                "answers": request.answers,
                "email_count": len(request.emails),
                "emails": [
                    {"id": e.get("id"), "subject": e.get("subject")}
                    for e in request.emails[:100]
                ],
            },
            "response": {
                "final_summary": resp.final_summary,
                "top_email_ids": resp.top_email_ids,
                "reasoning": resp.reasoning,
            },
        },
    )
    return resp


@app.post("/ai/calendar/questions", response_model=CalendarQuestionResponse)
async def generate_calendar_question(
    request: CalendarQuestionRequest,
    http_request: Request,
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
    resp = CalendarQuestionResponse(
        status=status,
        question=result.get("question", ""),
        event=event_payload,
    )
    rid = http_request.headers.get("x-request-id") or new_request_id()
    await append_ai_session_event(
        kind="calendar_question",
        username=username,
        source="ai_service",
        backend="crewai",
        correlation_id=http_request.headers.get("x-correlation-id"),
        request_id=rid,
        payload={
            "route": "/ai/calendar/questions",
            "request": {
                "previous_answers": request.previous_answers,
            },
            "response": {"status": resp.status},
        },
    )
    return resp


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
    resp = CalendarCreateResponse(**result)
    rid = http_request.headers.get("x-request-id") or new_request_id()
    await append_ai_session_event(
        kind="calendar_create",
        username=username,
        source="ai_service",
        backend="crewai",
        correlation_id=http_request.headers.get("x-correlation-id"),
        request_id=rid,
        payload={
            "route": "/ai/calendar/create",
            "request": {
                "event_title": request.event.title,
                "start_datetime": request.event.start_datetime,
                "timezone": request.event.timezone,
            },
            "response": {
                "event_id": resp.event_id,
                "html_link": resp.html_link,
            },
        },
    )
    return resp
