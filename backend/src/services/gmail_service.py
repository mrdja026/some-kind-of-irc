import base64
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


def _decode_body(data: str) -> str:
    """Decode base64url encoded body data."""
    try:
        if not data:
            return ""
        # Fix padding if necessary
        pad = len(data) % 4
        if pad:
            data += "=" * (4 - pad)
        return base64.urlsafe_b64decode(data).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to decode email body: {e}")
        return ""


def _extract_body(payload: Dict[str, Any]) -> str:
    """Recursively extract text/plain body from payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                body += _decode_body(part.get("body", {}).get("data", ""))
            elif "parts" in part:
                body += _extract_body(part)
    elif payload.get("mimeType") == "text/plain":
        body = _decode_body(payload.get("body", {}).get("data", ""))
    return body


async def fetch_latest_emails(
    db: Session, user_id: int, max_results: int = 10
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
            # Fetch full message to get body
            full_msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )

            payload = full_msg.get("payload", {})
            headers = payload.get("headers", [])
            header_map = {h["name"].lower(): h["value"] for h in headers}

            # Map category from labels
            labels = full_msg.get("labelIds", [])
            category = "primary"
            for label in labels:
                if label.startswith("CATEGORY_"):
                    category = label.replace("CATEGORY_", "").lower()
                    break
            
            # Extract body
            body_text = _extract_body(payload)
            if not body_text:
                # Fallback to snippet if body extraction fails
                body_text = full_msg.get("snippet", "")
            
            # Truncate body if excessively long (e.g., > 2000 chars) to save tokens
            if len(body_text) > 2000:
                body_text = body_text[:2000] + "... [truncated]"

            normalized = {
                "message_id": msg_id,
                "thread_id": full_msg.get("threadId"),
                "from": header_map.get("from"),
                "to": header_map.get("to"),
                "subject": header_map.get("subject"),
                "snippet": full_msg.get("snippet"),
                "body": body_text,
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
