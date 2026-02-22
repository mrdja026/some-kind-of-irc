"""AI Service — standalone FastAPI application.

Extracted from the monolith's AI endpoints to run as an independent
microservice in the K3s strangler pattern architecture.

Endpoints:
  /healthz            — ungated K8s probe (liveness + readiness)
  /ai/query           — AI query with intent routing (AI allowlist)
  /ai/query/stream    — SSE streaming AI response (AI allowlist)
  /ai/status          — Rate limit status + AI availability (AI allowlist)
  /ai/gmail/questions — Gmail agent quiz generation
  /ai/gmail/summary   — Gmail agent summarization
"""

import json
import logging
import re
from typing import Literal, Optional, List, Dict, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth import require_ai_access
from config import settings
from orchestrator import orchestrator
from rate_limiter import enforce_rate_limit, remaining_requests
from gmail_agent import GmailAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FALLBACK_QUESTIONS = [
    "What is your target budget and hard spending limit for this decision?",
    "What is the most important outcome for you here?",
    "What timeline are you working with?",
]

MANDATORY_GUARDRAIL_QUESTION = "Do you have a 6-month emergency fund?"
CLARIFICATION_MAX_ROUNDS = 4

gmail_agent = GmailAgent(api_key=settings.ANTHROPIC_API_KEY)


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
        "Standard guardrail: runway unclear or below threshold.",
    )


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ClarificationState(BaseModel):
    original_query: str
    questions: list[str]
    answers: list[str]
    fallback_flags: Optional[list[bool]] = None
    max_rounds: int = 3


class AIQueryRequest(BaseModel):
    intent: str
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


class GmailSummaryRequest(BaseModel):
    emails: List[Dict[str, Any]]
    interest: str
    answers: List[str] = []


class GmailQuestionsRequest(BaseModel):
    interest: str
    previous_answers: List[str] = []


class GmailSummaryResponse(BaseModel):
    final_summary: str
    top_email_ids: List[str]
    reasoning: str


class GmailQuestionsResponse(BaseModel):
    questions: List[str]


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
# FastAPI App
# ---------------------------------------------------------------------------

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


@app.post("/ai/query", response_model=AIQueryResponse)
async def query_ai_agents(
    request: AIQueryRequest,
    username: str = Depends(require_ai_access),
):
    """Query the AI agents with a specific intent (allowlist users only)."""
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    _validate_query(request)

    intent = request.intent
    if intent not in ["afford", "learn"]:
        raise HTTPException(status_code=400, detail=f"Unknown intent: {intent}")

    if request.conversation_stage == "initial":
        # Initial query: generate the first clarification question
        (
            question,
            is_fallback,
            others,
            reasoning,
            chosen_from,
            agents,
            agent_reasoning,
        ) = await _select_next_clarification_question(intent, request.query, [], [])

        if not question:
            # Should not happen ideally, but if no question is generated, fallback or fail
            raise HTTPException(status_code=500, detail="Failed to generate clarification question.")

        return AIQueryResponse(
            mode="clarify",
            intent=intent,
            query=request.query,
            question=question,
            questions=[question],
            candidate_questions=others,
            other_suggested_questions=others,
            agent_candidates=agents,
            agent_reasoning=agent_reasoning,
            judge_reasoning=reasoning,
            chosen_from_agent=chosen_from,
            current_round=1,
            total_rounds=CLARIFICATION_MAX_ROUNDS,
            is_fallback_question=is_fallback,
            clarification_state=ClarificationState(
                original_query=request.query,
                questions=[question],
                answers=[],
                fallback_flags=[is_fallback],
                max_rounds=CLARIFICATION_MAX_ROUNDS,
            ),
            agent="JudgeBot",
        )

    else:
        # Clarification stage
        state = request.clarification_state
        if not state:
            raise HTTPException(status_code=400, detail="Missing clarification state")

        # Check if we have gathered all answers
        # If the user just submitted an answer to the last question:
        # (Client should append the answer to state.answers before sending, or we assume the query IS the answer?
        # The contract implies 'query' is the user's latest input.
        # But for 'clarification' stage, usually we expect the client to have updated the state?
        # Let's assume the client sends the *latest answer* as `query`, and we append it.)
        
        # Actually, looking at the frontend, it sends `query` as the answer.
        # But `AIChannel.tsx` builds the `clarificationState` by appending answers locally?
        # Wait, `queryAI` just passes the state.
        
        # Let's look at `_validate_query`. It expects `state` to be present.
        # If `answers` length < `questions` length, `query` is the answer to `questions[-1]`.
        
        answers = list(state.answers)
        if len(answers) < len(state.questions):
            answers.append(request.query)
        
        # If we have enough answers, generate final response OR next question
        if len(answers) >= state.max_rounds:
            # Generate final response
            final_response = await orchestrator.generate_final_response(
                intent=intent,
                original_query=state.original_query,
                questions=state.questions,
                answers=answers,
            )
            return AIQueryResponse(
                mode="final",
                intent=intent,
                query=request.query,
                response=final_response,
                agent="JudgeBot",
            )
        else:
            # Generate next question
            (
                question,
                is_fallback,
                others,
                reasoning,
                chosen_from,
                agents,
                agent_reasoning,
            ) = await _select_next_clarification_question(
                intent,
                state.original_query,
                state.questions,
                answers,
            )

            if not question:
                # No more questions generated? Proceed to final response early?
                final_response = await orchestrator.generate_final_response(
                    intent=intent,
                    original_query=state.original_query,
                    questions=state.questions,
                    answers=answers,
                )
                return AIQueryResponse(
                    mode="final",
                    intent=intent,
                    query=request.query,
                    response=final_response,
                    agent="JudgeBot",
                )

            # Update state
            new_questions = list(state.questions)
            new_questions.append(question)
            new_fallback_flags = list(state.fallback_flags or [])
            new_fallback_flags.append(is_fallback)

            return AIQueryResponse(
                mode="clarify",
                intent=intent,
                query=request.query,
                question=question,
                questions=new_questions,
                candidate_questions=others,
                other_suggested_questions=others,
                agent_candidates=agents,
                agent_reasoning=agent_reasoning,
                judge_reasoning=reasoning,
                chosen_from_agent=chosen_from,
                current_round=len(new_questions),
                total_rounds=state.max_rounds,
                is_fallback_question=is_fallback,
                clarification_state=ClarificationState(
                    original_query=state.original_query,
                    questions=new_questions,
                    answers=answers,
                    fallback_flags=new_fallback_flags,
                    max_rounds=state.max_rounds,
                ),
                agent="JudgeBot",
            )


@app.post("/ai/query/stream")
async def query_ai_agents_stream(
    request: AIQueryRequest,
    username: str = Depends(require_ai_access),
):
    """Stream AI response (SSE)."""
    await enforce_rate_limit(
        user_id=username,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    _validate_query(request)

    intent = request.intent
    if intent not in ["afford", "learn"]:
        raise HTTPException(status_code=400, detail=f"Unknown intent: {intent}")

    # For now, streaming just wraps the non-streaming logic but emits SSE events.
    # In a real implementation, we would stream tokens from the LLM.
    # Here we simulate the events structure.

    async def event_generator():
        # Emit meta event
        yield f"data: {json.dumps({'type': 'meta', 'intent': intent, 'query': request.query, 'agent': 'JudgeBot', 'disclaimer': 'AI responses are for informational purposes only.'})}\n\n"

        if request.conversation_stage == "initial":
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'collect_candidates', 'message': 'Consulting specialists...'})}\n\n"
            
            (
                question,
                is_fallback,
                others,
                reasoning,
                chosen_from,
                agents,
                agent_reasoning,
            ) = await _select_next_clarification_question(intent, request.query, [], [])

            if not question:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate question'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'progress', 'stage': 'rank_questions', 'message': 'Judge selecting best question...'})}\n\n"

            response_data = {
                "type": "clarify_question",
                "intent": intent,
                "query": request.query,
                "question": question,
                "questions": [question],
                "candidate_questions": others,
                "other_suggested_questions": others,
                "agent_candidates": agents,
                "agent_reasoning": agent_reasoning,
                "judge_reasoning": reasoning,
                "chosen_from_agent": chosen_from,
                "current_round": 1,
                "total_rounds": CLARIFICATION_MAX_ROUNDS,
                "is_fallback_question": is_fallback,
                "clarification_state": {
                    "original_query": request.query,
                    "questions": [question],
                    "answers": [],
                    "fallback_flags": [is_fallback],
                    "max_rounds": CLARIFICATION_MAX_ROUNDS,
                },
                "agent": "JudgeBot",
                "disclaimer": "AI responses are for informational purposes only."
            }
            yield f"data: {json.dumps(response_data)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'mode': 'clarify'})}\n\n"

        else:
            # Clarification stage logic
            state = request.clarification_state
            answers = list(state.answers)
            if len(answers) < len(state.questions):
                answers.append(request.query)

            if len(answers) >= state.max_rounds:
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'prepare_final', 'message': 'Synthesizing final answer...'})}\n\n"
                final_response = await orchestrator.generate_final_response(
                    intent=intent,
                    original_query=state.original_query,
                    questions=state.questions,
                    answers=answers,
                )
                # Stream delta (simulate)
                chunk_size = 20
                for i in range(0, len(final_response), chunk_size):
                    chunk = final_response[i:i+chunk_size]
                    yield f"data: {json.dumps({'type': 'delta', 'text': chunk})}\n\n"
                
                yield f"data: {json.dumps({'type': 'done', 'mode': 'final'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'collect_candidates', 'message': 'Consulting specialists...'})}\n\n"
                (
                    question,
                    is_fallback,
                    others,
                    reasoning,
                    chosen_from,
                    agents,
                    agent_reasoning,
                ) = await _select_next_clarification_question(
                    intent,
                    state.original_query,
                    state.questions,
                    answers,
                )

                if not question:
                     # Fallback to final response if no question
                    final_response = await orchestrator.generate_final_response(
                        intent=intent,
                        original_query=state.original_query,
                        questions=state.questions,
                        answers=answers,
                    )
                    for i in range(0, len(final_response), 20):
                        yield f"data: {json.dumps({'type': 'delta', 'text': final_response[i:i+20]})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'mode': 'final'})}\n\n"
                    return

                new_questions = list(state.questions)
                new_questions.append(question)
                new_fallback_flags = list(state.fallback_flags or [])
                new_fallback_flags.append(is_fallback)

                response_data = {
                    "type": "clarify_question",
                    "intent": intent,
                    "query": request.query,
                    "question": question,
                    "questions": new_questions,
                    "candidate_questions": others,
                    "other_suggested_questions": others,
                    "agent_candidates": agents,
                    "agent_reasoning": agent_reasoning,
                    "judge_reasoning": reasoning,
                    "chosen_from_agent": chosen_from,
                    "current_round": len(new_questions),
                    "total_rounds": state.max_rounds,
                    "is_fallback_question": is_fallback,
                    "clarification_state": {
                        "original_query": state.original_query,
                        "questions": new_questions,
                        "answers": answers,
                        "fallback_flags": new_fallback_flags,
                        "max_rounds": state.max_rounds,
                    },
                    "agent": "JudgeBot",
                    "disclaimer": "AI responses are for informational purposes only."
                }
                yield f"data: {json.dumps(response_data)}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'mode': 'clarify'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
    
    questions = gmail_agent.generate_followup_questions(
        interest=request.interest,
        previous_answers=request.previous_answers
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
    
    # 1. Generate dual summaries
    summaries = gmail_agent.generate_summaries(
        emails=request.emails,
        interest=request.interest,
        answers=request.answers
    )
    
    # 2. Judge and rank
    result = gmail_agent.judge_and_rank(
        emails=request.emails,
        summary_a=summaries.get("summary_a", ""),
        summary_b=summaries.get("summary_b", ""),
        interest=request.interest,
        answers=request.answers
    )
    
    return GmailSummaryResponse(
        final_summary=result.get("final_summary", ""),
        top_email_ids=result.get("top_email_ids", []),
        reasoning=result.get("reasoning", "")
    )
