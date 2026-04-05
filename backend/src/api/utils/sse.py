"""SSE (Server-Sent Events) utilities for streaming AI responses."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Literal

from fastapi.responses import StreamingResponse


SSE_EVENT_TYPES = Literal["meta", "progress", "delta", "done", "error"]


def sse_event(event_type: SSE_EVENT_TYPES, data: dict[str, Any]) -> str:
    """Format a single SSE event.

    Args:
        event_type: One of meta, progress, delta, done, error
        data: JSON-serializable payload

    Returns:
        SSE-formatted string with event type and data lines
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def sse_response(generator: AsyncIterator[str]) -> StreamingResponse:
    """Wrap an async generator as an SSE StreamingResponse.

    Args:
        generator: Async iterator yielding SSE-formatted strings

    Returns:
        FastAPI StreamingResponse with correct headers
    """
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def emit_meta(agent: str, model: str = "gemini-2.0-flash") -> str:
    """Emit a meta event with agent info."""
    return sse_event("meta", {"agent": agent, "model": model})


async def emit_progress(stage: str, message: str) -> str:
    """Emit a progress event."""
    return sse_event("progress", {"stage": stage, "message": message})


async def emit_done(result: dict[str, Any]) -> str:
    """Emit a done event with final result."""
    return sse_event("done", {"result": result})


async def emit_error(code: str, message: str) -> str:
    """Emit an error event."""
    return sse_event("error", {"code": code, "message": message})
