"""Persist claims Q&A sessions to Postgres incrementally.

This module writes to three tables owned by the backend Alembic schema:
  - claims_visible_sessions  (conversation header — upserted each turn)
  - claims_visible_turns     (per Q&A turn — appended each turn)
  - claims_debug_events      (inference debug events from Redis stream)

Writes are fire-and-forget: failures are logged but never block the
API response.  Called after **every** turn, not just when done=true.

Design notes:
  - Debug events are collected from Redis **before** acquiring the DB
    connection so that a slow Redis call never holds a Postgres connection
    open.
  - Deduplication of debug events is done via the ``stream_msg_id`` column
    (the Redis XADD message ID), which is always unique per message.  This
    avoids the PostgreSQL NULL-inequality trap that makes nullable columns
    unsafe as unique constraint components.
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
    """Read Redis stream events tagged with the given session_id.

    Returns a list of dicts that include ``stream_msg_id`` (the Redis XADD
    message ID), which is the authoritative dedup key for ``claims_debug_events``.
    """
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
                    "stream_msg_id": msg_id,
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
    """Upsert session header, append a single turn, and flush debug events.

    Called after every API turn.  The session row is upserted so the first
    call creates it and subsequent calls update turn_count / status / flags.

    Debug events are collected from Redis **before** the DB transaction so
    that a slow Redis read never holds a Postgres connection open.  Each event
    is deduplicated by its Redis stream message ID (``stream_msg_id``), which
    is always unique, avoiding NULL-equality issues with nullable columns.
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

    # Collect debug events from Redis BEFORE acquiring the DB connection so
    # that a slow Redis read does not hold a Postgres connection/transaction open.
    debug_events = await _collect_debug_events(session_id, redis_client, stream_key)

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

                # Insert debug events collected earlier (outside this transaction).
                # stream_msg_id is the Redis XADD message ID — always unique per
                # message — used as the dedup key so ON CONFLICT is always reliable.
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
                            (id, session_id, stream_msg_id, event_kind, stage, payload,
                             request_id, correlation_id, recorded_at, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT ON CONSTRAINT uq_debug_event_stream_msg DO NOTHING
                        """,
                        (
                            uuid.uuid4(),
                            sid,
                            evt.get("stream_msg_id", ""),
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
