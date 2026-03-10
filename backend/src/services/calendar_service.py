from datetime import datetime
from datetime import datetime, timezone, tzinfo
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from src.models.gmail_token import GmailToken
from src.services.gmail_service import _get_credentials, _refresh_credentials_if_needed


def _normalize_timezone(value: Optional[str]) -> tuple[str, tzinfo]:
    if not value:
        return "UTC", timezone.utc
    try:
        return value, ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return "UTC", timezone.utc


def _parse_iso_datetime(value: str, tzinfo: tzinfo) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime format: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tzinfo)
    return parsed


def create_calendar_event(
    db: Session,
    user_id: int,
    title: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str,
    attendees: Optional[List[str]] = None,
) -> Dict[str, Any]:
    db_token = db.query(GmailToken).filter(GmailToken.user_id == user_id).first()
    if not db_token:
        raise ValueError("Gmail not connected for this user")

    tz_label, tzinfo = _normalize_timezone(timezone)
    start = _parse_iso_datetime(start_datetime, tzinfo)
    end = _parse_iso_datetime(end_datetime, tzinfo)
    if end <= start:
        raise ValueError("End time must be after start time")

    creds = _get_credentials(db_token)
    _refresh_credentials_if_needed(creds, db_token, db)

    service = build("calendar", "v3", credentials=creds)

    event_body: Dict[str, Any] = {
        "summary": title or "Meeting",
        "start": {"dateTime": start.isoformat(), "timeZone": tz_label},
        "end": {"dateTime": end.isoformat(), "timeZone": tz_label},
    }

    cleaned_attendees = [email for email in attendees or [] if email]
    if cleaned_attendees:
        event_body["attendees"] = [{"email": email} for email in cleaned_attendees]

    try:
        created = (
            service.events().insert(calendarId="primary", body=event_body).execute()
        )
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        if status == 400:
            raise ValueError(
                "Calendar event rejected; check date/time format."
            ) from exc
        if status == 403:
            raise ValueError(
                "Calendar access denied; reconnect with calendar scopes."
            ) from exc
        raise

    return {
        "event_id": created.get("id"),
        "html_link": created.get("htmlLink"),
        "summary": created.get("summary"),
    }
