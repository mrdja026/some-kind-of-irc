"""Persist completed claims Q&A sessions to Postgres.

This module writes to three tables owned by the backend Alembic schema:
  - claims_visible_sessions  (conversation header)
  - claims_visible_turns     (per Q&A turn)
  - claims_debug_events      (inference debug events from Redis stream)

Writes are fire-and-forget: failures are logged but never block the
API response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
import psycopg.rows
import redis.asyncio as redis_async

from config import settings

LOG = logging.getLogger(__name__)

_pool: Optional[psycopg.AsyncConnectionPool] = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> Optional[psycopg.AsyncConnectionPool]:
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
            _pool = psycopg.AsyncConnectionPool(
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


async def persist_completed_session(
    *,
    session_id: str,
    claim_id: str,
    username: str,
    status: str,
    flags: Optional[dict[str, Any]],
    turns: list[dict[str, Any]],
    redis_client: Optional[redis_async.Redis] = None,
    stream_key: str = "",
) -> None:
    """Write a completed session (header + turns + debug events) to Postgres.

    Parameters
    ----------
    session_id : UUID string for this conversation.
    claim_id   : e.g. "CLM-2026-0001" (reference to MinIO).
    username   : User who completed the session.
    status     : Final claim status from flags.
    flags      : Truth-check flags snapshot (JSONB).
    turns      : List of dicts, each with keys:
                 question, answer, reasoning, tool_calls, done, next_question.
    redis_client : Optional async Redis client for collecting debug events.
    stream_key   : Redis stream key for debug events.
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

    debug_events = await _collect_debug_events(session_id, redis_client, stream_key)

    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO claims_visible_sessions
                        (id, claim_id, username, status, flags, turn_count, created_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        sid,
                        claim_id,
                        username,
                        status,
                        json.dumps(flags, default=str) if flags else None,
                        len(turns),
                        now,
                        now,
                    ),
                )

                for i, turn in enumerate(turns, start=1):
                    tc = turn.get("tool_calls")
                    await conn.execute(
                        """
                        INSERT INTO claims_visible_turns
                            (id, session_id, turn_number, question, answer, reasoning,
                             tool_calls, done, next_question, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            uuid.uuid4(),
                            sid,
                            i,
                            turn.get("question", ""),
                            turn.get("answer", ""),
                            turn.get("reasoning"),
                            json.dumps(tc, default=str) if tc else None,
                            bool(turn.get("done", False)),
                            turn.get("next_question"),
                            now,
                        ),
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
            "Persisted claims session %s: %d turns, %d debug events",
            session_id,
            len(turns),
            len(debug_events),
        )
    except Exception:
        LOG.warning(
            "Failed to persist claims session %s to Postgres",
            session_id,
            exc_info=True,
        )
