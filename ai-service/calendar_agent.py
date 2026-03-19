import json
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from config import settings

try:
    from crewai import Agent, Crew, LLM, Process, Task
    from crewai.tools import BaseTool
except Exception:
    Agent = Crew = LLM = Process = Task = BaseTool = None

logger = logging.getLogger(__name__)

MODEL_NAME = "claude-3-haiku-20240307"


def _format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


class CalendarEventToolInput(BaseModel):
    title: str = Field(..., description="Event title")
    start_datetime: str = Field(..., description="ISO-8601 start datetime")
    end_datetime: str = Field(..., description="ISO-8601 end datetime")
    timezone: str = Field("UTC", description="IANA timezone")
    attendees: List[str] = Field(default_factory=list, description="Attendee emails")


class CalendarCreateEventTool(BaseTool):
    name: str = "create_calendar_event"
    description: str = (
        "Create a calendar event in the user's primary Google Calendar using "
        "the provided title, start/end datetime, timezone, and attendees."
    )
    args_schema: type[BaseModel] = CalendarEventToolInput

    def __init__(self, backend_url: str, auth_token: str) -> None:
        super().__init__()
        self._backend_url = backend_url.rstrip("/")
        self._auth_token = auth_token

    def _run(
        self,
        title: str,
        start_datetime: str,
        end_datetime: str,
        timezone: str = "UTC",
        attendees: Optional[List[str]] = None,
    ) -> str:
        if not self._auth_token:
            raise RuntimeError(
                "Missing user session token for calendar event creation."
            )
        payload = {
            "title": title,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "timezone": timezone,
            "attendees": attendees or [],
        }
        headers = {"Cookie": f"access_token={self._auth_token}"}
        response = httpx.post(
            f"{self._backend_url}/auth/calendar/events",
            json=payload,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        return response.text


class CalendarAgent:
    def __init__(self, api_key: str, backend_url: str) -> None:
        self.api_key = api_key
        self.backend_url = backend_url
        self.model = MODEL_NAME
        self._llm: Optional[Any] = None

    def _ensure_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        if (
            LLM is None
            or Agent is None
            or Crew is None
            or Task is None
            or Process is None
        ):
            raise RuntimeError("CrewAI is not installed.")
        if not self.api_key:
            raise RuntimeError("Anthropic API key is missing.")
        self._llm = LLM(
            model=f"anthropic/{self.model}",
            api_key=self.api_key,
            base_url=settings.ANTHROPIC_API_BASE,
        )
        return self._llm

    def _clean_and_parse_json(self, text: str) -> Any:
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

    def _run_task(self, agent: Any, description: str, expected_output: str) -> str:
        task = Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )
        return str(crew.kickoff())

    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
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
        if "date" in missing_fields and "time" in missing_fields:
            return "What date and time should I schedule it? (DD/MM/YYYY HH:MM)"
        if "date" in missing_fields:
            return "What date should I use? (DD/MM/YYYY)"
        if "time" in missing_fields:
            return "What time should I schedule it? (e.g., 14:00)"
        return "Could you clarify the meeting details?"

    def _is_iso_datetime(self, value: str) -> bool:
        if not value:
            return False
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False

    def _resolve_missing_fields(self, result: Dict[str, Any]) -> List[str]:
        missing_fields = result.get("missing_fields") or []
        if isinstance(missing_fields, str):
            missing_fields = [missing_fields]
        missing_fields = [
            field.lower() for field in missing_fields if isinstance(field, str)
        ]
        return missing_fields

        if not resolved_time:
            question = "What time should I schedule it? (e.g., 14:00)"
            return {
                "needs_clarification": True,
                "question": question,
                "event": event,
            }

        start_dt = datetime.combine(resolved_date, resolved_time, tzinfo=timezone.utc)
        duration_minutes = resolved_duration or 60
        if resolved_end_time:
            end_dt = datetime.combine(
                resolved_date, resolved_end_time, tzinfo=timezone.utc
            )
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(minutes=duration_minutes)
        else:
            end_dt = start_dt + timedelta(minutes=duration_minutes)

        event["start_datetime"] = start_dt.isoformat(timespec="minutes")
        event["end_datetime"] = end_dt.isoformat(timespec="minutes")
        event["timezone"] = "UTC"

        summary = event.get("title") or "Meeting"
        question = (
            f"Schedule '{summary}' on {_format_date(resolved_date)} "
            f"at {_format_time(resolved_time)} UTC?"
        )
        return {
            "needs_clarification": False,
            "question": question,
            "event": event,
        }

    async def plan_event(
        self,
        request_text: str,
        previous_answers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        previous_answers = previous_answers or []
        today_label = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        prompt = (
            "You are a calendar assistant. Extract meeting details from the user request "
            "and any previous answers.\n\n"
            f"Today (UTC): {today_label}\n"
            f"User request: {request_text}\n"
            f"Previous answers: {json.dumps(previous_answers)}\n\n"
            "Required fields: title, start_datetime, end_datetime. "
            "Timezone is optional (default to UTC). Attendees are optional.\n"
            "Dates use DD/MM/YYYY, times use 24h HH:MM. "
            "If the user says 'tomorrow', interpret it as the day after today (UTC).\n"
            "If the user provides a time range like 'between 12-16', "
            "assume the meeting starts at the first time and lasts 1 hour.\n"
            "If a reply contains a time alongside words like 'yes', use the time.\n"
            "If only a time is provided, request the date. If only a date is provided, "
            "request the time.\n"
            "If any required field is missing or ambiguous, set needs_clarification=true "
            "and include missing_fields (date/time/both) plus a single follow-up question.\n"
            "If all required fields are present, set needs_clarification=false and "
            "provide a confirmation question that restates the meeting details.\n\n"
            "Return ONLY JSON with this structure:\n"
            "{\n"
            '  "needs_clarification": true|false,\n'
            '  "missing_fields": ["date"|"time"],\n'
            '  "question": "...",\n'
            '  "event": {\n'
            '    "title": "...",\n'
            '    "start_datetime": "YYYY-MM-DDTHH:MM",\n'
            '    "end_datetime": "YYYY-MM-DDTHH:MM",\n'
            '    "timezone": "UTC",\n'
            '    "attendees": ["email@example.com"]\n'
            "  }\n"
            "}\n"
        )

        try:
            llm = self._ensure_llm()
            planner = Agent(
                role="Calendar Planner",
                goal="Extract meeting details and ask clarifying questions.",
                backstory="You schedule meetings and verify details carefully.",
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )
            output = self._run_task(
                planner,
                prompt,
                "JSON object with needs_clarification, question, event.",
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
        if BaseTool is None:
            raise RuntimeError("CrewAI tools are not available.")
        tool = CalendarCreateEventTool(self.backend_url, auth_token)
        llm = self._ensure_llm()
        scheduler = Agent(
            role="Calendar Scheduler",
            goal="Create the calendar event using the provided tool.",
            backstory="You schedule meetings precisely and confirm success.",
            llm=llm,
            tools=[tool],
            allow_delegation=False,
            verbose=False,
        )
        normalized = self._normalize_event(event)
        prompt = (
            "Create a calendar event with the following details using the tool.\n"
            f"Event payload: {json.dumps(normalized)}\n\n"
            "Return ONLY JSON with keys event_id, html_link, summary."
        )
        try:
            output = self._run_task(
                scheduler,
                prompt,
                "JSON object with event_id, html_link, summary.",
            )
            return self._clean_and_parse_json(output)
        except Exception as exc:
            logger.error(f"Failed to create calendar event: {exc}")
            return {
                "event_id": None,
                "html_link": None,
                "summary": normalized.get("title", ""),
            }
