import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models.gmail_token import GmailToken

logger = logging.getLogger(__name__)


def _get_credentials(db_token: GmailToken) -> Credentials:
    """Create a Credentials object from the DB token."""
    return Credentials(
        token=db_token.access_token,
        refresh_token=db_token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_OAUTH_CLIENT_ID,
        client_secret=settings.GMAIL_OAUTH_CLIENT_SECRET,
        scopes=db_token.scope.split(" ") if db_token.scope else [],
    )


async def fetch_latest_emails(
    db: Session, user_id: int, max_results: int = 100
) -> List[Dict[str, Any]]:
    """Fetch latest emails for the user and normalize them."""
    db_token = db.query(GmailToken).filter(GmailToken.user_id == user_id).first()
    if not db_token:
        raise ValueError("Gmail not connected for this user")

    creds = _get_credentials(db_token)

    # Build the service
    service = build("gmail", "v1", credentials=creds)

    try:
        # List messages
        results = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])

        if not messages:
            return []

        # Update access token in DB if it was refreshed
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            db_token.access_token = creds.token
            if creds.expiry:
                db_token.expires_at = creds.expiry
            db.commit()

        # Batch fetch details
        email_data = []
        for msg in messages:
            msg_id = msg["id"]
            full_msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="metadata")
                .execute()
            )

            headers = full_msg.get("payload", {}).get("headers", [])
            header_map = {h["name"].lower(): h["value"] for h in headers}

            # Map category from labels
            labels = full_msg.get("labelIds", [])
            category = "primary"
            for label in labels:
                if label.startswith("CATEGORY_"):
                    category = label.replace("CATEGORY_", "").lower()
                    break

            normalized = {
                "message_id": msg_id,
                "thread_id": full_msg.get("threadId"),
                "from": header_map.get("from"),
                "to": header_map.get("to"),
                "subject": header_map.get("subject"),
                "snippet": full_msg.get("snippet"),
                "received_at": full_msg.get("internalDate"),
                "labels": labels,
                "category": category,
                "permalink": f"https://mail.google.com/mail/u/0/#all/{msg_id}",
            }
            email_data.append(normalized)

        return email_data

    except Exception as e:
        logger.error(f"Failed to fetch Gmail messages: {e}")
        raise
