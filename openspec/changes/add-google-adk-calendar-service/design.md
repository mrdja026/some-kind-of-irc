## Context

The frontend `AIChannel.tsx` component already implements an A/B testing UI that allows users to select between "crewAI" and "googleADK" backends. Currently only the CrewAI backend exists (`ai-service/` on port 8003). This change implements the Google ADK backend to enable actual A/B comparison.

The goal is to compare agent frameworks while keeping prompts identical, allowing measurement of:
- Response quality and accuracy
- Latency and performance
- Tool execution reliability
- Cost per request

## Goals / Non-Goals

**Goals:**
- Feature parity with CrewAI calendar agent (`plan_event()`, `create_event()`)
- Identical prompts for consistent A/B comparison
- Independent microservice on port 8004
- Support Claude via LiteLLM integration

**Non-Goals:**
- Gmail agent implementation (calendar only for initial scope)
- Performance optimization (establish baseline first)
- Shared code library (copy dependencies for isolation)

## Decisions

### 1. Google ADK Agent Pattern

**Decision:** Use `google.adk.agents.Agent` with `instruction` parameter for system prompt.

```python
from google.adk.agents import Agent

agent = Agent(
    model="litellm/anthropic/claude-3-haiku-20240307",
    name="calendar_planner",
    instruction=PLAN_EVENT_PROMPT,
    tools=[],  # No tools for planning
)
```

**Rationale:** ADK's Agent class is the direct equivalent of CrewAI's Agent, with `instruction` serving the role of `backstory` + task description.

### 2. LiteLLM for Claude Support

**Decision:** Use LiteLLM model format `litellm/anthropic/claude-3-haiku-20240307`.

**Rationale:** Google ADK doesn't natively support Anthropic Claude. LiteLLM provides a unified interface that ADK can use. The `litellm/` prefix triggers ADK to route through LiteLLM.

**Alternative Considered:** Direct Anthropic API with custom adapter - rejected as more complex.

### 3. Function Tools vs BaseTool

**Decision:** Use plain Python functions with type hints and docstrings.

```python
def create_calendar_event(
    title: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str = "UTC",
    attendees: list[str] = None,
) -> str:
    """Create a calendar event in the user's Google Calendar.
    
    Args:
        title: Event title
        start_datetime: ISO-8601 start datetime
        end_datetime: ISO-8601 end datetime
        timezone: IANA timezone (default: UTC)
        attendees: List of attendee email addresses
    
    Returns:
        JSON string with event_id, html_link, summary
    """
    ...
```

**Rationale:** ADK uses function introspection to generate tool schemas. Docstrings become tool descriptions. This is simpler than CrewAI's Pydantic-based BaseTool pattern.

### 4. Copied Dependencies

**Decision:** Copy `auth.py` and `rate_limiter.py` from `ai-service/` to `ai-service-adk/`.

**Rationale:** 
- Keeps services fully independent
- No cross-service import complications
- Allows ADK service to evolve independently
- Simplifies Docker build context

**Alternative Considered:** Shared library package - rejected as premature abstraction for 2-service scenario.

### 5. Port Assignment

**Decision:** ADK service runs on port 8004.

**Rationale:** Allows both services to run simultaneously for A/B testing. Matches existing port allocation pattern (backend: 8002, ai-service: 8003).

## Architecture

```
┌─────────────────┐
│    Frontend     │
│  AIChannel.tsx  │
│   A/B Toggle    │
└────────┬────────┘
         │
         ▼
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ai-svc  │ │ai-svc  │
│CrewAI  │ │  ADK   │
│ :8003  │ │ :8004  │
└────┬───┘ └───┬────┘
     │         │
     └────┬────┘
          │
          ▼
    ┌───────────┐
    │  Backend  │
    │   :8002   │
    │/auth/cal/ │
    └───────────┘
```

## Prompts (Extracted from CrewAI)

### Plan Event Prompt (calendar_agent.py:225-257)

```python
PLAN_EVENT_PROMPT = '''
You are a calendar assistant. Extract meeting details from the user request 
and any previous answers.

Today (UTC): {today_label}
User request: {request_text}
Previous answers: {previous_answers_json}

Required fields: title, start_datetime, end_datetime.
Timezone is optional (default to UTC). Attendees are optional.
Dates use DD/MM/YYYY, times use 24h HH:MM.
If the user says 'tomorrow', interpret it as the day after today (UTC).
If the user provides a time range like 'between 12-16', 
assume the meeting starts at the first time and lasts 1 hour.
If a reply contains a time alongside words like 'yes', use the time.
If only a time is provided, request the date. If only a date is provided, 
request the time.
If any required field is missing or ambiguous, set needs_clarification=true 
and include missing_fields (date/time/both) plus a single follow-up question.
If all required fields are present, set needs_clarification=false and 
provide a confirmation question that restates the meeting details.

Return ONLY JSON with this structure:
{
  "needs_clarification": true|false,
  "missing_fields": ["date"|"time"],
  "question": "...",
  "event": {
    "title": "...",
    "start_datetime": "YYYY-MM-DDTHH:MM",
    "end_datetime": "YYYY-MM-DDTHH:MM",
    "timezone": "UTC",
    "attendees": ["email@example.com"]
  }
}
'''
```

### Create Event Prompt (calendar_agent.py:331-335)

```python
CREATE_EVENT_PROMPT = '''
Create a calendar event with the following details using the tool.
Event payload: {event_json}

Return ONLY JSON with keys event_id, html_link, summary.
'''
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| ADK API differs from examples | Start minimal, iterate based on actual behavior |
| LiteLLM integration complexity | Test with direct API first as fallback option |
| Prompt behavior differs between frameworks | Log responses for comparison, tune if needed |
| Rate limiting shared state | Each service uses own rate limit key prefix |

## Migration Plan

1. **Phase 1:** Deploy ADK service alongside CrewAI (both running)
2. **Phase 2:** Enable A/B testing for subset of users
3. **Phase 3:** Collect metrics (quality, latency, errors)
4. **Phase 4:** Make data-driven decision on primary backend

## Open Questions

1. Should we add telemetry/logging to compare response quality?
2. Should the frontend persist A/B selection or reset each session?
3. What metrics should we track for comparison (latency, token count, success rate)?
