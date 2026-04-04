"""
Continuous Redis→Postgres consumer for AI inference and Caddy log events.

Reads from two Redis streams using XREADGROUP and fans out events to
domain-specific Postgres tables:

  ai:session_events →
    - ai_inference_events      (ALL events, audit log)
    - gmail_agent_events       (gmail_* kinds)
    - calendar_agent_events    (calendar_* kinds)

  caddy:warn_error_logs →
    - caddy_log_events         (warn/error HTTP logs)

Deduplicates by stream_msg_id using ON CONFLICT DO NOTHING.
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import redis

LOG = logging.getLogger("redis-log-sink.consumer")

CONSUMER_GROUP = "log_sink_persister"
CONSUMER_NAME = "sink_worker"
BATCH_SIZE = 100
BLOCK_MS = 5000
MIN_IDLE_TIME_MS = 60_000

# Domain routing prefixes
def _is_gmail_kind(kind: str) -> bool:
    """Return True for any gmail_* event kind."""
    return kind.startswith("gmail_")


_CALENDAR_KINDS = frozenset(
    {
        "calendar_question",
        "calendar_create",
    }
)

_TTL_DAYS = 90

# ── SQL templates ───────────────────────────────────────────────────

_INSERT_AI_INFERENCE = """
INSERT INTO ai_inference_events (
    id, stream_msg_id, recorded_at, source, kind, backend,
    session_id, request_id, correlation_id, username,
    caller, tool_calls, question, questions, reasoning, plan,
    payload, created_at, expires_at
) VALUES (
    %(id)s::UUID, %(stream_msg_id)s, %(recorded_at)s::TIMESTAMPTZ,
    %(source)s, %(kind)s, %(backend)s,
    %(session_id)s, %(request_id)s, %(correlation_id)s, %(username)s,
    %(caller)s::JSONB, %(tool_calls)s::JSONB, %(question)s,
    %(questions)s::JSONB, %(reasoning)s, %(plan)s::JSONB,
    %(payload)s::JSONB, %(created_at)s::TIMESTAMPTZ, %(expires_at)s::TIMESTAMPTZ
) ON CONFLICT (stream_msg_id) DO NOTHING
"""

_INSERT_GMAIL = """
INSERT INTO gmail_agent_events (
    id, stream_msg_id, session_id, request_id, username,
    kind, step, interest, email_count, questions, top_email_ids,
    final_summary, reasoning, caller, payload,
    recorded_at, created_at, expires_at
) VALUES (
    %(id)s::UUID, %(stream_msg_id)s, %(session_id)s, %(request_id)s, %(username)s,
    %(kind)s, %(step)s, %(interest)s, %(email_count)s,
    %(questions)s::JSONB, %(top_email_ids)s::JSONB,
    %(final_summary)s, %(reasoning)s, %(caller)s::JSONB, %(payload)s::JSONB,
    %(recorded_at)s::TIMESTAMPTZ, %(created_at)s::TIMESTAMPTZ, %(expires_at)s::TIMESTAMPTZ
) ON CONFLICT (stream_msg_id) DO NOTHING
"""

_INSERT_CALENDAR = """
INSERT INTO calendar_agent_events (
    id, stream_msg_id, session_id, request_id, username,
    kind, status, event_title, start_datetime, end_datetime,
    timezone, attendees, google_event_id, google_html_link,
    caller, payload, recorded_at, created_at, expires_at
) VALUES (
    %(id)s::UUID, %(stream_msg_id)s, %(session_id)s, %(request_id)s, %(username)s,
    %(kind)s, %(status)s, %(event_title)s, %(start_datetime)s, %(end_datetime)s,
    %(timezone)s, %(attendees)s::JSONB, %(google_event_id)s, %(google_html_link)s,
    %(caller)s::JSONB, %(payload)s::JSONB,
    %(recorded_at)s::TIMESTAMPTZ, %(created_at)s::TIMESTAMPTZ, %(expires_at)s::TIMESTAMPTZ
) ON CONFLICT (stream_msg_id) DO NOTHING
"""

_INSERT_CADDY = """
INSERT INTO caddy_log_events (
    id, stream_msg_id, level, logger, message, raw_payload,
    recorded_at, created_at, expires_at
) VALUES (
    %(id)s::UUID, %(stream_msg_id)s, %(level)s, %(logger)s, %(message)s,
    %(raw_payload)s::JSONB, %(recorded_at)s::TIMESTAMPTZ,
    %(created_at)s::TIMESTAMPTZ, %(expires_at)s::TIMESTAMPTZ
) ON CONFLICT (stream_msg_id) DO NOTHING
"""


def _safe_json(value: Optional[str]) -> Any:
    """Parse JSON string, returning None on failure."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _safe_json_text(value: Optional[str], *, default: Optional[str] = None) -> Optional[str]:
    """Round-trip a JSON string through parse+re-serialize to ensure validity.

    Returns *default* when the input is absent or unparseable so that JSONB
    columns receive either valid JSON or NULL instead of a raw malformed string
    that would cause the INSERT to fail.
    """
    parsed = _safe_json(value)
    if parsed is None:
        return default
    return json.dumps(parsed)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime, returning None on failure."""
    if not value:
        return None
    try:
        v = value.replace("Z", "+00:00") if value.endswith("Z") else value
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expiry() -> datetime:
    return _now() + timedelta(days=_TTL_DAYS)


def _build_ai_inference_row(msg_id: str, f: dict[str, str]) -> Optional[dict]:
    """Parse Redis fields into ai_inference_events row dict."""
    recorded_at = _parse_dt(f.get("recorded_at"))
    if not recorded_at:
        return None

    return {
        "id": str(uuid.uuid4()),
        "stream_msg_id": msg_id,
        "recorded_at": recorded_at,
        "source": f.get("source", "unknown"),
        "kind": f.get("kind", "generic_ai"),
        "backend": f.get("backend", "n/a"),
        "session_id": f.get("session_id"),
        "request_id": f.get("request_id"),
        "correlation_id": f.get("correlation_id"),
        "username": f.get("username"),
        "caller": _safe_json_text(f.get("caller")),
        "tool_calls": _safe_json_text(f.get("tool_calls")),
        "question": f.get("question"),
        "questions": _safe_json_text(f.get("questions")),
        "reasoning": f.get("reasoning"),
        "plan": _safe_json_text(f.get("plan")),
        "payload": _safe_json_text(f.get("payload"), default="{}"),
        "created_at": _now(),
        "expires_at": _expiry(),
    }


def _build_gmail_row(msg_id: str, f: dict[str, str]) -> Optional[dict]:
    """Parse Redis fields into gmail_agent_events row dict."""
    recorded_at = _parse_dt(f.get("recorded_at"))
    if not recorded_at:
        return None

    payload_raw = _safe_json_text(f.get("payload"), default="{}")
    payload = _safe_json(payload_raw) or {}

    req = payload.get("request", {}) if isinstance(payload, dict) else {}
    resp = payload.get("response", {}) if isinstance(payload, dict) else {}
    step = payload.get("step") if isinstance(payload, dict) else None

    questions_val = (
        json.dumps(resp.get("questions"))
        if isinstance(resp, dict) and resp.get("questions")
        else _safe_json_text(f.get("questions"))
    )
    top_emails_val = (
        json.dumps(resp.get("top_email_ids"))
        if isinstance(resp, dict) and resp.get("top_email_ids")
        else None
    )

    return {
        "id": str(uuid.uuid4()),
        "stream_msg_id": msg_id,
        "session_id": f.get("session_id"),
        "request_id": f.get("request_id"),
        "username": f.get("username"),
        "kind": f.get("kind", ""),
        "step": step,
        "interest": req.get("interest") if isinstance(req, dict) else None,
        "email_count": req.get("email_count") if isinstance(req, dict) else None,
        "questions": questions_val,
        "top_email_ids": top_emails_val,
        "final_summary": resp.get("final_summary") if isinstance(resp, dict) else None,
        "reasoning": resp.get("reasoning") if isinstance(resp, dict) else f.get("reasoning"),
        "caller": _safe_json_text(f.get("caller")),
        "payload": payload_raw,
        "recorded_at": recorded_at,
        "created_at": _now(),
        "expires_at": _expiry(),
    }


def _build_calendar_row(msg_id: str, f: dict[str, str]) -> Optional[dict]:
    """Parse Redis fields into calendar_agent_events row dict."""
    recorded_at = _parse_dt(f.get("recorded_at"))
    if not recorded_at:
        return None

    payload_raw = _safe_json_text(f.get("payload"), default="{}")
    payload = _safe_json(payload_raw) or {}

    req = payload.get("request", {}) if isinstance(payload, dict) else {}
    resp = payload.get("response", {}) if isinstance(payload, dict) else {}

    attendees_val = (
        json.dumps(req.get("attendees"))
        if isinstance(req, dict) and req.get("attendees")
        else None
    )

    return {
        "id": str(uuid.uuid4()),
        "stream_msg_id": msg_id,
        "session_id": f.get("session_id"),
        "request_id": f.get("request_id"),
        "username": f.get("username"),
        "kind": f.get("kind", ""),
        "status": resp.get("status") if isinstance(resp, dict) else None,
        "event_title": req.get("event_title") if isinstance(req, dict) else None,
        "start_datetime": req.get("start_datetime") if isinstance(req, dict) else None,
        "end_datetime": req.get("end_datetime") if isinstance(req, dict) else None,
        "timezone": req.get("timezone") if isinstance(req, dict) else None,
        "attendees": attendees_val,
        "google_event_id": resp.get("event_id") if isinstance(resp, dict) else None,
        "google_html_link": resp.get("html_link") if isinstance(resp, dict) else None,
        "caller": _safe_json_text(f.get("caller")),
        "payload": payload_raw,
        "recorded_at": recorded_at,
        "created_at": _now(),
        "expires_at": _expiry(),
    }


def _build_caddy_row(msg_id: str, f: dict[str, str]) -> Optional[dict]:
    """Parse Redis fields into caddy_log_events row dict."""
    ts_raw = f.get("ts")
    recorded_at = _parse_dt(ts_raw) if ts_raw else _now()

    return {
        "id": str(uuid.uuid4()),
        "stream_msg_id": msg_id,
        "level": f.get("level", "unknown"),
        "logger": f.get("logger"),
        "message": f.get("msg"),
        "raw_payload": f.get("payload", "{}"),
        "recorded_at": recorded_at,
        "created_at": _now(),
        "expires_at": _expiry(),
    }


class StreamConsumer:
    """
    Background consumer that reads from Redis streams and writes to Postgres.

    Uses XREADGROUP for reliable consumption with automatic acknowledgment.
    Routes events by kind to domain-specific tables.
    """

    def __init__(
        self,
        redis_url: str,
        database_url: str,
        ai_stream_key: str = "ai:session_events",
        caddy_stream_key: str = "caddy:warn_error_logs",
    ):
        self._redis_url = redis_url
        self._database_url = database_url
        self._ai_stream_key = ai_stream_key
        self._caddy_stream_key = caddy_stream_key
        self._client: Optional[redis.Redis] = None
        self._pg_pool = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def _get_pg_conn(self):
        """Get a connection from the psycopg pool."""
        if self._pg_pool is None:
            import psycopg_pool
            self._pg_pool = psycopg_pool.ConnectionPool(
                self._database_url,
                min_size=1,
                max_size=4,
                open=True,
            )
        return self._pg_pool.getconn()

    def _return_pg_conn(self, conn):
        """Return a connection to the pool."""
        if self._pg_pool:
            self._pg_pool.putconn(conn)

    def _ensure_consumer_groups(self) -> None:
        """Create consumer groups for both streams."""
        for stream_key in (self._ai_stream_key, self._caddy_stream_key):
            try:
                self._client.xgroup_create(stream_key, CONSUMER_GROUP, id="0", mkstream=True)
                LOG.info("Created consumer group '%s' for stream '%s'", CONSUMER_GROUP, stream_key)
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    LOG.debug("Consumer group '%s' already exists for '%s'", CONSUMER_GROUP, stream_key)
                else:
                    raise

    def _persist_ai_events(self, messages: list[tuple[str, dict[str, str]]]) -> list[str]:
        """Persist AI session events to audit + domain tables."""
        ack_ids = []
        conn = self._get_pg_conn()
        try:
            with conn.cursor() as cur:
                for msg_id, fields in messages:
                    kind = fields.get("kind", "")

                    # Always write to audit table
                    audit_row = _build_ai_inference_row(msg_id, fields)
                    if audit_row:
                        try:
                            cur.execute(_INSERT_AI_INFERENCE, audit_row)
                        except Exception as e:
                            LOG.warning("Audit insert failed for %s: %s", msg_id, e)
                            conn.rollback()
                            continue

                    # Route to domain table
                    if _is_gmail_kind(kind):
                        domain_row = _build_gmail_row(msg_id, fields)
                        if domain_row:
                            try:
                                cur.execute(_INSERT_GMAIL, domain_row)
                            except Exception as e:
                                LOG.warning("Gmail insert failed for %s: %s", msg_id, e)
                                conn.rollback()
                                continue

                    elif kind in _CALENDAR_KINDS:
                        domain_row = _build_calendar_row(msg_id, fields)
                        if domain_row:
                            try:
                                cur.execute(_INSERT_CALENDAR, domain_row)
                            except Exception as e:
                                LOG.warning("Calendar insert failed for %s: %s", msg_id, e)
                                conn.rollback()
                                continue

                    conn.commit()
                    ack_ids.append(msg_id)

        except Exception as e:
            LOG.error("Failed to persist AI events: %s", e)
            conn.rollback()
        finally:
            self._return_pg_conn(conn)

        return ack_ids

    def _persist_caddy_events(self, messages: list[tuple[str, dict[str, str]]]) -> list[str]:
        """Persist Caddy log events to caddy_log_events table."""
        ack_ids = []
        conn = self._get_pg_conn()
        try:
            with conn.cursor() as cur:
                for msg_id, fields in messages:
                    row = _build_caddy_row(msg_id, fields)
                    if row:
                        try:
                            cur.execute(_INSERT_CADDY, row)
                            conn.commit()
                            ack_ids.append(msg_id)
                        except Exception as e:
                            LOG.warning("Caddy insert failed for %s: %s", msg_id, e)
                            conn.rollback()
                    else:
                        ack_ids.append(msg_id)
        except Exception as e:
            LOG.error("Failed to persist Caddy events: %s", e)
            conn.rollback()
        finally:
            self._return_pg_conn(conn)

        return ack_ids

    def _decode_messages(self, messages) -> list[tuple[str, dict[str, str]]]:
        """Decode Redis byte messages to strings."""
        return [
            (
                msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                {
                    (k.decode() if isinstance(k, bytes) else k): (
                        v.decode() if isinstance(v, bytes) else v
                    )
                    for k, v in fields.items()
                },
            )
            for msg_id, fields in messages
        ]

    def _process_stream(
        self,
        stream_key: str,
        persist_fn,
        messages: list[tuple[str, dict[str, str]]],
    ) -> None:
        """Process and acknowledge a batch of messages."""
        if not messages:
            return
        decoded = self._decode_messages(messages)
        ack_ids = persist_fn(decoded)
        if ack_ids:
            self._client.xack(stream_key, CONSUMER_GROUP, *ack_ids)
            LOG.debug("Acked %d/%d messages for %s", len(ack_ids), len(decoded), stream_key)

    def _reclaim_pending(self, stream_key: str, persist_fn) -> None:
        """Reclaim idle pending messages via XAUTOCLAIM."""
        try:
            next_id = "0-0"
            while True:
                next_id, claimed, deleted_ids = self._client.xautoclaim(
                    stream_key,
                    CONSUMER_GROUP,
                    CONSUMER_NAME,
                    min_idle_time=MIN_IDLE_TIME_MS,
                    start_id=next_id,
                    count=BATCH_SIZE,
                )
                if deleted_ids:
                    LOG.debug("XAUTOCLAIM pruned %d stale IDs from %s PEL", len(deleted_ids), stream_key)
                if claimed:
                    self._process_stream(stream_key, persist_fn, claimed)
                next_id_str = next_id.decode() if isinstance(next_id, bytes) else next_id
                if next_id_str == "0-0" or not claimed:
                    break
        except Exception as e:
            LOG.warning("XAUTOCLAIM failed for %s (non-fatal): %s", stream_key, e)

    def _run(self) -> None:
        """Main consumer loop."""
        LOG.info("Stream consumer started (AI=%s, Caddy=%s)", self._ai_stream_key, self._caddy_stream_key)

        while self._running:
            try:
                # Reclaim pending messages
                self._reclaim_pending(self._ai_stream_key, self._persist_ai_events)
                self._reclaim_pending(self._caddy_stream_key, self._persist_caddy_events)

                # Read new messages from both streams
                result = self._client.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={
                        self._ai_stream_key: ">",
                        self._caddy_stream_key: ">",
                    },
                    count=BATCH_SIZE,
                    block=BLOCK_MS,
                )

                if not result:
                    continue

                for stream_name, messages in result:
                    if not messages:
                        continue
                    sn = stream_name.decode() if isinstance(stream_name, bytes) else stream_name
                    if sn == self._ai_stream_key:
                        self._process_stream(sn, self._persist_ai_events, messages)
                    elif sn == self._caddy_stream_key:
                        self._process_stream(sn, self._persist_caddy_events, messages)

            except redis.ConnectionError as e:
                LOG.error("Redis connection error: %s, retrying in 5s", e)
                time.sleep(5)
            except Exception as e:
                LOG.exception("Error in stream consumer: %s", e)
                time.sleep(1)

        LOG.info("Stream consumer stopped")

    def start(self) -> None:
        """Start consumer in background thread."""
        if self._running:
            return
        if not self._database_url:
            LOG.warning("DATABASE_URL not set; stream consumer disabled")
            return

        try:
            self._client = redis.Redis.from_url(self._redis_url, decode_responses=False)
            self._ensure_consumer_groups()
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            LOG.info("StreamConsumer started")
        except Exception as e:
            LOG.error("Failed to start stream consumer: %s", e)
            raise

    def stop(self) -> None:
        """Stop consumer and close connections."""
        self._running = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        if self._pg_pool:
            try:
                self._pg_pool.close()
            except Exception:
                pass
        LOG.info("StreamConsumer stopped")
