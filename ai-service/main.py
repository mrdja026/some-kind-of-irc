"""AI Service — standalone FastAPI application.

Extracted from the monolith's AI endpoints to run as an independent
microservice in the K3s strangler pattern architecture.

Endpoints:
  /healthz            — ungated K8s probe (liveness + readiness)
  /ai/query           — AI query with intent routing (AI allowlist)
  /ai/query/stream    — SSE streaming AI response (AI allowlist)
  /ai/status          — Rate limit status + AI availability (AI allowlist)
"""

import json
import logging
import re
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth import require_ai_access
from config import settings
from orchestrator import orchestrator
from rate_limiter import enforce_rate_limit, remaining_requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FALLBACK_QUESTIONS = [
    "What is your target budget and hard spending limit for this decision?",
    "What is the most important outcome for you here?",
    "What timeline are you working with?",
]

MANDATORY_GUARDRAIL_QUESTION = "Do you have a 6-month emergency fund?"
CLARIFICATION_MAX_ROUNDS = 4


def _debug_log(message: str, *args):
    if settings.AI_DEBUG_LOG:
        logger.info("[ai-debug] " + message, *args)


def _extract_runway_months(text: str) -> Optional[float]:
    years = re.findall(r"(\d+(?:\.\d+)?)\s*(?:year|years|yr|yrs)\b", text)
    months = re.findall(r"(\d+(?:\.\d+)?)\s*(?:month|months|mo)\b", text)
    values: list[float] = []
    for item in years:
        try:
            values.append(float(item) * 12.0)
        except ValueError:
            continue
    for item in months:
        try:
            values.append(float(item))
        except ValueError:
            continue
    return max(values) if values else None


def _extract_fraction_ratio(text: str) -> Optional[float]:
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    ratios: list[float] = []
    for left, right in matches:
        try:
            denominator = float(right)
            if denominator <= 0:
                continue
            ratios.append(float(left) / denominator)
        except ValueError:
            continue
    return min(ratios) if ratios else None


def _build_smart_guardrail_question(original_query: str, answers: list[str]) -> tuple[str, str]:
    """Build a contextual 4th guardrail question for affordability intent."""
    combined = f"{original_query}\n" + "\n".join(answers)
    lower = combined.lower()
    runway_months = _extract_runway_months(lower)
    ratio = _extract_fraction_ratio(lower)
    no_income = any(token in lower for token in ["no income", "career break", "unemployed", "between jobs"])

    if no_income and runway_months is not None and runway_months >= 24 and ratio is not None and ratio <= 0.05:
        return (
            "You mentioned strong runway and low purchase impact; what minimum emergency buffer (in months) do you want to keep untouched after buying this?",
            "Soft guardrail: user appears resilient, so ask for explicit personal buffer target.",
        )

    if no_income and (runway_months is None or runway_months < 12):
        return (
            "Before buying this, do you still have at least 6 months of essential expenses in emergency savings after the purchase?",
            "Hard guardrail: low/unclear runway with no income requires stricter safety check.",
        )

    if runway_months is not None and runway_months >= 12:
        return (
            "After this purchase, how many months of essential expenses will remain in your emergency fund?",
            "Contextual guardrail: confirm remaining safety runway in months.",
        )

    return (
        MANDATORY_GUARDRAIL_QUESTION,
        "Default guardrail: emergency fund coverage check.",
    )

app = FastAPI(title="AI Service", version="1.0.0")

# CORS — allow monolith origins for browser-based requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health probe — ungated
# ---------------------------------------------------------------------------

@app.get("/healthz")
async def healthz(request: Request):
    """Kubernetes liveness/readiness probe (no auth required)."""
    logger.info("healthz ok from %s", request.client.host if request.client else "unknown")
    return {"service": "ai-service", "status": "ok"}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ClarificationState(BaseModel):
    original_query: str
    questions: list[str]
    answers: list[str] = Field(default_factory=list)
    fallback_flags: list[bool] = Field(default_factory=list)
    max_rounds: int = CLARIFICATION_MAX_ROUNDS

    model_config = {"extra": "forbid"}


class AIQueryRequest(BaseModel):
    intent: Literal["afford", "learn"]
    query: str
    media_urls: Optional[list[str]] = None
    conversation_stage: Literal["initial", "clarification"] = "initial"
    clarification_state: Optional[ClarificationState] = None

    model_config = {"extra": "forbid"}


class AIQueryResponse(BaseModel):
    mode: Literal["clarify", "final"]
    intent: str
    query: str
    question: Optional[str] = None
    questions: Optional[list[str]] = None
    candidate_questions: Optional[list[str]] = None
    other_suggested_questions: Optional[list[str]] = None
    agent_candidates: Optional[dict[str, list[str]]] = None
    agent_reasoning: Optional[dict[str, str]] = None
    judge_reasoning: Optional[str] = None
    chosen_from_agent: Optional[str] = None
    current_round: Optional[int] = None
    total_rounds: Optional[int] = None
    is_fallback_question: Optional[bool] = None
    clarification_state: Optional[ClarificationState] = None
    response: Optional[str] = None
    agent: str
    disclaimer: str = (
        "AI responses are for informational purposes only. "
        "Always verify important decisions with qualified professionals."
    )


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def _validate_query(request: AIQueryRequest):
    if request.media_urls:
        raise HTTPException(
            status_code=400,
            detail="Media inputs are not supported for AI queries.",
        )

    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if request.conversation_stage == "initial" and len(query_text) < 10:
        raise HTTPException(
            status_code=400,
            detail="Query too short. Please provide more details.",
        )

    if len(request.query) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Query too long. Please keep it under 1000 characters.",
        )

    if request.conversation_stage == "clarification":
        if request.clarification_state is None:
            raise HTTPException(
                status_code=400,
                detail="clarification_state is required during clarification stage.",
            )
        if not request.clarification_state.questions:
            raise HTTPException(
                status_code=400,
                detail="clarification_state.questions cannot be empty.",
            )
        if request.clarification_state.max_rounds < 1 or request.clarification_state.max_rounds > CLARIFICATION_MAX_ROUNDS:
            raise HTTPException(
                status_code=400,
                detail=f"clarification_state.max_rounds must be between 1 and {CLARIFICATION_MAX_ROUNDS}.",
            )


def _next_fallback_question(asked_questions: list[str]) -> Optional[str]:
    asked = {q.strip().lower() for q in asked_questions if q.strip()}
    for question in FALLBACK_QUESTIONS:
        if question.lower() not in asked:
            return question
    return None


async def _select_next_clarification_question(
    intent: str,
    original_query: str,
    asked_questions: list[str],
    answers: list[str],
) -> tuple[Optional[str], bool, list[str], str, str, dict[str, list[str]], dict[str, str]]:
    asked_norm = {q.strip().lower() for q in asked_questions if q.strip()}

    # Smart guardrail for affordability: always ask a contextual 4th safety question.
    if (
        intent == "afford"
        and len(answers) == CLARIFICATION_MAX_ROUNDS - 1
        and MANDATORY_GUARDRAIL_QUESTION.lower() not in asked_norm
    ):
        guardrail_question, guardrail_reason = _build_smart_guardrail_question(original_query, answers)
        _debug_log("guardrail question selected: %s", guardrail_question)
        return (
            guardrail_question,
            False,
            [],
            guardrail_reason,
            "Guardrail",
            {"Guardrail": [guardrail_question]},
            {"Guardrail": guardrail_reason},
        )

    panel = await orchestrator.generate_clarification_panel(
        intent=intent,
        user_original_query=original_query,
        asked_questions=asked_questions,
        answers=answers,
        max_questions=3,
    )

    chosen_question_raw = panel.get("chosen_question")
    chosen_question = chosen_question_raw if isinstance(chosen_question_raw, str) else ""
    chosen_question = chosen_question.strip()
    if len(answers) < CLARIFICATION_MAX_ROUNDS - 1 and chosen_question.lower() == MANDATORY_GUARDRAIL_QUESTION.lower():
        chosen_question = ""
    if chosen_question:
        panel_others_raw = panel.get("other_suggested_questions")
        panel_others: list[str] = [
            item
            for item in panel_others_raw
            if isinstance(item, str)
            and item.strip().lower() != MANDATORY_GUARDRAIL_QUESTION.lower()
        ] if isinstance(panel_others_raw, list) else []
        panel_reasoning_raw = panel.get("judge_reasoning")
        panel_reasoning = panel_reasoning_raw.strip() if isinstance(panel_reasoning_raw, str) else ""
        panel_chosen_raw = panel.get("chosen_from_agent")
        panel_chosen = panel_chosen_raw if isinstance(panel_chosen_raw, str) else "JudgeBot"
        panel_agents_raw = panel.get("agent_candidates")
        panel_agents: dict[str, list[str]] = {}
        if isinstance(panel_agents_raw, dict):
            for key, value in panel_agents_raw.items():
                if isinstance(key, str) and isinstance(value, list):
                    panel_agents[key] = [item for item in value if isinstance(item, str)]
        panel_reasoning_raw_map = panel.get("agent_reasoning")
        panel_agent_reasoning: dict[str, str] = {}
        if isinstance(panel_reasoning_raw_map, dict):
            for key, value in panel_reasoning_raw_map.items():
                if isinstance(key, str) and isinstance(value, str):
                    panel_agent_reasoning[key] = value.strip()

        return (
            chosen_question,
            False,
            panel_others,
            panel_reasoning,
            panel_chosen,
            panel_agents,
            panel_agent_reasoning,
        )

    fallback = _next_fallback_question(asked_questions)
    if fallback:
        fallback_candidates = []
        for question in FALLBACK_QUESTIONS:
            question_norm = question.lower()
            if question_norm in asked_norm or question == fallback:
                continue
            fallback_candidates.append(question)
            if len(fallback_candidates) >= 3:
                break
        return (
            fallback,
            True,
            fallback_candidates,
            "Fallback question selected because judge panel did not return a valid candidate.",
            "Fallback",
            {"Fallback": [fallback, *fallback_candidates]},
            {"Fallback": "Fallback path used because specialists/judge returned no valid next question."},
        )

    return None, False, [], "", "JudgeBot", {}, {}


# ---------------------------------------------------------------------------
# AI endpoints — allowlist-gated
# ---------------------------------------------------------------------------

@app.post("/ai/query", response_model=AIQueryResponse)
async def query_ai_agents(
    request: AIQueryRequest,
    username: str = Depends(require_ai_access),
):
    """Query the AI agents with a specific intent (allowlist users only).

    Intents:
    - afford: Financial affordability analysis
    - learn: Learning material recommendations
    """
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    _debug_log(
        "query start user=%s stage=%s intent=%s has_state=%s",
        username,
        request.conversation_stage,
        request.intent,
        request.clarification_state is not None,
    )

    _validate_query(request)

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Please contact administrator.",
        )

    try:
        if request.conversation_stage == "initial":
            (
                next_question,
                is_fallback,
                other_suggested_questions,
                judge_reasoning,
                chosen_from_agent,
                agent_candidates,
                agent_reasoning,
            ) = await _select_next_clarification_question(
                request.intent,
                request.query,
                asked_questions=[],
                answers=[],
            )
            if not next_question:
                next_question = FALLBACK_QUESTIONS[0]
                is_fallback = True
                other_suggested_questions = []
                judge_reasoning = "Fallback question selected because no valid panel output was available."
                chosen_from_agent = "Fallback"
                agent_candidates = {"Fallback": [next_question]}
                agent_reasoning = {"Fallback": "Fallback path used because panel returned no valid next question."}

            _debug_log(
                "query clarify round=%s/%s chosen=%s source=%s fallback=%s",
                1,
                CLARIFICATION_MAX_ROUNDS,
                next_question,
                chosen_from_agent,
                is_fallback,
            )

            state = ClarificationState(
                original_query=request.query,
                questions=[next_question],
                answers=[],
                fallback_flags=[is_fallback],
                max_rounds=CLARIFICATION_MAX_ROUNDS,
            )
            return AIQueryResponse(
                mode="clarify",
                intent=request.intent,
                query=request.query,
                question=next_question,
                questions=state.questions,
                candidate_questions=other_suggested_questions,
                other_suggested_questions=other_suggested_questions,
                judge_reasoning=judge_reasoning,
                chosen_from_agent=chosen_from_agent,
                agent_candidates=agent_candidates,
                agent_reasoning=agent_reasoning,
                current_round=1,
                total_rounds=state.max_rounds,
                is_fallback_question=is_fallback,
                clarification_state=state,
                agent="JudgeBot",
            )

        assert request.clarification_state is not None
        state = request.clarification_state
        fallback_flags = (state.fallback_flags + [False] * len(state.questions))[: len(state.questions)]
        answers = [answer for answer in state.answers if answer.strip()]
        answers.append(request.query.strip())

        if len(answers) < state.max_rounds:
            (
                next_question,
                is_fallback,
                other_suggested_questions,
                judge_reasoning,
                chosen_from_agent,
                agent_candidates,
                agent_reasoning,
            ) = await _select_next_clarification_question(
                request.intent,
                state.original_query,
                asked_questions=state.questions,
                answers=answers,
            )

            if next_question:
                updated_questions = [*state.questions, next_question]
                updated_flags = [*fallback_flags, is_fallback]
            else:
                updated_questions = state.questions
                updated_flags = fallback_flags

            if next_question:
                updated_state = ClarificationState(
                    original_query=state.original_query,
                    questions=updated_questions,
                    answers=answers,
                    fallback_flags=updated_flags,
                    max_rounds=state.max_rounds,
                )
                return AIQueryResponse(
                    mode="clarify",
                    intent=request.intent,
                    query=request.query,
                    question=next_question,
                    questions=updated_state.questions,
                    candidate_questions=other_suggested_questions,
                    other_suggested_questions=other_suggested_questions,
                    judge_reasoning=judge_reasoning,
                    chosen_from_agent=chosen_from_agent,
                    agent_candidates=agent_candidates,
                    agent_reasoning=agent_reasoning,
                    current_round=len(answers) + 1,
                    total_rounds=updated_state.max_rounds,
                    is_fallback_question=is_fallback,
                    clarification_state=updated_state,
                    agent="JudgeBot",
                )

        questions_for_final = state.questions[: len(answers)]
        if not questions_for_final:
            questions_for_final = FALLBACK_QUESTIONS[: min(3, len(answers))]

        result = await orchestrator.process_query_with_clarifications(
            request.intent,
            state.original_query,
            questions_for_final,
            answers,
        )
        _debug_log("query final round_count=%s intent=%s", len(answers), request.intent)
        return AIQueryResponse(mode="final", **result)
    except Exception as e:
        logger.error(f"AI processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


@app.post("/ai/query/stream")
async def query_ai_agents_stream(
    request: AIQueryRequest,
    username: str = Depends(require_ai_access),
):
    """Stream clarify or final AI responses via Server-Sent Events."""
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    _validate_query(request)

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Please contact administrator.",
        )

    async def event_stream():
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        _debug_log(
            "stream start user=%s stage=%s intent=%s has_state=%s",
            username,
            request.conversation_stage,
            request.intent,
            request.clarification_state is not None,
        )

        meta = {
            "type": "meta",
            "intent": request.intent,
            "query": request.query,
            "agent": "JudgeBot",
            "service_mode": "clarify-v4-smart-guardrail",
            "disclaimer": (
                "AI responses are for informational purposes only. "
                "Always verify important decisions with qualified professionals."
            ),
        }
        yield sse(meta)
        try:
            if request.conversation_stage == "initial":
                yield sse(
                    {
                        "type": "progress",
                        "stage": "collect_candidates",
                        "message": "Collecting candidate clarifying questions...",
                    }
                )

                (
                    next_question,
                    is_fallback,
                    other_suggested_questions,
                    judge_reasoning,
                    chosen_from_agent,
                    agent_candidates,
                    agent_reasoning,
                ) = await _select_next_clarification_question(
                    request.intent,
                    request.query,
                    asked_questions=[],
                    answers=[],
                )

                yield sse(
                    {
                        "type": "progress",
                        "stage": "rank_questions",
                        "message": "Ranking and selecting the best follow-up questions...",
                    }
                )

                if not next_question:
                    next_question = FALLBACK_QUESTIONS[0]
                    is_fallback = True
                    other_suggested_questions = []
                    judge_reasoning = "Fallback question selected because no valid panel output was available."
                    chosen_from_agent = "Fallback"
                    agent_candidates = {"Fallback": [next_question]}
                    agent_reasoning = {"Fallback": "Fallback path used because panel returned no valid next question."}

                state = ClarificationState(
                    original_query=request.query,
                    questions=[next_question],
                    answers=[],
                    fallback_flags=[is_fallback],
                    max_rounds=CLARIFICATION_MAX_ROUNDS,
                )
                yield sse(
                    {
                        "type": "clarify_question",
                        "intent": request.intent,
                        "query": request.query,
                        "question": next_question,
                        "questions": state.questions,
                        "candidate_questions": other_suggested_questions,
                        "other_suggested_questions": other_suggested_questions,
                        "judge_reasoning": judge_reasoning,
                        "chosen_from_agent": chosen_from_agent,
                        "agent_candidates": agent_candidates,
                        "agent_reasoning": agent_reasoning,
                        "current_round": 1,
                        "total_rounds": state.max_rounds,
                        "is_fallback_question": is_fallback,
                        "clarification_state": state.model_dump(),
                        "agent": "JudgeBot",
                        "disclaimer": (
                            "AI responses are for informational purposes only. "
                            "Always verify important decisions with qualified professionals."
                        ),
                    }
                )
                _debug_log(
                    "stream clarify round=%s/%s chosen=%s source=%s fallback=%s",
                    1,
                    CLARIFICATION_MAX_ROUNDS,
                    next_question,
                    chosen_from_agent,
                    is_fallback,
                )
                yield sse({"type": "done", "mode": "clarify"})
                return

            assert request.clarification_state is not None
            state = request.clarification_state
            fallback_flags = (state.fallback_flags + [False] * len(state.questions))[: len(state.questions)]
            answers = [answer for answer in state.answers if answer.strip()]
            answers.append(request.query.strip())

            if len(answers) < state.max_rounds:
                (
                    next_question,
                    is_fallback,
                    other_suggested_questions,
                    judge_reasoning,
                    chosen_from_agent,
                    agent_candidates,
                    agent_reasoning,
                ) = await _select_next_clarification_question(
                    request.intent,
                    state.original_query,
                    asked_questions=state.questions,
                    answers=answers,
                )

                if next_question:
                    updated_state = ClarificationState(
                        original_query=state.original_query,
                        questions=[*state.questions, next_question],
                        answers=answers,
                        fallback_flags=[*fallback_flags, is_fallback],
                        max_rounds=state.max_rounds,
                    )
                    yield sse(
                        {
                            "type": "clarify_question",
                            "intent": request.intent,
                            "query": request.query,
                            "question": next_question,
                            "questions": updated_state.questions,
                            "candidate_questions": other_suggested_questions,
                            "other_suggested_questions": other_suggested_questions,
                            "judge_reasoning": judge_reasoning,
                            "chosen_from_agent": chosen_from_agent,
                            "agent_candidates": agent_candidates,
                            "agent_reasoning": agent_reasoning,
                            "current_round": len(answers) + 1,
                            "total_rounds": updated_state.max_rounds,
                            "is_fallback_question": is_fallback,
                            "clarification_state": updated_state.model_dump(),
                            "agent": "JudgeBot",
                            "disclaimer": (
                                "AI responses are for informational purposes only. "
                                "Always verify important decisions with qualified professionals."
                            ),
                        }
                    )
                    _debug_log(
                        "stream clarify round=%s/%s chosen=%s source=%s fallback=%s",
                        len(answers) + 1,
                        updated_state.max_rounds,
                        next_question,
                        chosen_from_agent,
                        is_fallback,
                    )
                    yield sse({"type": "done", "mode": "clarify"})
                    return

            yield sse(
                {
                    "type": "progress",
                    "stage": "prepare_final",
                    "message": "Generating final recommendation from your answers...",
                }
            )
            async for chunk in orchestrator.stream_judge_response_with_clarifications(
                request.intent,
                state.original_query,
                state.questions[: len(answers)],
                answers,
            ):
                yield sse({"type": "delta", "text": chunk})
            _debug_log("stream final round_count=%s intent=%s", len(answers), request.intent)
            yield sse({"type": "done", "mode": "final"})
        except Exception as e:
            logger.exception("stream failure")
            error_payload = {"type": "error", "message": str(e)}
            yield sse(error_payload)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/ai/status")
async def get_ai_status(
    username: str = Depends(require_ai_access),
):
    """Get AI service status and remaining requests for the current allowlisted user."""
    remaining = await remaining_requests(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    configured = bool(settings.ANTHROPIC_API_KEY)

    return {
        "available": configured,
        "remaining_requests": remaining,
        "max_requests_per_hour": settings.AI_RATE_LIMIT_PER_HOUR,
    }
