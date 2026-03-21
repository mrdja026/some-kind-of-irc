"""Google ADK Gmail Agent implementation.

Mirrors the CrewAI GmailAgent interface for A/B testing.
Uses Google ADK with LiteLLM for Claude support.
All prompts, roles, goals, and backstories are IDENTICAL to CrewAI.
"""

import json
import logging
from typing import Any, Dict, List, Optional

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

# Model hardcoded to match CrewAI implementation
MODEL_NAME = "claude-3-haiku-20240307"


class GmailAgentADK:
    """Google ADK-based Gmail agent mirroring CrewAI GmailAgent interface."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.model = f"anthropic/{MODEL_NAME}"
        self._session_service = None

    def _ensure_session_service(self):
        """Initialize session service if needed."""
        if self._session_service is None:
            if InMemorySessionService is None:
                raise RuntimeError("Google ADK is not installed.")
            self._session_service = InMemorySessionService()
        return self._session_service

    def _clean_and_parse_json(self, text: str) -> Any:
        """Parse JSON from LLM response, handling markdown code blocks.

        Identical to CrewAI gmail_agent.py lines 43-69.
        """
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

    def _format_email_context(self, emails: List[Dict[str, Any]]) -> str:
        """Format emails for prompt context.

        Identical to CrewAI gmail_agent.py lines 71-85.
        """
        lines = []
        for email in emails:
            body = email.get("body") or email.get("snippet") or ""
            lines.append(
                "\n".join(
                    [
                        f"- Message ID: {email.get('message_id')}",
                        f"  From: {email.get('from')}",
                        f"  Subject: {email.get('subject')}",
                        f"  Body: {body}",
                    ]
                )
            )
        return "\n".join(lines)

    def _email_selection_payload(self, emails: List[Dict[str, Any]]) -> str:
        """Create trimmed email payload for selection.

        Identical to CrewAI gmail_agent.py lines 87-97.
        """
        trimmed = [
            {
                "message_id": email.get("message_id"),
                "subject": email.get("subject"),
                "from": email.get("from"),
                "received_at": email.get("received_at"),
            }
            for email in emails
        ]
        return json.dumps(trimmed)

    async def _run_agent(
        self,
        agent_name: str,
        role: str,
        goal: str,
        backstory: str,
        user_message: str,
    ) -> str:
        """Run an ADK agent and return the text response.

        Similar to calendar_agent.py:215-277 but adapted for Gmail.
        """
        if Agent is None or Runner is None or LiteLlm is None:
            raise RuntimeError("Google ADK is not installed.")

        session_service = self._ensure_session_service()

        # Create LiteLLM model wrapper for Claude
        model = LiteLlm(model=self.model)

        # Create instruction from role, goal, and backstory (matching CrewAI agent structure)
        instruction = f"""You are a {role}.

Goal: {goal}

Backstory: {backstory}

Follow the user's instructions precisely and return ONLY the requested JSON format."""

        # Create agent with instruction
        agent = Agent(
            model=model,
            name=agent_name,
            instruction=instruction,
            tools=[],
        )

        # Create runner
        runner = Runner(
            agent=agent,
            app_name="gmail_adk",
            session_service=session_service,
        )

        # Generate unique session/user IDs for this request
        import uuid

        user_id = f"user_{uuid.uuid4().hex[:8]}"
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Create session
        session = await session_service.create_session(
            app_name="gmail_adk",
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
                    app_name="gmail_adk",
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception as exc:
                logger.warning("Failed to delete gmail ADK session: %s", exc)

    async def generate_followup_questions(
        self,
        emails: List[Dict[str, Any]],
        interest: str = "",
        previous_answers: Optional[List[str]] = None,
        question_count: int = 2,
    ) -> List[str]:
        """Generate follow-up questions for Gmail summarization.

        Prompts identical to CrewAI gmail_agent.py lines 123-129.
        Agent role/goal/backstory identical to lines 134-139.
        Fallback identical to lines 152-156.
        """
        previous_answers = previous_answers or []
        question_count = max(question_count, 1)
        email_context = self._format_email_context(emails)

        # Prompt identical to CrewAI lines 123-129
        prompt = (
            "You are helping a user filter their Gmail inbox based on the emails below.\n"
            f"User interest (if provided): {interest}\n"
            f"Previous answers: {json.dumps(previous_answers)}\n\n"
            f"Emails (raw HTML allowed):\n{email_context}\n\n"
            f"Generate exactly {question_count} short, distinct question(s) to clarify what matters most.\n"
            "Return ONLY a JSON array of strings."
        )

        try:
            output = await self._run_agent(
                agent_name="gmail_follow_up_interviewer",
                # Role, goal, backstory identical to CrewAI lines 135-138
                role="Gmail Follow-up Interviewer",
                goal="Ask concise follow-up questions to refine Gmail summaries.",
                backstory="You are an expert inbox assistant who asks precise questions.",
                user_message=prompt,
            )
            return self._clean_and_parse_json(output)
        except Exception as exc:
            logger.error(f"Failed to generate questions: {exc}")
            # Fallback identical to CrewAI lines 152-156
            fallback = [
                f"What specific topics within {interest or 'these emails'} matter most?",
                "Are you looking for newsletters, personal updates, or transactional emails?",
            ]
            return fallback[: max(question_count, 1)]

    async def generate_summaries(
        self,
        emails: List[Dict[str, Any]],
        interest: str,
        answers: List[str],
    ) -> Dict[str, str]:
        """Generate dual summaries (action + insight).

        Prompts identical to CrewAI gmail_agent.py lines 196-207.
        Agent roles/goals/backstories identical to lines 179-194.
        """
        if not emails:
            return {
                "summary_a": "No unread discovery emails found.",
                "summary_b": "No unread discovery emails found.",
            }

        email_text = self._format_email_context(emails)
        context = (
            f"User interest: {interest}\n"
            f"User context: {json.dumps(answers)}\n"
            "Emails below are already scoped to discovery emails relevant to the user's interest.\n\n"
            f"Emails:\n{email_text}"
        )

        try:
            # Action prompt identical to CrewAI lines 196-201
            action_prompt = (
                f"{context}\n\n"
                "Create Summary A focused strictly on ACTIONABLE items.\n"
                'Return ONLY JSON: {"summary_a": '
                '"..."}'
            )

            # Insight prompt identical to CrewAI lines 202-207
            insight_prompt = (
                f"{context}\n\n"
                "Create Summary B focused strictly on INSIGHTS and key updates.\n"
                'Return ONLY JSON: {"summary_b": '
                '"..."}'
            )

            # Action agent - role/goal/backstory identical to CrewAI lines 179-186
            action_output = await self._run_agent(
                agent_name="action_summary_analyst",
                role="Action Summary Analyst",
                goal="Extract actionable items, deadlines, and required responses.",
                backstory="You prioritize tasks and obligations in email.",
                user_message=action_prompt,
            )

            # Insight agent - role/goal/backstory identical to CrewAI lines 187-194
            insight_output = await self._run_agent(
                agent_name="insight_summary_analyst",
                role="Insight Summary Analyst",
                goal="Summarize key updates, trends, and information.",
                backstory="You extract meaningful insights from updates and newsletters.",
                user_message=insight_prompt,
            )

            summary_a = self._clean_and_parse_json(action_output).get("summary_a")
            summary_b = self._clean_and_parse_json(insight_output).get("summary_b")

            return {
                "summary_a": summary_a or "Error generating action summary.",
                "summary_b": summary_b or "Error generating insight summary.",
            }
        except Exception as exc:
            logger.error(f"Failed to generate summaries: {exc}")
            return {
                "summary_a": "Error generating action summary.",
                "summary_b": "Error generating insight summary.",
            }

    async def judge_and_rank(
        self,
        emails: List[Dict[str, Any]],
        summary_a: str,
        summary_b: str,
        interest: str,
        answers: List[str],
    ) -> Dict[str, Any]:
        """Judge summaries and rank emails.

        Prompts identical to CrewAI gmail_agent.py lines 268-294.
        Agent roles/goals/backstories identical to lines 251-266.
        """
        if not emails:
            return {
                "final_summary": "No unread discovery emails found.",
                "top_email_ids": [],
                "reasoning": "There were no unread discovery emails to summarize.",
            }

        try:
            # Triage prompt identical to CrewAI lines 268-277
            triage_prompt = (
                f"User interest: {interest}\n"
                f"User context: {json.dumps(answers)}\n\n"
                f"Emails:\n{self._format_email_context(emails)}\n\n"
                "Classify each email with relevance (high/medium/low) and urgency "
                "(urgent/soon/whenever).\n"
                'Return ONLY JSON: {"classified_emails": [{"message_id": '
                '"...", "relevance": "...", '
                '"urgency": "...", "reason": "..."}]}'
            )

            # Triage agent - role/goal/backstory identical to CrewAI lines 251-258
            classification_output = await self._run_agent(
                agent_name="inbox_triage_specialist",
                role="Inbox Triage Specialist",
                goal="Classify emails by relevance and urgency for the user.",
                backstory="You quickly triage inboxes to highlight what matters.",
                user_message=triage_prompt,
            )
            classification = self._clean_and_parse_json(classification_output)

            # Judge prompt identical to CrewAI lines 285-294
            judge_prompt = (
                f"User interest: {interest}\n"
                f"User context: {json.dumps(answers)}\n\n"
                "Emails provided are already scoped to discovery emails relevant to the user's interest.\n\n"
                f"Summary A (Action): {summary_a}\n"
                f"Summary B (Insight): {summary_b}\n\n"
                f"Classified emails: {json.dumps(classification)}\n\n"
                f"Email list: {self._email_selection_payload(emails)}\n\n"
                "Choose the best summary style or merge them.\n"
                "Select the top 5 message_ids.\n"
                "Return ONLY JSON with keys final_summary, top_email_ids, reasoning. "
                "Reasoning must be a single string (not an object)."
            )

            # Judge agent - role/goal/backstory identical to CrewAI lines 259-266
            judge_output = await self._run_agent(
                agent_name="gmail_summary_judge",
                role="Gmail Summary Judge",
                goal="Select the best summary and rank the most relevant emails.",
                backstory="You combine summaries and classifications into a final report.",
                user_message=judge_prompt,
            )
            parsed = self._clean_and_parse_json(judge_output)
            if not isinstance(parsed, dict):
                return {
                    "final_summary": f"{summary_a}\n\n{summary_b}",
                    "top_email_ids": [],
                    "reasoning": "Fallback: LLM returned unexpected format.",
                }

            final_summary = parsed.get("final_summary", f"{summary_a}\n\n{summary_b}")
            if isinstance(final_summary, dict):
                for key in ("summary", "text", "content", "final_summary"):
                    value = final_summary.get(key)
                    if isinstance(value, str):
                        final_summary = value
                        break
                else:
                    final_summary = json.dumps(final_summary)
            elif not isinstance(final_summary, str):
                final_summary = str(final_summary)

            top_email_ids = parsed.get("top_email_ids", [])
            if isinstance(top_email_ids, dict):
                top_email_ids = list(top_email_ids.keys())
            elif isinstance(top_email_ids, str):
                top_email_ids = [top_email_ids]
            elif not isinstance(top_email_ids, list):
                top_email_ids = []
            top_email_ids = [str(item) for item in top_email_ids if item is not None]

            reasoning = parsed.get("reasoning", "")
            if isinstance(reasoning, dict):
                if reasoning:
                    lines = []
                    for key, value in reasoning.items():
                        if isinstance(value, str):
                            lines.append(f"{key}: {value}")
                        else:
                            lines.append(f"{key}: {json.dumps(value)}")
                    reasoning = "\n".join(lines)
                else:
                    reasoning = ""
            elif not isinstance(reasoning, str):
                reasoning = str(reasoning)

            return {
                "final_summary": final_summary,
                "top_email_ids": top_email_ids,
                "reasoning": reasoning,
            }
        except Exception as exc:
            logger.error(f"Failed to judge summaries: {exc}")
            return {
                "final_summary": f"{summary_a}\n\n{summary_b}",
                "top_email_ids": [],
                "reasoning": "Fallback due to error.",
            }
