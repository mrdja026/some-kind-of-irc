"""
AI Agent endpoint for the #ai channel.

Handles AI queries and rate limiting.
"""

from datetime import datetime, timedelta
import json
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.models.user import User
from src.api.endpoints.auth import get_current_user
from src.services.agent_orchestrator import orchestrator

router = APIRouter(prefix="/ai", tags=["ai"])

# In-memory rate limiting (for production, use Redis)
_rate_limit_store: dict[int, list[datetime]] = {}


class AIQueryRequest(BaseModel):
    intent: Literal["afford", "learn"]
    query: str
    media_urls: Optional[list[str]] = None

    model_config = {
        "extra": "forbid"
    }


class AIQueryResponse(BaseModel):
    intent: str
    query: str
    response: str
    agent: str
    disclaimer: str = "AI responses are for informational purposes only. Always verify important decisions with qualified professionals."


def check_rate_limit(user_id: int) -> bool:
    """Check if user has exceeded rate limit. Returns True if allowed."""
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    
    # Clean up old entries
    if user_id in _rate_limit_store:
        _rate_limit_store[user_id] = [
            ts for ts in _rate_limit_store[user_id] if ts > hour_ago
        ]
    else:
        _rate_limit_store[user_id] = []
    
    # Check limit
    if len(_rate_limit_store[user_id]) >= settings.AI_RATE_LIMIT_PER_HOUR:
        return False
    
    # Record this request
    _rate_limit_store[user_id].append(now)
    return True


def get_remaining_requests(user_id: int) -> int:
    """Get number of remaining AI requests for the user."""
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    
    if user_id not in _rate_limit_store:
        return settings.AI_RATE_LIMIT_PER_HOUR
    
    recent = [ts for ts in _rate_limit_store[user_id] if ts > hour_ago]
    return max(0, settings.AI_RATE_LIMIT_PER_HOUR - len(recent))


def _validate_query(request: AIQueryRequest):
    if request.media_urls:
        raise HTTPException(
            status_code=400,
            detail="Media inputs are not supported for AI queries."
        )
    if len(request.query.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Query too short. Please provide more details."
        )
    if len(request.query) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Query too long. Please keep it under 1000 characters."
        )


@router.post("/query", response_model=AIQueryResponse)
async def query_ai_agents(
    request: AIQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Query the AI agents with a specific intent.

    Intents:
    - afford: Financial affordability analysis
    - learn: Learning material recommendations
    """
    # Check rate limit
    if not check_rate_limit(current_user.id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. You can make {settings.AI_RATE_LIMIT_PER_HOUR} AI queries per hour."
        )
    
    _validate_query(request)

    # Check if Anthropic AI is configured
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Please contact administrator."
        )
    
    try:
        result = await orchestrator.process_query(request.intent, request.query)
        return AIQueryResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI processing failed: {str(e)}"
        )


@router.post("/query/stream")
async def query_ai_agents_stream(
    request: AIQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not check_rate_limit(current_user.id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. You can make {settings.AI_RATE_LIMIT_PER_HOUR} AI queries per hour."
        )

    _validate_query(request)

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Please contact administrator."
        )

    async def event_stream():
        meta = {
            "type": "meta",
            "intent": request.intent,
            "query": request.query,
            "agent": "JudgeBot",
            "disclaimer": "AI responses are for informational purposes only. Always verify important decisions with qualified professionals.",
        }
        yield f"data: {json.dumps(meta)}\n\n"
        try:
            async for chunk in orchestrator.stream_judge_response(request.intent, request.query):
                payload = {"type": "delta", "text": chunk}
                yield f"data: {json.dumps(payload)}\n\n"
            yield "data: {\"type\":\"done\"}\n\n"
        except Exception as e:
            error_payload = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/status")
async def get_ai_status(
    current_user: User = Depends(get_current_user)
):
    """Get AI service status and remaining requests for the user."""
    remaining = get_remaining_requests(current_user.id)
    configured = bool(settings.ANTHROPIC_API_KEY)
    
    return {
        "available": configured,
        "remaining_requests": remaining,
        "max_requests_per_hour": settings.AI_RATE_LIMIT_PER_HOUR
    }
