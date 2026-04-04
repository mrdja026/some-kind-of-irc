"""
Redis stream consumer for persisting AI inference events to Postgres.

Reads from the `ai:session_events` Redis stream using XREADGROUP and writes
each event to the `ai_inference_events` table. Deduplicates by `stream_msg_id`.
Runs as a background thread, similar to ChannelEventSubscriber.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import redis
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import SessionLocal, engine
from src.models.ai_inference_event import AiInferenceEvent

logger = logging.getLogger(__name__)

# Consumer group and consumer name
CONSUMER_GROUP = "ai_event_persister"
CONSUMER_NAME = "backend_worker"

# Read batch size and block timeout
BATCH_SIZE = 100
BLOCK_MS = 5000  # 5 seconds
# Minimum idle time before pending messages are reclaimed via XAUTOCLAIM
MIN_IDLE_TIME_MS = 60_000  # 60 seconds


def _parse_datetime(value: str | None) -> Optional[datetime]:
    """Parse ISO datetime string, returning None on failure."""
    if not value:
        return None
    try:
        # Handle ISO format with or without timezone
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        logger.warning("Failed to parse datetime: %s", value)
        return None


def _safe_json_loads(value: str | None) -> Any:
    """Parse JSON string, returning None on failure."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


class AiEventStreamConsumer:
    """
    Background consumer that persists AI inference events from Redis to Postgres.

    Uses XREADGROUP for reliable consumption with automatic acknowledgment.
    Deduplicates by stream_msg_id using ON CONFLICT DO NOTHING.
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stream_key = settings.AI_SESSION_STREAM_KEY

    def _get_db(self) -> Session:
        """Get database session for persistence."""
        return SessionLocal()

    def _ensure_consumer_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        if not self._client:
            return
        try:
            self._client.xgroup_create(
                self._stream_key,
                CONSUMER_GROUP,
                id="0",  # Start from beginning
                mkstream=True,
            )
            logger.info(
                "Created consumer group '%s' for stream '%s'",
                CONSUMER_GROUP,
                self._stream_key,
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists
                logger.debug("Consumer group '%s' already exists", CONSUMER_GROUP)
            else:
                raise

    def _parse_event_fields(
        self, stream_msg_id: str, fields: dict[str, str]
    ) -> Optional[dict[str, Any]]:
        """Parse raw Redis stream fields into event dict for DB insertion."""
        try:
            recorded_at = _parse_datetime(fields.get("recorded_at"))
            if not recorded_at:
                logger.warning(
                    "Missing or invalid recorded_at for event %s", stream_msg_id
                )
                return None

            payload = _safe_json_loads(fields.get("payload"))
            if payload is None:
                payload = {}

            # Extract caller and tool_calls from payload or top-level fields
            caller = _safe_json_loads(fields.get("caller")) or payload.get("caller")
            tool_calls = _safe_json_loads(fields.get("tool_calls")) or payload.get(
                "tool_calls"
            )

            # Extract question(s), reasoning, plan from payload
            question = fields.get("question") or payload.get("question")
            questions = _safe_json_loads(fields.get("questions")) or payload.get(
                "questions"
            )
            reasoning = fields.get("reasoning") or payload.get("reasoning")
            plan = _safe_json_loads(fields.get("plan")) or payload.get("plan")

            return {
                "stream_msg_id": stream_msg_id,
                "recorded_at": recorded_at,
                "source": fields.get("source", "unknown"),
                "kind": fields.get("kind", "generic_ai"),
                "backend": fields.get("backend", "n/a"),
                "session_id": fields.get("session_id"),
                "request_id": fields.get("request_id"),
                "correlation_id": fields.get("correlation_id"),
                "username": fields.get("username"),
                "caller": caller,
                "tool_calls": tool_calls,
                "question": question,
                "questions": questions,
                "reasoning": reasoning,
                "plan": plan,
                "payload": payload,
                # Retention: automatically expire after 90 days
                "expires_at": datetime.now(timezone.utc) + timedelta(days=90),
            }
        except Exception as e:
            logger.error("Failed to parse event %s: %s", stream_msg_id, e)
            return None

    def _persist_events(self, events: list[dict[str, Any]]) -> int:
        """
        Persist events to Postgres with dedup by stream_msg_id.

        Uses INSERT ... ON CONFLICT DO NOTHING for efficient dedup.
        Returns number of rows inserted.
        Raises on DB failure so callers can skip ACK.
        """
        if not events:
            return 0

        # Check if we're using PostgreSQL (supports ON CONFLICT)
        is_postgres = engine.dialect.name == "postgresql"

        db = self._get_db()
        try:
            if is_postgres:
                # Use PostgreSQL upsert for efficient bulk dedup
                stmt = pg_insert(AiInferenceEvent).values(events)
                stmt = stmt.on_conflict_do_nothing(index_elements=["stream_msg_id"])
                result = db.execute(stmt)
                db.commit()
                return result.rowcount
            else:
                # SQLite fallback: insert one by one with error handling
                inserted = 0
                for event_data in events:
                    try:
                        event = AiInferenceEvent(**event_data)
                        db.add(event)
                        db.commit()
                        inserted += 1
                    except IntegrityError:
                        db.rollback()
                        # Duplicate, skip
                return inserted
        except Exception as e:
            logger.error("Failed to persist events: %s", e)
            db.rollback()
            raise
        finally:
            db.close()

    def _process_messages(
        self, messages: list[tuple[str, dict[str, str]]]
    ) -> list[str]:
        """
        Process a batch of messages from the stream.

        Returns list of message IDs to acknowledge:
        - All IDs when persistence succeeds (including parse failures, which
          should be acked to avoid infinite reprocessing of unparsable messages).
        - Empty list when persistence fails, so messages remain pending and
          will be reclaimed for retry.
        """
        events = []
        msg_ids = []
        failed_parse_ids = []

        for msg_id, fields in messages:
            event_data = self._parse_event_fields(msg_id, fields)
            if event_data:
                events.append(event_data)
                msg_ids.append(msg_id)
            else:
                # Parse failure: track separately — always ACK to prevent infinite reprocessing
                failed_parse_ids.append(msg_id)

        if events:
            try:
                inserted = self._persist_events(events)
                logger.debug("Persisted %d/%d events to Postgres", inserted, len(events))
            except Exception:
                # Persistence failed — do not ACK so messages stay pending for retry
                return []

        return msg_ids + failed_parse_ids

    def _run(self) -> None:
        """Main consumer loop."""
        logger.info("AI event stream consumer started")

        while self._running:
            try:
                # Reclaim messages that have been idle for >60 s in the PEL
                # (Pending Entry List) so they are retried after failures.
                try:
                    next_id = "0-0"
                    while True:
                        next_id, claimed = self._client.xautoclaim(
                            self._stream_key,
                            CONSUMER_GROUP,
                            CONSUMER_NAME,
                            min_idle_time=MIN_IDLE_TIME_MS,
                            start_id=next_id,
                            count=BATCH_SIZE,
                        )
                        if claimed:
                            parsed_claimed = [
                                (
                                    msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                                    {
                                        (k.decode() if isinstance(k, bytes) else k): (
                                            v.decode() if isinstance(v, bytes) else v
                                        )
                                        for k, v in fields.items()
                                    },
                                )
                                for msg_id, fields in claimed
                            ]
                            reclaim_ids = self._process_messages(parsed_claimed)
                            if reclaim_ids:
                                self._client.xack(
                                    self._stream_key, CONSUMER_GROUP, *reclaim_ids
                                )
                        # xautoclaim returns "0-0" when no more pending messages
                        next_id_str = next_id.decode() if isinstance(next_id, bytes) else next_id
                        if next_id_str == "0-0" or not claimed:
                            break
                except Exception as e:
                    logger.warning("XAUTOCLAIM failed (non-fatal): %s", e)

                # Read new messages from stream
                result = self._client.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={self._stream_key: ">"},
                    count=BATCH_SIZE,
                    block=BLOCK_MS,
                )

                if not result:
                    continue

                # Process each stream's messages
                for stream_name, messages in result:
                    if not messages:
                        continue

                    # messages is a list of (msg_id, {field: value})
                    parsed_messages = [
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

                    processed_ids = self._process_messages(parsed_messages)

                    # Acknowledge processed messages
                    if processed_ids:
                        self._client.xack(
                            self._stream_key, CONSUMER_GROUP, *processed_ids
                        )

            except redis.ConnectionError as e:
                logger.error("Redis connection error: %s, retrying in 5s", e)
                time.sleep(5)
            except Exception as e:
                logger.exception("Error in AI event consumer: %s", e)
                time.sleep(1)

        logger.info("AI event stream consumer stopped")

    def start(self) -> None:
        """Start consumer in background thread."""
        if self._running:
            return

        try:
            self._client = redis.Redis.from_url(
                settings.REDIS_LOG_URL, decode_responses=False
            )
            self._ensure_consumer_group()

            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info("AiEventStreamConsumer started")
        except Exception as e:
            logger.error("Failed to start AI event consumer: %s", e)

    def stop(self) -> None:
        """Stop consumer."""
        self._running = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        logger.info("AiEventStreamConsumer stopped")


# Module-level singleton
_consumer: Optional[AiEventStreamConsumer] = None


def start_ai_event_consumer() -> None:
    """Start the AI event stream consumer (call on app startup)."""
    global _consumer
    if _consumer is None:
        _consumer = AiEventStreamConsumer()
        _consumer.start()


def stop_ai_event_consumer() -> None:
    """Stop the AI event stream consumer (call on app shutdown)."""
    global _consumer
    if _consumer:
        _consumer.stop()
        _consumer = None
