"""AI Service ADK — standalone FastAPI application using Google ADK.

Parallel implementation to ai-service (CrewAI) for A/B testing.

Endpoints:
  /healthz                — ungated K8s probe (liveness + readiness)
  /ai/status              — Rate limit status + AI availability (AI allowlist)
  /ai/calendar/questions  — Calendar clarification/confirmation
  /ai/calendar/create     — Create calendar event
  /ai/gmail/questions     — Gmail agent quiz generation
  /ai/gmail/summary       — Gmail agent summarization
  /ai/claims/qa           — Claims Q&A with judge
"""

import logging
import time
import uuid as _uuid
from typing import Annotated, Literal, Optional, List, Dict, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auth import require_ai_access
from config import settings
from rate_limiter import enforce_rate_limit, remaining_requests
from ai_session_events import append_ai_session_event, new_request_id, _client as _redis_log_client
from calendar_agent import CalendarAgentADK
from gmail_agent import GmailAgentADK
from claims_agent import (
    ClaimsAgentADK,
    build_tool_calls,
    is_followup_question_valid,
)
from claims_persistence import persist_completed_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

calendar_agent = CalendarAgentADK(
    api_key=settings.ANTHROPIC_API_KEY,
    backend_url=settings.BACKEND_URL,
)

gmail_agent = GmailAgentADK(api_key=settings.ANTHROPIC_API_KEY)
claims_agent = ClaimsAgentADK(api_key=settings.ANTHROPIC_API_KEY)


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
MAX_GMAIL_EMAILS = 10


class GmailSummaryRequest(BaseModel):
    emails: Annotated[List[Dict[str, Any]], Field(max_length=MAX_GMAIL_EMAILS)]
    interest: str
    answers: List[str] = []


class GmailQuestionsRequest(BaseModel):
    emails: Annotated[List[Dict[str, Any]], Field(max_length=MAX_GMAIL_EMAILS)]
    interest: str = ""
    previous_answers: List[str] = []
    question_count: int = 2


class GmailSummaryResponse(BaseModel):
    final_summary: str
    top_email_ids: List[str]
    reasoning: str


class GmailQuestionsResponse(BaseModel):
    questions: List[str]


class ClaimQaHistoryEntry(BaseModel):
    question: str
    answer: str


class ClaimQaRequest(BaseModel):
    claim: Dict[str, Any]
    question: str
    history: List[ClaimQaHistoryEntry] = []
    question_count: int = Field(0, ge=0, le=5)
    asked_questions: List[str] = []
    tool_history: List[Dict[str, Any]] = []
    session_id: Optional[str] = None


class ClaimQaResponse(BaseModel):
    answer: str
    reasoning: str
    done: bool = False
    next_question: Optional[str] = None
    followup_reasoning: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_history: Optional[List[Dict[str, Any]]] = None
    flags: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


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
    resp = CalendarCreateResponse(
        event_id=result.get("event_id"),
        html_link=result.get("html_link"),
        summary=result.get("summary"),
    )
    rid = http_request.headers.get("x-request-id") or new_request_id()
    await append_ai_session_event(
        kind="calendar_create",
        username=username,
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

    resp = GmailSummaryResponse(
        final_summary=result.get("final_summary", ""),
        top_email_ids=result.get("top_email_ids", []),
        reasoning=result.get("reasoning", ""),
    )
    rid = http_request.headers.get("x-request-id") or new_request_id()
    await append_ai_session_event(
        kind="gmail_summary",
        username=username,
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


@app.post("/ai/claims/qa", response_model=ClaimQaResponse)
async def generate_claims_answer(
    request: ClaimQaRequest,
    http_request: Request,
    username: str = Depends(require_ai_access),
):
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    rid = http_request.headers.get("x-request-id") or new_request_id()
    correlation_id = http_request.headers.get("x-correlation-id")

    # Generate or reuse session_id for multi-turn correlation.
    # Validate client-supplied value; fall back to new UUID on bad input.
    _incoming_sid = (request.session_id or "").strip()
    if _incoming_sid:
        try:
            _uuid.UUID(_incoming_sid)
            session_id = _incoming_sid
        except ValueError:
            session_id = _uuid.uuid4().hex
    else:
        session_id = _uuid.uuid4().hex

    tool_history = list(request.tool_history or [])
    response_tool_calls: List[Dict[str, Any]] = []

    start = time.perf_counter()
    tool_output = claims_agent.truth_check(request.claim)
    tool_elapsed_ms = int((time.perf_counter() - start) * 1000)

    truth_tool_calls = [
        {"name": "truth_check", "result": tool_output, "stage": "truth_check"}
    ]
    tool_history.extend(truth_tool_calls)
    response_tool_calls.extend(truth_tool_calls)

    # Dedicated log per tool invocation
    await append_ai_session_event(
        kind="tool_invoked",
        username=username,
        correlation_id=correlation_id,
        request_id=rid,
        session_id=session_id,
        payload={
            "route": "/ai/claims/qa",
            "tool_name": "truth_check",
            "stage": "truth_check",
            "result_summary": {
                "status": tool_output.get("status"),
                "status_ok": tool_output.get("status_ok"),
                "summary_ok": tool_output.get("summary_ok"),
                "timeline_ok": tool_output.get("timeline_ok"),
                "issue_count": len(tool_output.get("issues", [])),
            },
            "inference_time_ms": tool_elapsed_ms,
        },
    )

    await append_ai_session_event(
        kind="claims_truth_check",
        username=username,
        correlation_id=correlation_id,
        request_id=rid,
        session_id=session_id,
        payload={
            "route": "/ai/claims/qa",
            "step": "truth_check",
            "request": {
                "question": request.question,
                "question_count": request.question_count,
                "history": [entry.model_dump() for entry in request.history],
                "asked_questions": request.asked_questions,
                "claim": request.claim,
            },
            "response": tool_output,
            "tool_calls": truth_tool_calls,
            "findings": {
                "status": tool_output.get("status"),
                "status_ok": tool_output.get("status_ok"),
                "summary_ok": tool_output.get("summary_ok"),
                "timeline_ok": tool_output.get("timeline_ok"),
                "issue_count": len(tool_output.get("issues", [])),
            },
            "token_cost": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated": False,
            },
            "inference_time_ms": tool_elapsed_ms,
        },
    )

    candidate_a_tools = build_tool_calls(
        request.claim,
        ["status_check", "timeline_check", "notes_summary"],
        stage="candidate_a",
    )
    tool_history.extend(candidate_a_tools)
    response_tool_calls.extend(candidate_a_tools)

    # Dedicated log per tool invocation — candidate_a stage
    for _tc in candidate_a_tools:
        await append_ai_session_event(
            kind="tool_invoked",
            username=username,
            correlation_id=correlation_id,
            request_id=rid,
            session_id=session_id,
            payload={
                "route": "/ai/claims/qa",
                "tool_name": _tc["name"],
                "stage": "candidate_a",
                "result_summary": _tc.get("result"),
            },
        )

    answer_a, metrics_a = await claims_agent.generate_candidate_answer(
        payload=request.claim,
        question=request.question,
        history=[entry.model_dump() for entry in request.history],
        tool_output=tool_output,
        tool_calls=candidate_a_tools,
        tool_history=tool_history,
        variant="A",
    )

    await append_ai_session_event(
        kind="claims_candidate",
        username=username,
        correlation_id=correlation_id,
        request_id=rid,
        session_id=session_id,
        payload={
            "route": "/ai/claims/qa",
            "step": "candidate_a",
            "request": {"question": request.question},
            "response": {"answer": answer_a},
            "tool_calls": candidate_a_tools,
            "findings": {"answer": answer_a},
            **metrics_a,
        },
    )

    candidate_b_tools = build_tool_calls(
        request.claim,
        ["coverage_snapshot", "documents_summary", "financials_summary"],
        stage="candidate_b",
    )
    tool_history.extend(candidate_b_tools)
    response_tool_calls.extend(candidate_b_tools)

    # Dedicated log per tool invocation — candidate_b stage
    for _tc in candidate_b_tools:
        await append_ai_session_event(
            kind="tool_invoked",
            username=username,
            correlation_id=correlation_id,
            request_id=rid,
            session_id=session_id,
            payload={
                "route": "/ai/claims/qa",
                "tool_name": _tc["name"],
                "stage": "candidate_b",
                "result_summary": _tc.get("result"),
            },
        )

    answer_b, metrics_b = await claims_agent.generate_candidate_answer(
        payload=request.claim,
        question=request.question,
        history=[entry.model_dump() for entry in request.history],
        tool_output=tool_output,
        tool_calls=candidate_b_tools,
        tool_history=tool_history,
        variant="B",
    )

    await append_ai_session_event(
        kind="claims_candidate",
        username=username,
        correlation_id=correlation_id,
        request_id=rid,
        session_id=session_id,
        payload={
            "route": "/ai/claims/qa",
            "step": "candidate_b",
            "request": {"question": request.question},
            "response": {"answer": answer_b},
            "tool_calls": candidate_b_tools,
            "findings": {"answer": answer_b},
            **metrics_b,
        },
    )

    judge_tools = build_tool_calls(
        request.claim,
        ["status_check", "coverage_snapshot", "financials_summary"],
        stage="judge",
    )
    tool_history.extend(judge_tools)
    response_tool_calls.extend(judge_tools)

    # Dedicated log per tool invocation — judge stage
    for _tc in judge_tools:
        await append_ai_session_event(
            kind="tool_invoked",
            username=username,
            correlation_id=correlation_id,
            request_id=rid,
            session_id=session_id,
            payload={
                "route": "/ai/claims/qa",
                "tool_name": _tc["name"],
                "stage": "judge",
                "result_summary": _tc.get("result"),
            },
        )

    judge_result, judge_metrics = await claims_agent.judge_answers(
        question=request.question,
        tool_output=tool_output,
        tool_calls=judge_tools,
        tool_history=tool_history,
        answer_a=answer_a,
        answer_b=answer_b,
    )

    await append_ai_session_event(
        kind="claims_judge",
        username=username,
        correlation_id=correlation_id,
        request_id=rid,
        session_id=session_id,
        payload={
            "route": "/ai/claims/qa",
            "step": "judge",
            "request": {"question": request.question},
            "response": judge_result,
            "tool_calls": judge_tools,
            "findings": {
                "winner": judge_result.get("winner")
                if isinstance(judge_result, dict)
                else None,
                "done": judge_result.get("done")
                if isinstance(judge_result, dict)
                else None,
                "reasoning": judge_result.get("reasoning")
                if isinstance(judge_result, dict)
                else None,
            },
            **judge_metrics,
        },
    )

    winner = judge_result.get("winner") if isinstance(judge_result, dict) else 1
    reasoning = ""
    done = False
    if isinstance(judge_result, dict):
        reasoning = str(judge_result.get("reasoning") or "").strip()
        done = bool(judge_result.get("done"))
    if winner == 2:
        final_answer = answer_b
    else:
        final_answer = answer_a

    next_question = None
    followup_reasoning = None
    followup_elapsed_ms = 0
    if not done and request.question_count < 5:
        followup_start = time.perf_counter()
        history_payload = [entry.model_dump() for entry in request.history]
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            followup_tools_a = build_tool_calls(
                request.claim,
                ["status_check", "timeline_check"],
                stage="followup_candidate_a",
                attempt=attempt,
            )
            tool_history.extend(followup_tools_a)
            response_tool_calls.extend(followup_tools_a)

            # Dedicated log per tool invocation — followup_candidate_a
            for _tc in followup_tools_a:
                await append_ai_session_event(
                    kind="tool_invoked",
                    username=username,
                    correlation_id=correlation_id,
                    request_id=rid,
                    session_id=session_id,
                    payload={
                        "route": "/ai/claims/qa",
                        "tool_name": _tc["name"],
                        "stage": "followup_candidate_a",
                        "attempt": attempt,
                        "result_summary": _tc.get("result"),
                    },
                )

            (
                followup_a,
                followup_metrics_a,
                followup_raw_a,
            ) = await claims_agent.generate_followup_candidate(
                payload=request.claim,
                question=request.question,
                history=history_payload,
                asked_questions=request.asked_questions,
                tool_output=tool_output,
                tool_calls=followup_tools_a,
                tool_history=tool_history,
                attempt=attempt,
                max_attempts=max_attempts,
                variant="A",
            )

            await append_ai_session_event(
                kind="claims_followup_candidate",
                username=username,
                correlation_id=correlation_id,
                request_id=rid,
                session_id=session_id,
                payload={
                    "route": "/ai/claims/qa",
                    "step": "followup_candidate_a",
                    "attempt": attempt,
                    "request": {"question": request.question},
                    "response": {"question": followup_a, "raw": followup_raw_a},
                    "tool_calls": followup_tools_a,
                    "findings": {"question": followup_a},
                    **followup_metrics_a,
                },
            )

            followup_tools_b = build_tool_calls(
                request.claim,
                ["documents_summary", "coverage_snapshot"],
                stage="followup_candidate_b",
                attempt=attempt,
            )
            tool_history.extend(followup_tools_b)
            response_tool_calls.extend(followup_tools_b)

            # Dedicated log per tool invocation — followup_candidate_b
            for _tc in followup_tools_b:
                await append_ai_session_event(
                    kind="tool_invoked",
                    username=username,
                    correlation_id=correlation_id,
                    request_id=rid,
                    session_id=session_id,
                    payload={
                        "route": "/ai/claims/qa",
                        "tool_name": _tc["name"],
                        "stage": "followup_candidate_b",
                        "attempt": attempt,
                        "result_summary": _tc.get("result"),
                    },
                )

            (
                followup_b,
                followup_metrics_b,
                followup_raw_b,
            ) = await claims_agent.generate_followup_candidate(
                payload=request.claim,
                question=request.question,
                history=history_payload,
                asked_questions=request.asked_questions,
                tool_output=tool_output,
                tool_calls=followup_tools_b,
                tool_history=tool_history,
                attempt=attempt,
                max_attempts=max_attempts,
                variant="B",
            )

            await append_ai_session_event(
                kind="claims_followup_candidate",
                username=username,
                correlation_id=correlation_id,
                request_id=rid,
                session_id=session_id,
                payload={
                    "route": "/ai/claims/qa",
                    "step": "followup_candidate_b",
                    "attempt": attempt,
                    "request": {"question": request.question},
                    "response": {"question": followup_b, "raw": followup_raw_b},
                    "tool_calls": followup_tools_b,
                    "findings": {"question": followup_b},
                    **followup_metrics_b,
                },
            )

            followup_judge_tools = build_tool_calls(
                request.claim,
                ["status_check", "financials_summary"],
                stage="followup_judge",
                attempt=attempt,
            )
            tool_history.extend(followup_judge_tools)
            response_tool_calls.extend(followup_judge_tools)

            # Dedicated log per tool invocation — followup_judge
            for _tc in followup_judge_tools:
                await append_ai_session_event(
                    kind="tool_invoked",
                    username=username,
                    correlation_id=correlation_id,
                    request_id=rid,
                    session_id=session_id,
                    payload={
                        "route": "/ai/claims/qa",
                        "tool_name": _tc["name"],
                        "stage": "followup_judge",
                        "attempt": attempt,
                        "result_summary": _tc.get("result"),
                    },
                )

            (
                followup_judge_result,
                followup_judge_metrics,
            ) = await claims_agent.judge_followup_question(
                question=request.question,
                history=history_payload,
                asked_questions=request.asked_questions,
                tool_output=tool_output,
                tool_calls=followup_judge_tools,
                tool_history=tool_history,
                attempt=attempt,
                candidate_a=followup_a,
                candidate_b=followup_b,
            )

            await append_ai_session_event(
                kind="claims_followup_judge",
                username=username,
                correlation_id=correlation_id,
                request_id=rid,
                session_id=session_id,
                payload={
                    "route": "/ai/claims/qa",
                    "step": "followup_judge",
                    "attempt": attempt,
                    "request": {"question": request.question},
                    "response": followup_judge_result,
                    "tool_calls": followup_judge_tools,
                    "findings": {
                        "winner": followup_judge_result.get("winner")
                        if isinstance(followup_judge_result, dict)
                        else None,
                        "reasoning": followup_judge_result.get("reasoning")
                        if isinstance(followup_judge_result, dict)
                        else None,
                        "question": followup_judge_result.get("question")
                        if isinstance(followup_judge_result, dict)
                        else None,
                    },
                    **followup_judge_metrics,
                },
            )

            attempt_reasoning = None
            candidate_question = None
            winner = None
            if isinstance(followup_judge_result, dict):
                chosen = followup_judge_result.get("question")
                candidate_question = (
                    chosen if isinstance(chosen, str) and chosen.strip() else None
                )
                attempt_reasoning = (
                    str(followup_judge_result.get("reasoning") or "").strip()
                    if followup_judge_result.get("reasoning")
                    else None
                )
                winner = followup_judge_result.get("winner")

            if not candidate_question:
                if winner == 2:
                    candidate_question = followup_b or followup_a
                else:
                    candidate_question = followup_a or followup_b

            if candidate_question and is_followup_question_valid(
                candidate_question,
                history_payload,
                request.asked_questions,
                tool_history,
            ):
                next_question = candidate_question
                followup_reasoning = attempt_reasoning
                break

            if attempt == max_attempts and candidate_question:
                next_question = candidate_question
                followup_reasoning = attempt_reasoning

        followup_elapsed_ms = int((time.perf_counter() - followup_start) * 1000)

    await append_ai_session_event(
        kind="claims_followup",
        username=username,
        correlation_id=correlation_id,
        request_id=rid,
        session_id=session_id,
        payload={
            "route": "/ai/claims/qa",
            "step": "followup",
            "request": {"question": request.question},
            "response": {
                "next_question": next_question,
                "done": done,
                "followup_reasoning": followup_reasoning,
            },
            "findings": {
                "next_question": next_question,
                "done": done,
                "followup_reasoning": followup_reasoning,
            },
            "token_cost": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated": False,
            },
            "inference_time_ms": followup_elapsed_ms,
        },
    )

    # Persist completed session to Postgres (fire-and-forget)
    if done:
        all_turns: list[dict[str, Any]] = []
        for h in request.history:
            all_turns.append(
                {"question": h.question, "answer": h.answer, "done": False}
            )
        all_turns.append(
            {
                "question": request.question,
                "answer": final_answer,
                "reasoning": reasoning,
                "tool_calls": response_tool_calls,
                "done": True,
                "next_question": next_question,
            }
        )
        claim_id = ""
        if isinstance(request.claim, dict):
            claim_id = request.claim.get("claim_id", "")
        claim_status = ""
        if isinstance(tool_output, dict):
            claim_status = str(tool_output.get("status", ""))

        try:
            await persist_completed_session(
                session_id=session_id,
                claim_id=claim_id,
                username=username,
                status=claim_status,
                flags=tool_output,
                turns=all_turns,
                redis_client=_redis_log_client(),
                stream_key=settings.AI_SESSION_STREAM_KEY,
            )
        except Exception:
            logger.warning("Claims persistence failed (session=%s)", session_id, exc_info=True)

    return ClaimQaResponse(
        answer=final_answer,
        reasoning=reasoning,
        done=done,
        next_question=next_question,
        followup_reasoning=followup_reasoning,
        tool_calls=response_tool_calls,
        tool_history=tool_history,
        flags=tool_output,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
