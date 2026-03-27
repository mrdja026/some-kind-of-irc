"""Persist claims Q&A sessions to Postgres incrementally.

This module writes to three tables owned by the backend Alembic schema:
  - claims_visible_sessions  (conversation header — upserted each turn)
  - claims_visible_turns     (per Q&A turn — appended each turn)
  - claims_debug_events      (inference debug events from Redis stream)

Writes are fire-and-forget: failures are logged but never block the
API response.  Called after **every** turn, not just when done=true.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
from psycopg_pool import AsyncConnectionPool
import redis.asyncio as redis_async

from config import settings

LOG = logging.getLogger(__name__)

_pool: Optional[AsyncConnectionPool] = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> Optional[AsyncConnectionPool]:
    """Lazy-init a small async connection pool (thread-safe via asyncio.Lock)."""
    global _pool
    dsn = settings.DATABASE_URL.strip()
    if not dsn:
        return None
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            _pool = AsyncConnectionPool(
                conninfo=dsn,
                min_size=1,
                max_size=4,
                open=False,
            )
            await _pool.open()
        except Exception:
            LOG.warning("Failed to open Postgres pool for claims persistence", exc_info=True)
            _pool = None
    return _pool


async def _collect_debug_events(
    session_id: str,
    redis_client: Optional[redis_async.Redis],
    stream_key: str,
) -> list[dict[str, Any]]:
    """Read Redis stream events tagged with the given session_id."""
    if redis_client is None:
        return []
    try:
        rows = await redis_client.xrange(stream_key, "-", "+", count=2000)
        events = []
        for msg_id, fields in rows:
            if fields.get("session_id") != session_id:
                continue
            payload_raw = fields.get("payload", "{}")
            try:
                payload = json.loads(payload_raw)
            except (json.JSONDecodeError, TypeError):
                payload = {"raw": payload_raw}
            events.append(
                {
                    "event_kind": fields.get("kind", ""),
                    "stage": payload.get("stage") or payload.get("step"),
                    "payload": payload,
                    "request_id": fields.get("request_id"),
                    "correlation_id": fields.get("correlation_id"),
                    "recorded_at": fields.get("recorded_at", ""),
                }
            )
        return events
    except Exception:
        LOG.warning("Failed to collect debug events from Redis", exc_info=True)
        return []


async def persist_turn(
    *,
    session_id: str,
    claim_id: str,
    username: str,
    status: str,
    flags: Optional[dict[str, Any]],
    turn_number: int,
    question: str,
    answer: str,
    reasoning: Optional[str] = None,
    tool_calls: Optional[list[dict[str, Any]]] = None,
    done: bool = False,
    next_question: Optional[str] = None,
    redis_client: Optional[redis_async.Redis] = None,
    stream_key: str = "",
) -> None:
    """Upsert session header, append a single turn, and (on done) flush debug events.

    Called after every API turn.  The session row is upserted so the first
    call creates it and subsequent calls update turn_count / status / flags.
    Debug events are only collected and written when ``done=True`` to avoid
    reading the full Redis stream on every intermediate turn.
    """
    pool = await _get_pool()
    if pool is None:
        LOG.info("Claims persistence disabled (no DATABASE_URL)")
        return

    now = datetime.now(timezone.utc)
    try:
        sid = uuid.UUID(session_id)
    except (ValueError, AttributeError):
        LOG.warning("Invalid session_id format: %s — skipping persistence", session_id)
        return

    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                # Upsert session header
                await conn.execute(
                    """
                    INSERT INTO claims_visible_sessions
                        (id, claim_id, username, status, flags, turn_count,
                         created_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status       = EXCLUDED.status,
                        flags        = EXCLUDED.flags,
                        turn_count   = EXCLUDED.turn_count,
                        completed_at = CASE WHEN %s THEN EXCLUDED.completed_at
                                            ELSE claims_visible_sessions.completed_at END
                    """,
                    (
                        sid,
                        claim_id,
                        username,
                        status,
                        json.dumps(flags, default=str) if flags else None,
                        turn_number,
                        now,
                        now,
                        done,
                    ),
                )

                # Append this turn
                tc_json = json.dumps(tool_calls, default=str) if tool_calls else None
                await conn.execute(
                    """
                    INSERT INTO claims_visible_turns
                        (id, session_id, turn_number, question, answer, reasoning,
                         tool_calls, done, next_question, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT ON CONSTRAINT uq_session_turn DO UPDATE SET
                        answer       = EXCLUDED.answer,
                        reasoning    = EXCLUDED.reasoning,
                        tool_calls   = EXCLUDED.tool_calls,
                        done         = EXCLUDED.done,
                        next_question = EXCLUDED.next_question
                    """,
                    (
                        uuid.uuid4(),
                        sid,
                        turn_number,
                        question,
                        answer,
                        reasoning,
                        tc_json,
                        done,
                        next_question,
                        now,
                    ),
                )

                # Flush debug events from Redis every turn
                debug_events = await _collect_debug_events(
                    session_id, redis_client, stream_key
                )
                for evt in debug_events:
                    recorded_at_str = evt.get("recorded_at", "")
                    try:
                        recorded_at = datetime.fromisoformat(
                            recorded_at_str.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        recorded_at = now

                    await conn.execute(
                        """
                        INSERT INTO claims_debug_events
                            (id, session_id, event_kind, stage, payload,
                             request_id, correlation_id, recorded_at, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT ON CONSTRAINT uq_debug_event_dedup DO NOTHING
                        """,
                        (
                            uuid.uuid4(),
                            sid,
                            evt.get("event_kind", ""),
                            evt.get("stage"),
                            json.dumps(evt.get("payload", {}), default=str),
                            evt.get("request_id"),
                            evt.get("correlation_id"),
                            recorded_at,
                            now,
                        ),
                    )

                LOG.info(
                    "Persisted turn %d for session %s (done=%s, %d debug events)",
                    turn_number, session_id, done, len(debug_events),
                )

    except Exception:
        LOG.warning(
            "Failed to persist turn %d for session %s",
            turn_number, session_id, exc_info=True,
        )
