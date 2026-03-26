import json
import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config import settings

try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.models.lite_llm import LiteLlm
    from google.genai import types
except ImportError:
    Agent = Runner = InMemorySessionService = LiteLlm = types = None

logger = logging.getLogger(__name__)

MAX_FOLLOWUP_QUESTIONS = 5
MODEL_FAMILY = "claude-3-haiku-20240307"

REQUIRED_FIELDS = [
    "claim_id",
    "policy_id",
    "status",
    "claim_type",
    "loss_date",
    "reported_date",
    "insured",
    "policy",
    "claim_intake",
    "documents",
    "adjuster_notes",
    "coverage_review",
    "resolution",
    "conversation_seed_questions",
]

KNOWN_STATUSES = {
    "new",
    "pending_documents",
    "investigating",
    "coverage_review",
    "reopened",
    "paid",
    "partially_paid",
    "denied",
    "closed_no_payment",
}


def _clean_and_parse_json(text: str) -> Any:
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


def _normalize_question_text(text: str) -> Optional[str]:
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    if cleaned.lower().startswith("question:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    if cleaned.startswith("- "):
        cleaned = cleaned[2:].strip()
    if cleaned.startswith("*"):
        cleaned = cleaned.lstrip("* ").strip()
    if not cleaned:
        return None
    return cleaned.splitlines()[0].strip()


def _extract_followup_question(text: str) -> Optional[str]:
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.upper() in {"NONE", "NO_FOLLOWUP", "NO FOLLOWUP", "NO FOLLOW-UP"}:
        return None
    if stripped.startswith("{"):
        try:
            parsed = _clean_and_parse_json(stripped)
            if isinstance(parsed, dict):
                candidate = parsed.get("question") or parsed.get("followup")
                return (
                    _normalize_question_text(candidate)
                    if isinstance(candidate, str)
                    else None
                )
        except Exception:
            pass
    return _normalize_question_text(stripped)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _build_token_cost(input_text: str, output_text: str) -> Dict[str, Any]:
    input_tokens = _estimate_tokens(input_text)
    output_tokens = _estimate_tokens(output_text)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated": True,
    }


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _get_nested_value(payload: Any, path: List[str]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _collect_negative_numbers(payload: Any, path: str = "") -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}" if path else key
            issues.extend(_collect_negative_numbers(value, next_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            next_path = f"{path}[{index}]"
            issues.extend(_collect_negative_numbers(value, next_path))
    elif isinstance(payload, (int, float)):
        if payload < 0:
            issues.append(
                {
                    "code": "negative_value",
                    "field": path or "value",
                    "message": f"Negative value detected at {path}.",
                }
            )
    return issues


def status_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    status_value = payload.get("status")
    status_ok = True
    issues: List[Dict[str, str]] = []

    if not status_value or not isinstance(status_value, str):
        status_ok = False
        issues.append(
            {
                "code": "missing_status",
                "field": "status",
                "message": "Claim status is missing or empty.",
            }
        )
    elif status_value not in KNOWN_STATUSES:
        status_ok = False
        issues.append(
            {
                "code": "unknown_status",
                "field": "status",
                "message": "Claim status is not a known value.",
            }
        )

    return {
        "status": status_value,
        "status_ok": status_ok,
        "issues": issues,
    }


def truth_check_claim(payload: Any) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    summary_ok = True
    timeline_ok = True
    claim_valid = isinstance(payload, dict)
    status_ok = True
    status_value = None

    if not claim_valid:
        return {
            "summary_ok": False,
            "timeline_ok": False,
            "is_off": True,
            "issues": [
                {
                    "code": "invalid_claim",
                    "field": "claim",
                    "message": "Claim payload is not a JSON object.",
                }
            ],
            "claim_valid": False,
        }

    for field in REQUIRED_FIELDS:
        if field not in payload:
            issues.append(
                {
                    "code": "missing_field",
                    "field": field,
                    "message": f"Required field '{field}' is missing.",
                }
            )

    status_result = status_check(payload)
    status_ok = bool(status_result.get("status_ok", True))
    status_value = status_result.get("status")
    issues.extend(status_result.get("issues") or [])

    summary = _get_nested_value(payload, ["claim_intake", "summary"])
    cause = _get_nested_value(payload, ["claim_intake", "cause_of_loss"])
    if not summary or not isinstance(summary, str):
        summary_ok = False
        issues.append(
            {
                "code": "missing_summary",
                "field": "claim_intake.summary",
                "message": "Claim summary is missing or empty.",
            }
        )
    if not cause or not isinstance(cause, str):
        summary_ok = False
        issues.append(
            {
                "code": "missing_cause",
                "field": "claim_intake.cause_of_loss",
                "message": "Cause of loss is missing or empty.",
            }
        )

    loss_date = _parse_date(payload.get("loss_date"))
    reported_date = _parse_date(payload.get("reported_date"))
    if not loss_date or not reported_date:
        timeline_ok = False
        issues.append(
            {
                "code": "invalid_dates",
                "field": "loss_date/reported_date",
                "message": "Loss date or reported date is missing or invalid.",
            }
        )
    elif loss_date > reported_date:
        timeline_ok = False
        issues.append(
            {
                "code": "loss_after_report",
                "field": "loss_date",
                "message": "Loss date occurs after the reported date.",
            }
        )

    resolution_date = _parse_date(
        _get_nested_value(payload, ["resolution", "resolution_date"])
    )
    if resolution_date and reported_date and resolution_date < reported_date:
        timeline_ok = False
        issues.append(
            {
                "code": "resolution_before_report",
                "field": "resolution.resolution_date",
                "message": "Resolution date occurs before the reported date.",
            }
        )

    policy_effective = _parse_date(
        _get_nested_value(payload, ["policy", "effective_date"])
    )
    policy_expiration = _parse_date(
        _get_nested_value(payload, ["policy", "expiration_date"])
    )
    if loss_date and policy_effective and loss_date < policy_effective:
        timeline_ok = False
        issues.append(
            {
                "code": "loss_before_policy",
                "field": "policy.effective_date",
                "message": "Loss date occurs before policy effective date.",
            }
        )
    if loss_date and policy_expiration and loss_date > policy_expiration:
        timeline_ok = False
        issues.append(
            {
                "code": "loss_after_policy",
                "field": "policy.expiration_date",
                "message": "Loss date occurs after policy expiration date.",
            }
        )

    resolution = payload.get("resolution") or {}
    gross = resolution.get("gross_settlement_eur")
    deductible = resolution.get("deductible_eur")
    net = resolution.get("net_payment_eur")
    if all(isinstance(value, (int, float)) for value in [gross, deductible, net]):
        expected_net = gross - deductible
        if abs(expected_net - net) > 0:
            issues.append(
                {
                    "code": "net_payment_mismatch",
                    "field": "resolution.net_payment_eur",
                    "message": "Net payment does not match gross minus deductible.",
                }
            )

    outcome = resolution.get("outcome")
    if isinstance(net, (int, float)) and outcome in ["denied", "closed_no_payment"]:
        if net > 0:
            issues.append(
                {
                    "code": "payment_with_denial",
                    "field": "resolution.outcome",
                    "message": "Net payment is positive despite a denial outcome.",
                }
            )

    coverage_decision = _get_nested_value(payload, ["coverage_review", "decision"])
    if coverage_decision == "not_covered" and outcome in ["paid", "partially_paid"]:
        issues.append(
            {
                "code": "coverage_conflict",
                "field": "coverage_review.decision",
                "message": "Coverage decision conflicts with paid outcome.",
            }
        )

    issues.extend(_collect_negative_numbers(payload))

    return {
        "summary_ok": summary_ok,
        "timeline_ok": timeline_ok,
        "status_ok": status_ok,
        "status": status_value,
        "is_off": bool(issues),
        "issues": issues,
        "claim_valid": True,
    }


def _issue_to_question(issue: Dict[str, str]) -> Optional[str]:
    code = issue.get("code")
    if code == "net_payment_mismatch":
        return (
            "Can you confirm how the net payment was calculated based on the gross "
            "settlement and deductible?"
        )
    if code in {"loss_after_report", "resolution_before_report"}:
        return "Can you confirm the correct sequence of loss, report, and resolution dates?"
    if code == "loss_before_policy" or code == "loss_after_policy":
        return "Can you confirm the loss date relative to the policy effective and expiration dates?"
    if code == "payment_with_denial":
        return "Should a payment have been issued despite the denial outcome?"
    if code == "coverage_conflict":
        return "Can you clarify the coverage decision versus the paid outcome?"
    if code == "missing_summary" or code == "missing_cause":
        return "Can you clarify the loss summary and cause of loss?"
    if code == "missing_field":
        field = issue.get("field", "the claim")
        return f"Can you provide the missing field {field}?"
    if code in {"missing_status", "unknown_status"}:
        return "Can you confirm the claim status?"
    if code == "negative_value":
        field = issue.get("field", "a value")
        return f"Can you confirm why {field} is negative?"
    return None


def select_followup_question(
    payload: Any,
    issues: List[Dict[str, str]],
    history: List[Dict[str, str]],
    question_count: int,
    asked_questions: Optional[List[str]] = None,
) -> Optional[str]:
    if question_count >= MAX_FOLLOWUP_QUESTIONS:
        return None

    used_questions = set()
    for entry in history:
        question = entry.get("question") if isinstance(entry, dict) else None
        normalized = _normalize_question_text(question or "")
        if normalized:
            used_questions.add(normalized)
        if isinstance(question, str) and question.strip():
            used_questions.add(question.strip())

    for asked in asked_questions or []:
        normalized = _normalize_question_text(asked)
        if normalized:
            used_questions.add(normalized)
        if isinstance(asked, str) and asked.strip():
            used_questions.add(asked.strip())

    for issue in issues:
        candidate = _issue_to_question(issue)
        if candidate and candidate not in used_questions:
            return candidate

    return None


class ClaimsAgentADK:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.model = settings.ADK_MODEL or f"anthropic/{MODEL_FAMILY}"
        self._session_service = None

    def _ensure_session_service(self):
        if self._session_service is None:
            if InMemorySessionService is None:
                raise RuntimeError("Google ADK is not installed.")
            self._session_service = InMemorySessionService()
        return self._session_service

    async def _run_agent(
        self, agent_name: str, instruction: str, user_message: str
    ) -> str:
        if Agent is None or Runner is None or LiteLlm is None:
            raise RuntimeError("Google ADK is not installed.")

        session_service = self._ensure_session_service()
        model = LiteLlm(model=self.model)

        agent = Agent(
            model=model,
            name=agent_name,
            instruction=instruction,
            tools=[],
        )

        runner = Runner(
            agent=agent,
            app_name="claims_qa",
            session_service=session_service,
        )

        import uuid

        user_id = f"user_{uuid.uuid4().hex[:8]}"
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        await session_service.create_session(
            app_name="claims_qa",
            user_id=user_id,
            session_id=session_id,
        )

        content = types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        )

        response_text = ""
        try:
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
                    app_name="claims_qa",
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception as exc:
                logger.warning("Failed to delete claims ADK session: %s", exc)

    def truth_check(self, payload: Any) -> Dict[str, Any]:
        return truth_check_claim(payload)

    async def generate_candidate_answer(
        self,
        payload: Any,
        question: str,
        history: List[Dict[str, str]],
        tool_output: Dict[str, Any],
        variant: str,
    ) -> Tuple[str, Dict[str, Any]]:
        claim_json = json.dumps(payload, ensure_ascii=True, indent=2)
        history_json = json.dumps(history, ensure_ascii=True)
        tool_json = json.dumps(tool_output, ensure_ascii=True)

        if variant == "A":
            style = (
                "Answer in 2-4 concise sentences. Cite claim fields when possible. "
                "If information is missing, say 'Not enough info in claim.'"
            )
        else:
            style = (
                "Answer in 2-4 bullet points with field references. "
                "If information is missing, say 'Not enough info in claim.'"
            )

        instruction = (
            "You are a claims analyst. Use only the provided claim JSON and tool outputs. "
            "Do not use outside knowledge or assumptions."
        )

        user_message = (
            f"Claim JSON:\n{claim_json}\n\n"
            f"Tool outputs:\n{tool_json}\n\n"
            f"Conversation history (Q/A):\n{history_json}\n\n"
            f"Question: {question}\n\n"
            f"{style}"
        )

        start = time.perf_counter()
        try:
            output = await self._run_agent(
                agent_name=f"claims_candidate_{variant.lower()}",
                instruction=instruction,
                user_message=user_message,
            )
        except Exception as exc:
            logger.error("Claims candidate %s failed: %s", variant, exc)
            output = "Not enough info in claim to answer this question."
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        metrics = {
            "token_cost": _build_token_cost(user_message, output),
            "inference_time_ms": elapsed_ms,
        }
        return output.strip(), metrics

    async def judge_answers(
        self,
        question: str,
        tool_output: Dict[str, Any],
        answer_a: str,
        answer_b: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        tool_json = json.dumps(tool_output, ensure_ascii=True)
        instruction = (
            "You are a claims QA judge. Use the rubric below and select the best response.\n"
            "Rubric:\n"
            "1) Grounded in claim JSON and tool outputs.\n"
            "2) Directly answers the question.\n"
            "3) Notes issues when tool outputs show discrepancies.\n"
            "4) Clear and concise.\n\n"
            'Return ONLY JSON: {"winner": 1|2, "reasoning": "...", "done": true|false}. '
            "Set done=true only when the question is fully answered and no follow-up is needed. "
            "Set done=false when a follow-up would clarify or deepen the answer. "
            "Reasoning must be 1-2 sentences."
        )

        user_message = (
            f"Question: {question}\n\n"
            f"Tool outputs:\n{tool_json}\n\n"
            f"Response 1:\n{answer_a}\n\n"
            f"Response 2:\n{answer_b}\n"
        )

        start = time.perf_counter()
        try:
            output = await self._run_agent(
                agent_name="claims_judge",
                instruction=instruction,
                user_message=user_message,
            )
            parsed = _clean_and_parse_json(output)
            if not isinstance(parsed, dict):
                raise ValueError("Judge output is not an object")
            if "done" not in parsed:
                parsed["done"] = False
        except Exception as exc:
            logger.error("Claims judge failed: %s", exc)
            parsed = {
                "winner": 1,
                "reasoning": "Selected response 1 by default.",
                "done": False,
            }
            output = json.dumps(parsed)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        metrics = {
            "token_cost": _build_token_cost(user_message, output),
            "inference_time_ms": elapsed_ms,
        }
        return parsed, metrics

    async def generate_followup_candidate(
        self,
        payload: Any,
        question: str,
        history: List[Dict[str, str]],
        asked_questions: List[str],
        tool_output: Dict[str, Any],
        variant: str,
    ) -> Tuple[Optional[str], Dict[str, Any], str]:
        claim_json = json.dumps(payload, ensure_ascii=True, indent=2)
        history_json = json.dumps(history, ensure_ascii=True)
        asked_json = json.dumps(asked_questions, ensure_ascii=True)
        tool_json = json.dumps(tool_output, ensure_ascii=True)

        if variant == "A":
            focus = (
                "Focus on clarifying missing facts, timelines, or decision status. "
                "Prefer questions about dates, status, or unresolved steps."
            )
        else:
            focus = (
                "Focus on clarifying financials, coverage, or documentation details. "
                "Prefer questions about amounts, coverage limits, or key documents."
            )

        instruction = (
            "You generate ONE follow-up question for a claim Q&A. "
            "Use the claim JSON, tool outputs, history, and asked questions. "
            "Do not ask for fields already present in the claim JSON unless clarification is needed. "
            "Avoid repeating any prior questions. "
            "Avoid moral or blame framing (no 'who is wronged' questions). "
            "Use neutral factual wording. "
            "Return ONLY the question text, or 'NONE' if no follow-up is needed."
        )

        user_message = (
            f"Claim JSON:\n{claim_json}\n\n"
            f"Tool outputs:\n{tool_json}\n\n"
            f"Conversation history (Q/A):\n{history_json}\n\n"
            f"Asked questions:\n{asked_json}\n\n"
            f"Current question: {question}\n\n"
            f"{focus}"
        )

        start = time.perf_counter()
        try:
            output = await self._run_agent(
                agent_name=f"claims_followup_{variant.lower()}",
                instruction=instruction,
                user_message=user_message,
            )
        except Exception as exc:
            logger.error("Claims follow-up candidate %s failed: %s", variant, exc)
            output = "NONE"
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        metrics = {
            "token_cost": _build_token_cost(user_message, output),
            "inference_time_ms": elapsed_ms,
        }
        return _extract_followup_question(output), metrics, output

    async def judge_followup_question(
        self,
        question: str,
        history: List[Dict[str, str]],
        asked_questions: List[str],
        tool_output: Dict[str, Any],
        candidate_a: Optional[str],
        candidate_b: Optional[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        tool_json = json.dumps(tool_output, ensure_ascii=True)
        history_json = json.dumps(history, ensure_ascii=True)
        asked_json = json.dumps(asked_questions, ensure_ascii=True)
        instruction = (
            "You are a claims QA follow-up judge. Select the better follow-up question.\n"
            "Criteria:\n"
            "1) Non-redundant with prior questions.\n"
            "2) Clarifies missing or ambiguous details.\n"
            "3) Grounded in claim JSON and tool outputs.\n"
            "4) Neutral factual wording.\n\n"
            'Return ONLY JSON: {"winner": 1|2, "reasoning": "...", "question": "..."}. '
            "If both are poor or empty, set question to empty string."
        )

        user_message = (
            f"Current question: {question}\n\n"
            f"Tool outputs:\n{tool_json}\n\n"
            f"Conversation history (Q/A):\n{history_json}\n\n"
            f"Asked questions:\n{asked_json}\n\n"
            f"Follow-up 1: {candidate_a or 'NONE'}\n"
            f"Follow-up 2: {candidate_b or 'NONE'}\n"
        )

        start = time.perf_counter()
        try:
            output = await self._run_agent(
                agent_name="claims_followup_judge",
                instruction=instruction,
                user_message=user_message,
            )
            parsed = _clean_and_parse_json(output)
            if not isinstance(parsed, dict):
                raise ValueError("Follow-up judge output is not an object")
        except Exception as exc:
            logger.error("Claims follow-up judge failed: %s", exc)
            parsed = {
                "winner": 1,
                "reasoning": "Selected follow-up 1 by default.",
                "question": candidate_a or "",
            }
            output = json.dumps(parsed)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        metrics = {
            "token_cost": _build_token_cost(user_message, output),
            "inference_time_ms": elapsed_ms,
        }
        return parsed, metrics
