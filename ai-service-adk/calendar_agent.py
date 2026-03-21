"""Google ADK Calendar Agent implementation.

Mirrors the CrewAI CalendarAgent interface for A/B testing.
Uses Google ADK with LiteLLM for Claude support.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from config import settings

# Import Google ADK components
try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.models.lite_llm import LiteLlm
    from google.genai import types
except ImportError:
    Agent = Runner = InMemorySessionService = LiteLlm = types = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts (identical to CrewAI calendar_agent.py:225-257, 331-335)
# ---------------------------------------------------------------------------

PLAN_EVENT_PROMPT = """You are a calendar assistant. Extract meeting details from the user request and any previous answers.

Today (UTC): {today_label}
User request: {request_text}
Previous answers: {previous_answers_json}

Required fields: title, start_datetime, end_datetime.
Timezone is optional (default to UTC). Attendees are optional.
Dates use DD/MM/YYYY, times use 24h HH:MM.
If the user says 'tomorrow', interpret it as the day after today (UTC).
If the user provides a time range like 'between 12-16', assume the meeting starts at the first time and lasts 1 hour.
If a reply contains a time alongside words like 'yes', use the time.
If only a time is provided, request the date. If only a date is provided, request the time.
If any required field is missing or ambiguous, set needs_clarification=true and include missing_fields (date/time/both) plus a single follow-up question.
If all required fields are present, set needs_clarification=false and provide a confirmation question that restates the meeting details.

Return ONLY JSON with this structure:
{{
  "needs_clarification": true|false,
  "missing_fields": ["date"|"time"],
  "question": "...",
  "event": {{
    "title": "...",
    "start_datetime": "YYYY-MM-DDTHH:MM",
    "end_datetime": "YYYY-MM-DDTHH:MM",
    "timezone": "UTC",
    "attendees": ["email@example.com"]
  }}
}}"""


# ---------------------------------------------------------------------------
# Tool function for ADK (plain Python function with docstring)
# ---------------------------------------------------------------------------


def create_calendar_event(
    title: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str = "UTC",
    attendees: list = None,
    backend_url: str = "",
    auth_token: str = "",
) -> str:
    """Create a calendar event in the user's Google Calendar.

    Args:
        title: Event title
        start_datetime: ISO-8601 start datetime
        end_datetime: ISO-8601 end datetime
        timezone: IANA timezone (default: UTC)
        attendees: List of attendee email addresses
        backend_url: Backend URL for calendar API
        auth_token: User's authentication token

    Returns:
        JSON string with event_id, html_link, summary
    """
    if not auth_token:
        return json.dumps(
            {"error": "Missing user session token for calendar event creation."}
        )

    payload = {
        "title": title,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "timezone": timezone,
        "attendees": attendees or [],
    }
    headers = {"Cookie": f"access_token={auth_token}"}

    try:
        response = httpx.post(
            f"{backend_url}/auth/calendar/events",
            json=payload,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        return response.text
    except Exception as exc:
        logger.error(f"Calendar event creation failed: {exc}")
        return json.dumps(
            {
                "error": str(exc),
                "event_id": None,
                "html_link": None,
                "summary": title,
            }
        )


class CalendarAgentADK:
    """Google ADK-based calendar agent mirroring CrewAI CalendarAgent interface."""

    def __init__(self, api_key: str, backend_url: str) -> None:
        self.api_key = api_key
        self.backend_url = backend_url
        self.model = settings.ADK_MODEL
        self._session_service = None

    def _ensure_session_service(self):
        """Initialize session service if needed."""
        if self._session_service is None:
            if InMemorySessionService is None:
                raise RuntimeError("Google ADK is not installed.")
            self._session_service = InMemorySessionService()
        return self._session_service

    def _clean_and_parse_json(self, text: str) -> Any:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        text = text.strip()

        def _try_parse(candidate: str) -> Any:
            return json.loads(candidate, strict=False)

        try:
            return _try_parse(text)
        except json.JSONDecodeError as exc:
            last_error = exc

        for start_char, end_char in (("{", "}"), ("[", "]")):
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                candidate = text[start : end + 1]
                try:
                    return _try_parse(candidate)
                except json.JSONDecodeError as exc:
                    last_error = exc

        raise last_error

    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize event fields, ensuring all required keys exist."""
        attendees = event.get("attendees") or []
        if isinstance(attendees, str):
            attendees = [attendees]
        event["attendees"] = [email for email in attendees if email]
        event["timezone"] = event.get("timezone") or "UTC"
        event["title"] = event.get("title") or ""
        event["start_datetime"] = event.get("start_datetime") or ""
        event["end_datetime"] = event.get("end_datetime") or ""
        return event

    def _missing_fields_question(self, missing_fields: List[str]) -> str:
        """Generate clarification question based on missing fields."""
        if "date" in missing_fields and "time" in missing_fields:
            return "What date and time should I schedule it? (DD/MM/YYYY HH:MM)"
        if "date" in missing_fields:
            return "What date should I use? (DD/MM/YYYY)"
        if "time" in missing_fields:
            return "What time should I schedule it? (e.g., 14:00)"
        return "Could you clarify the meeting details?"

    def _is_iso_datetime(self, value: str) -> bool:
        """Check if value is a valid ISO datetime string."""
        if not value:
            return False
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False

    def _resolve_missing_fields(self, result: Dict[str, Any]) -> List[str]:
        """Extract and normalize missing_fields from LLM response."""
        missing_fields = result.get("missing_fields") or []
        if isinstance(missing_fields, str):
            missing_fields = [missing_fields]
        missing_fields = [
            field.lower() for field in missing_fields if isinstance(field, str)
        ]
        return missing_fields

    async def _run_agent(
        self,
        agent_name: str,
        instruction: str,
        user_message: str,
        tools: list = None,
    ) -> str:
        """Run an ADK agent and return the text response."""
        if Agent is None or Runner is None or LiteLlm is None:
            raise RuntimeError("Google ADK is not installed.")

        session_service = self._ensure_session_service()

        # Create LiteLLM model wrapper for Claude
        model = LiteLlm(model=self.model)

        # Create agent with instruction
        agent = Agent(
            model=model,
            name=agent_name,
            instruction=instruction,
            tools=tools or [],
        )

        # Create runner
        runner = Runner(
            agent=agent,
            app_name="calendar_adk",
            session_service=session_service,
        )

        # Generate unique session/user IDs for this request
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Create session
        session = await session_service.create_session(
            app_name="calendar_adk",
            user_id=user_id,
            session_id=session_id,
        )

        # Create user message content
        content = types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        )

        try:
            # Run agent and collect response
            response_text = ""
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_text += part.text

            return response_text
        finally:
            try:
                await session_service.delete_session(
                    app_name="calendar_adk",
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception as exc:
                logger.warning("Failed to delete calendar ADK session: %s", exc)

    async def plan_event(
        self,
        request_text: str,
        previous_answers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Plan a calendar event by extracting details from user request.

        Args:
            request_text: User's meeting request
            previous_answers: List of previous clarification answers

        Returns:
            Dict with needs_clarification, question, and event fields
        """
        previous_answers = previous_answers or []
        today_label = datetime.now(timezone.utc).strftime("%d/%m/%Y")

        # Format the prompt with context
        prompt = PLAN_EVENT_PROMPT.format(
            today_label=today_label,
            request_text=request_text,
            previous_answers_json=json.dumps(previous_answers),
        )

        try:
            # Run the planning agent
            output = await self._run_agent(
                agent_name="calendar_planner",
                instruction="You schedule meetings and verify details carefully. Extract meeting details and ask clarifying questions when needed.",
                user_message=prompt,
                tools=[],
            )

            result = self._clean_and_parse_json(output)
            event = self._normalize_event(result.get("event", {}))
            missing_fields = self._resolve_missing_fields(result)

            has_start = self._is_iso_datetime(event.get("start_datetime", ""))
            has_end = self._is_iso_datetime(event.get("end_datetime", ""))

            if not has_start or not has_end:
                if "date" not in missing_fields and "time" not in missing_fields:
                    missing_fields = ["date", "time"]

            if missing_fields:
                question = result.get("question") or self._missing_fields_question(
                    missing_fields
                )
                return {
                    "needs_clarification": True,
                    "question": question,
                    "event": event,
                }

            return {
                "needs_clarification": False,
                "question": result.get("question") or "Confirm the meeting details.",
                "event": event,
            }
        except Exception as exc:
            logger.error(f"Failed to plan calendar event: {exc}")
            return {
                "needs_clarification": True,
                "question": "What date and time should I schedule the meeting?",
                "event": {
                    "title": "",
                    "start_datetime": "",
                    "end_datetime": "",
                    "timezone": "UTC",
                    "attendees": [],
                },
            }

    async def create_event(
        self,
        event: Dict[str, Any],
        auth_token: str,
    ) -> Dict[str, Any]:
        """Create a calendar event by calling the backend directly.

        Args:
            event: Event details dict
            auth_token: User's session token

        Returns:
            Dict with event_id, html_link, summary
        """
        normalized = self._normalize_event(event)

        # Call backend directly - no LLM needed for creation.
        # create_calendar_event is sync (required as an ADK tool), so run it
        # in a thread to avoid blocking the async event loop.
        try:
            result_json = await asyncio.to_thread(
                create_calendar_event,
                title=normalized.get("title", ""),
                start_datetime=normalized.get("start_datetime", ""),
                end_datetime=normalized.get("end_datetime", ""),
                timezone=normalized.get("timezone", "UTC"),
                attendees=normalized.get("attendees", []),
                backend_url=self.backend_url,
                auth_token=auth_token,
            )
            return self._clean_and_parse_json(result_json)
        except Exception as exc:
            logger.error(f"Failed to create calendar event: {exc}")
            return {
                "event_id": None,
                "html_link": None,
                "summary": normalized.get("title", ""),
            }
