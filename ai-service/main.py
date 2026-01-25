"""AI Service — standalone FastAPI application.

Extracted from the monolith's AI endpoints to run as an independent
microservice in the K3s strangler pattern architecture.

Endpoints:
  /healthz            — ungated K8s probe (liveness + readiness)
  /ai/query           — AI query with intent routing (admin only)
  /ai/query/stream    — SSE streaming AI response (admin only)
  /ai/status          — Rate limit status + AI availability (admin only)
"""

import json
import logging
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import require_admin
from config import settings
from orchestrator import orchestrator
from rate_limiter import enforce_rate_limit, remaining_requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Service", version="1.0.0")

# CORS — allow monolith origins for browser-based requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(",") if hasattr(settings, "ALLOWED_ORIGINS") else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health probe — ungated
# ---------------------------------------------------------------------------

@app.get("/healthz")
async def healthz():
    """Kubernetes liveness/readiness probe (no auth required)."""
    return {"service": "ai-service", "status": "ok"}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AIQueryRequest(BaseModel):
    intent: Literal["afford", "learn"]
    query: str
    media_urls: Optional[list[str]] = None

    model_config = {"extra": "forbid"}


class AIQueryResponse(BaseModel):
    intent: str
    query: str
    response: str
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
    if len(request.query.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Query too short. Please provide more details.",
        )
    if len(request.query) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Query too long. Please keep it under 1000 characters.",
        )


# ---------------------------------------------------------------------------
# AI endpoints — admin-gated
# ---------------------------------------------------------------------------

@app.post("/ai/query", response_model=AIQueryResponse)
async def query_ai_agents(
    request: AIQueryRequest,
    username: str = Depends(require_admin),
):
    """Query the AI agents with a specific intent (admin only).

    Intents:
    - afford: Financial affordability analysis
    - learn: Learning material recommendations
    """
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

    try:
        result = await orchestrator.process_query(request.intent, request.query)
        return AIQueryResponse(**result)
    except Exception as e:
        logger.error(f"AI processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


@app.post("/ai/query/stream")
async def query_ai_agents_stream(
    request: AIQueryRequest,
    username: str = Depends(require_admin),
):
    """Stream an AI response via Server-Sent Events (admin only)."""
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
        meta = {
            "type": "meta",
            "intent": request.intent,
            "query": request.query,
            "agent": "JudgeBot",
            "disclaimer": (
                "AI responses are for informational purposes only. "
                "Always verify important decisions with qualified professionals."
            ),
        }
        yield f"data: {json.dumps(meta)}\n\n"
        try:
            async for chunk in orchestrator.stream_judge_response(request.intent, request.query):
                payload = {"type": "delta", "text": chunk}
                yield f"data: {json.dumps(payload)}\n\n"
            yield 'data: {"type":"done"}\n\n'
        except Exception as e:
            error_payload = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/ai/status")
async def get_ai_status(
    username: str = Depends(require_admin),
):
    """Get AI service status and remaining requests for the user (admin only)."""
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
