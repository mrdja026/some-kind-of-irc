"""Redis event subscriber for channel-related user events."""
import json
import logging
import threading
from typing import Optional

import redis
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import SessionLocal
from src.models.channel import Channel
from src.models.membership import Membership
from src.services.irc_logger import log_join

logger = logging.getLogger(__name__)


class ChannelEventSubscriber:
    """Subscribes to user events and auto-joins users to #general."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def _get_db(self) -> Session:
        """Get database session for event handlers."""
        return SessionLocal()

    def _ensure_general_channel(self, db: Session) -> Channel:
        """Get or create #general channel."""
        channel = db.query(Channel).filter(Channel.name == "#general").first()
        if not channel:
            channel = Channel(name="#general", type="public")
            db.add(channel)
            db.commit()
            db.refresh(channel)
            logger.info(f"Created #general channel (id={channel.id})")
        return channel

    def _ensure_membership(self, db: Session, user_id: int, channel_id: int) -> bool:
        """Create membership if not exists (idempotent)."""
        membership = (
            db.query(Membership)
            .filter(Membership.user_id == user_id, Membership.channel_id == channel_id)
            .first()
        )

        if not membership:
            membership = Membership(user_id=user_id, channel_id=channel_id)
            db.add(membership)
            db.commit()
            logger.info(f"Added user {user_id} to #general")
            return True
        return False

    def handle_user_registered(self, event_data: dict) -> None:
        """Handle user.registered event."""
        db = None
        try:
            db = self._get_db()
            user_id = event_data["user_id"]
            username = event_data["username"]

            general = self._ensure_general_channel(db)

            if self._ensure_membership(db, user_id, general.id):
                log_join(user_id, general.id, "#general")

        except Exception as e:
            logger.error(f"Failed to handle user.registered: {e}")
        finally:
            if db:
                db.close()

    def _message_handler(self, message: dict) -> None:
        """Route messages to appropriate handlers."""
        if message["type"] != "message":
            return

        try:
            event = json.loads(message["data"])
            event_type = event.get("event_type")

            if event_type == "user.registered":
                self.handle_user_registered(event)
            else:
                logger.warning(f"Unknown event type: {event_type}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in event: {message.get('data')}")
        except Exception as e:
            logger.error(f"Error handling event: {e}")

    def start(self) -> None:
        """Start subscriber in background thread."""
        if self._running:
            return

        try:
            self._client = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            self._pubsub = self._client.pubsub()
            self._pubsub.subscribe("user.events")

            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info("ChannelEventSubscriber started")
        except Exception as e:
            logger.error(f"Failed to start subscriber: {e}")

    def _run(self) -> None:
        """Main loop for subscriber."""
        for message in self._pubsub.listen():
            if not self._running:
                break
            self._message_handler(message)

    def stop(self) -> None:
        """Stop subscriber."""
        self._running = False
        if self._pubsub:
            self._pubsub.unsubscribe()
            self._pubsub.close()
        logger.info("ChannelEventSubscriber stopped")


_subscriber: Optional[ChannelEventSubscriber] = None


def start_event_subscriber() -> None:
    """Start the event subscriber (call on app startup)."""
    global _subscriber
    if _subscriber is None:
        _subscriber = ChannelEventSubscriber()
        _subscriber.start()


def stop_event_subscriber() -> None:
    """Stop the event subscriber (call on app shutdown)."""
    global _subscriber
    if _subscriber:
        _subscriber.stop()
        _subscriber = None
