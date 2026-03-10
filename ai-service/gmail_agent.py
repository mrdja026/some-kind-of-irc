import json
import json
import logging
from typing import Any, Dict, List, Optional

from config import settings

try:
    from crewai import Agent, Crew, LLM, Process, Task
except Exception:
    Agent = Crew = LLM = Process = Task = None

logger = logging.getLogger(__name__)

MODEL_NAME = "claude-3-haiku-20240307"


class GmailAgent:
    def __init__(self, api_key: str):
        self.api_key = api_key
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

    def _format_email_context(self, emails: List[Dict[str, Any]]) -> str:
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

    async def generate_followup_questions(
        self,
        emails: List[Dict[str, Any]],
        interest: str = "",
        previous_answers: Optional[List[str]] = None,
        question_count: int = 2,
    ) -> List[str]:
        previous_answers = previous_answers or []
        question_count = max(question_count, 1)
        email_context = self._format_email_context(emails)
        prompt = (
            "You are helping a user filter their Gmail inbox based on the emails below.\n"
            f"User interest (if provided): {interest}\n"
            f"Previous answers: {json.dumps(previous_answers)}\n\n"
            f"Emails (raw HTML allowed):\n{email_context}\n\n"
            f"Generate exactly {question_count} short, distinct question(s) to clarify what matters most.\n"
            "Return ONLY a JSON array of strings."
        )

        try:
            llm = self._ensure_llm()
            interviewer = Agent(
                role="Gmail Follow-up Interviewer",
                goal="Ask concise follow-up questions to refine Gmail summaries.",
                backstory=(
                    "You are an expert inbox assistant who asks precise questions."
                ),
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )
            output = self._run_task(
                interviewer,
                prompt,
                "JSON array with exactly 2 questions.",
            )
            return self._clean_and_parse_json(output)
        except Exception as exc:
            logger.error(f"Failed to generate questions: {exc}")
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
        if not emails:
            return {
                "summary_a": "No unread discovery emails found.",
                "summary_b": "No unread discovery emails found.",
            }

        email_text = self._format_email_context(emails)
        context = (
            f"User interest: {interest}\n"
            f"User context: {json.dumps(answers)}\n\n"
            f"Emails:\n{email_text}"
        )

        try:
            llm = self._ensure_llm()
            action_agent = Agent(
                role="Action Summary Analyst",
                goal="Extract actionable items, deadlines, and required responses.",
                backstory="You prioritize tasks and obligations in email.",
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )
            insight_agent = Agent(
                role="Insight Summary Analyst",
                goal="Summarize key updates, trends, and information.",
                backstory="You extract meaningful insights from updates and newsletters.",
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )

            action_prompt = (
                f"{context}\n\n"
                "Create Summary A focused strictly on ACTIONABLE items.\n"
                'Return ONLY JSON: {"summary_a": '
                '"..."}'
            )
            insight_prompt = (
                f"{context}\n\n"
                "Create Summary B focused strictly on INSIGHTS and key updates.\n"
                'Return ONLY JSON: {"summary_b": '
                '"..."}'
            )

            action_output = self._run_task(
                action_agent,
                action_prompt,
                "JSON object with summary_a string.",
            )
            insight_output = self._run_task(
                insight_agent,
                insight_prompt,
                "JSON object with summary_b string.",
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
        if not emails:
            return {
                "final_summary": "No unread discovery emails found.",
                "top_email_ids": [],
                "reasoning": "There were no unread discovery emails to summarize.",
            }

        try:
            llm = self._ensure_llm()
            triage_agent = Agent(
                role="Inbox Triage Specialist",
                goal="Classify emails by relevance and urgency for the user.",
                backstory="You quickly triage inboxes to highlight what matters.",
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )
            judge_agent = Agent(
                role="Gmail Summary Judge",
                goal="Select the best summary and rank the most relevant emails.",
                backstory="You combine summaries and classifications into a final report.",
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )

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
            classification_output = self._run_task(
                triage_agent,
                triage_prompt,
                "JSON object with classified_emails list.",
            )
            classification = self._clean_and_parse_json(classification_output)

            judge_prompt = (
                f"User interest: {interest}\n"
                f"User context: {json.dumps(answers)}\n\n"
                f"Summary A (Action): {summary_a}\n"
                f"Summary B (Insight): {summary_b}\n\n"
                f"Classified emails: {json.dumps(classification)}\n\n"
                f"Email list: {self._email_selection_payload(emails)}\n\n"
                "Choose the best summary style or merge them.\n"
                "Select the top 5 message_ids.\n"
                "Return ONLY JSON with keys final_summary, top_email_ids, reasoning."
            )
            judge_output = self._run_task(
                judge_agent,
                judge_prompt,
                "JSON object with final_summary, top_email_ids, reasoning.",
            )
            return self._clean_and_parse_json(judge_output)
        except Exception as exc:
            logger.error(f"Failed to judge summaries: {exc}")
            return {
                "final_summary": f"{summary_a}\n\n{summary_b}",
                "top_email_ids": [],
                "reasoning": "Fallback due to error.",
            }
