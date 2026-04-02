import asyncio
import json
import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pydantic import BaseModel, Field

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
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
MODEL_FAMILY = "claude-sonnet-4-5-20241022"


# ---------------------------------------------------------------------------
# Pydantic output schemas for structured LLM responses
# ---------------------------------------------------------------------------


class ClaimsJudgeSchema(BaseModel):
    """Schema enforced on the claims judge LLM output."""

    winner: int = Field(ge=1, le=2, description="1 or 2 — which candidate answer is better")
    reasoning: str = Field(description="1-2 sentence justification for the choice")
    done: bool = Field(
        default=False,
        description="True only when question is definitively answered with no remaining ambiguity",
    )


class ClaimsFollowupJudgeSchema(BaseModel):
    """Schema enforced on the follow-up judge LLM output."""

    winner: int = Field(ge=1, le=2, description="1 or 2 — which follow-up question is better")
    reasoning: str = Field(description="1-2 sentence justification for the choice")
    question: str = Field(
        default="",
        description="The chosen or synthesised follow-up question text",
    )

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


def _filter_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        result = call.get("result")
        if result is None:
            continue
        if isinstance(result, dict) and result.get("error"):
            continue
        filtered.append(call)
    return filtered


def _get_latest_tool_result(
    tool_history: List[Dict[str, Any]],
    tool_name: str,
) -> Dict[str, Any]:
    for call in reversed(tool_history):
        if call.get("name") == tool_name:
            result = call.get("result")
            if isinstance(result, dict):
                return result
    return {}


def is_followup_question_valid(
    question: Optional[str],
    history: List[Dict[str, str]],
    asked_questions: List[str],
    tool_history: List[Dict[str, Any]],
) -> bool:
    normalized = _normalize_question_text(question or "")
    if not normalized:
        return False

    used_questions = set()
    for entry in history:
        q = entry.get("question") if isinstance(entry, dict) else None
        normalized_q = _normalize_question_text(q or "")
        if normalized_q:
            used_questions.add(normalized_q)

    for asked in asked_questions:
        normalized_asked = _normalize_question_text(asked or "")
        if normalized_asked:
            used_questions.add(normalized_asked)

    if normalized in used_questions:
        return False

    lower = normalized.lower()
    if "wronged" in lower or "blame" in lower or "fault" in lower:
        return False

    status_result = _get_latest_tool_result(tool_history, "status_check")
    status_ok = status_result.get("status_ok")
    status_value = status_result.get("status")
    if "status" in lower and status_ok and status_value:
        steer_terms = [
            "timeline",
            "documents",
            "coverage",
            "payments",
            "focus",
            "which part",
        ]
        if not any(term in lower for term in steer_terms):
            return False

    return True


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


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
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


def timeline_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    timeline_ok = True

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

    return {
        "timeline_ok": timeline_ok,
        "issues": issues,
        "loss_date": payload.get("loss_date"),
        "reported_date": payload.get("reported_date"),
        "resolution_date": _get_nested_value(
            payload, ["resolution", "resolution_date"]
        ),
    }


def coverage_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    policy = payload.get("policy") or {}
    coverage_limits = policy.get("coverage_limits") or {}
    coverage_review = payload.get("coverage_review") or {}

    return {
        "coverage_limits": coverage_limits,
        "deductible_eur": policy.get("deductible_eur"),
        "product": policy.get("product"),
        "endorsements": policy.get("endorsements") or [],
        "exclusions": policy.get("exclusions") or [],
        "coverage_decision": coverage_review.get("decision"),
        "approved_repairs_eur": coverage_review.get("approved_repairs_eur"),
        "approved_contents_eur": coverage_review.get("approved_contents_eur"),
        "applied_deductible_eur": coverage_review.get("applied_deductible_eur"),
    }


def documents_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    documents = payload.get("documents") or []
    doc_types: List[str] = []
    titles: List[str] = []
    created_at_values: List[datetime] = []

    for doc in documents:
        if not isinstance(doc, dict):
            continue
        doc_type = doc.get("doc_type")
        if isinstance(doc_type, str):
            doc_types.append(doc_type)
        title = doc.get("title")
        if isinstance(title, str):
            titles.append(title)
        created_at = _parse_datetime(doc.get("created_at"))
        if created_at:
            created_at_values.append(created_at)

    first_created = min(created_at_values) if created_at_values else None
    last_created = max(created_at_values) if created_at_values else None

    return {
        "document_count": len(documents),
        "document_types": sorted(set(doc_types)),
        "sample_titles": titles[:5],
        "first_created_at": first_created.isoformat() if first_created else None,
        "last_created_at": last_created.isoformat() if last_created else None,
    }


def financials_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    resolution = payload.get("resolution") or {}
    coverage_review = payload.get("coverage_review") or {}
    gross = resolution.get("gross_settlement_eur")
    deductible = resolution.get("deductible_eur")
    net = resolution.get("net_payment_eur")
    expected_net = None
    net_matches = None
    if all(isinstance(value, (int, float)) for value in [gross, deductible, net]):
        expected_net = gross - deductible
        net_matches = expected_net == net

    return {
        "resolution_outcome": resolution.get("outcome"),
        "gross_settlement_eur": gross,
        "deductible_eur": deductible,
        "net_payment_eur": net,
        "expected_net_eur": expected_net,
        "net_matches": net_matches,
        "payment_method": resolution.get("payment_method"),
        "coverage_decision": coverage_review.get("decision"),
        "approved_repairs_eur": coverage_review.get("approved_repairs_eur"),
        "approved_contents_eur": coverage_review.get("approved_contents_eur"),
    }


def notes_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    notes = payload.get("adjuster_notes") or []
    latest_note = None
    latest_time: Optional[datetime] = None

    for note in notes:
        if not isinstance(note, dict):
            continue
        timestamp = _parse_datetime(note.get("timestamp"))
        if timestamp and (latest_time is None or timestamp > latest_time):
            latest_time = timestamp
            latest_note = note

    summary = None
    if isinstance(latest_note, dict):
        summary = {
            "author": latest_note.get("author"),
            "note": latest_note.get("note"),
            "timestamp": latest_note.get("timestamp"),
        }

    return {
        "note_count": len(notes),
        "latest_note": summary,
    }


def damage_annotations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch damage annotations for the claim from the backend proxy."""
    claim_id = payload.get("claim_id") or ""
    if not claim_id:
        return {"error": "No claim_id in payload", "annotations": []}

    backend_url = settings.BACKEND_URL.rstrip("/")
    try:
        resp = httpx.get(
            f"{backend_url}/media/claims/{claim_id}/damage-annotations",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        annotations = data.get("annotations", [])
        summary = {}
        for ann in annotations:
            lt = ann.get("label_type", "unknown")
            summary[lt] = summary.get(lt, 0) + 1
        return {
            "claim_id": claim_id,
            "annotation_count": len(annotations),
            "damage_types": summary,
            "annotations": annotations[:20],
        }
    except Exception as exc:
        logger.warning("damage_annotations fetch failed: %s", exc)
        return {"error": str(exc), "annotations": [], "claim_id": claim_id}


TOOL_REGISTRY = {
    "status_check": status_check,
    "timeline_check": timeline_check,
    "coverage_snapshot": coverage_snapshot,
    "documents_summary": documents_summary,
    "financials_summary": financials_summary,
    "notes_summary": notes_summary,
    "damage_annotations": damage_annotations,
}


def build_tool_calls(
    payload: Dict[str, Any],
    tool_names: List[str],
    stage: str,
    attempt: Optional[int] = None,
) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for name in tool_names:
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            continue
        try:
            result = tool(payload)
        except Exception as exc:
            result = {"error": str(exc)}
        entry: Dict[str, Any] = {"name": name, "result": result, "stage": stage}
        if attempt is not None:
            entry["attempt"] = attempt
        calls.append(entry)
    return calls


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
        self,
        agent_name: str,
        instruction: str,
        user_message: str,
        output_schema: Optional[type] = None,
    ) -> str:
        if Agent is None or Runner is None or LiteLlm is None:
            raise RuntimeError("Google ADK is not installed.")

        session_service = self._ensure_session_service()
        model = LiteLlm(model=self.model)

        agent_kwargs: Dict[str, Any] = {
            "model": model,
            "name": agent_name,
            "instruction": instruction,
            "tools": [],
        }
        if output_schema is not None:
            agent_kwargs["output_schema"] = output_schema
            agent_kwargs["output_key"] = "structured_output"

        agent = Agent(**agent_kwargs)

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

        last_error = None
        try:
            for attempt in range(1, MAX_RETRIES + 1):
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
                except Exception as exc:
                    last_error = exc
                    exc_str = str(exc).lower()
                    is_retryable = "overloaded" in exc_str or "rate" in exc_str or "529" in exc_str or "500" in exc_str
                    if is_retryable and attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                        logger.warning(
                            "Retryable error on %s (attempt %d/%d), retrying in %.1fs: %s",
                            agent_name, attempt, MAX_RETRIES, delay, exc,
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise
            raise last_error  # unreachable but satisfies type checker
        finally:
            try:
                await session_service.delete_session(
                    app_name="claims_qa",
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception as exc:
                logger.warning("Failed to delete claims ADK session: %s", exc)

    def _parse_structured(
        self,
        raw_text: str,
        schema: type,
        fallback: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Parse LLM output against a Pydantic schema with fallback.

        Tries Pydantic validation first, then falls back to _clean_and_parse_json.
        """
        # 1. Try direct Pydantic parse (works when ADK returns clean JSON)
        try:
            parsed = schema.model_validate_json(raw_text.strip())
            return parsed.model_dump()
        except Exception:
            pass

        # 2. Fallback: extract JSON via the legacy parser, then validate
        try:
            raw_dict = _clean_and_parse_json(raw_text)
            if isinstance(raw_dict, dict):
                parsed = schema.model_validate(raw_dict)
                return parsed.model_dump()
        except Exception as exc:
            logger.warning("Structured parse failed for %s: %s", schema.__name__, exc)

        return fallback

    def truth_check(self, payload: Any) -> Dict[str, Any]:
        return truth_check_claim(payload)

    async def generate_candidate_answer(
        self,
        payload: Any,
        question: str,
        history: List[Dict[str, str]],
        tool_output: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
        tool_history: List[Dict[str, Any]],
        variant: str,
    ) -> Tuple[str, Dict[str, Any]]:
        claim_json = json.dumps(payload, ensure_ascii=True, indent=2)
        history_json = json.dumps(history, ensure_ascii=True)
        tool_json = json.dumps(
            {
                "truth_check": tool_output,
                "tool_calls": _filter_tool_calls(tool_calls),
                "tool_history": _filter_tool_calls(tool_history),
            },
            ensure_ascii=True,
        )

        if variant == "A":
            style = (
                "Answer in 2-4 concise sentences. Cite specific claim field names and values. "
                "Lead with the most important finding. "
                "If a field is missing, note it precisely (e.g. 'resolution.outcome is not recorded'). "
                "Do not say 'Not enough info' unless no relevant field exists at all."
            )
        else:
            style = (
                "Answer using 2-4 bullet points. Each bullet must reference a specific field path "
                "(e.g. policy.deductible_eur, resolution.outcome). "
                "Flag any discrepancy found by the tool outputs. "
                "If a field is absent, name it explicitly."
            )

        instruction = (
            "You are a senior professional claims examiner conducting a structured file review. "
            "Your goal is to advance the review by surfacing concrete facts, discrepancies, and "
            "gaps directly from the claim JSON and tool outputs provided. "
            "Cite field names explicitly. Never speculate or use outside knowledge. "
            "Maintain a professional, precise, and constructive tone throughout."
        )

        user_message = (
            f"Claim JSON:\n{claim_json}\n\n"
            f"Tool context:\n{tool_json}\n\n"
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
        tool_calls: List[Dict[str, Any]],
        tool_history: List[Dict[str, Any]],
        answer_a: str,
        answer_b: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        tool_json = json.dumps(
            {
                "truth_check": tool_output,
                "tool_calls": _filter_tool_calls(tool_calls),
                "tool_history": _filter_tool_calls(tool_history),
            },
            ensure_ascii=True,
        )
        instruction = (
            "You are a claims QA judge. Use the rubric below and select the best response.\n"
            "Rubric:\n"
            "1) Grounded in claim JSON and tool outputs — cites specific fields.\n"
            "2) Directly answers the question with no speculation.\n"
            "3) Highlights discrepancies surfaced by tool outputs.\n"
            "4) Professional, clear, and concise.\n\n"
            'Return ONLY JSON: {"winner": 1|2, "reasoning": "...", "done": true|false}. '
            "Set done=true ONLY when the question is definitively and completely answered "
            "with no remaining ambiguity, gaps, or discrepancies worth clarifying. "
            "Set done=false whenever any detail, missing field, timeline gap, coverage conflict, "
            "or financial discrepancy could still be explored. "
            "Default to done=false — a rich claim review always benefits from follow-up. "
            "Reasoning must be 1-2 sentences."
        )

        user_message = (
            f"Question: {question}\n\n"
            f"Tool context:\n{tool_json}\n\n"
            f"Response 1:\n{answer_a}\n\n"
            f"Response 2:\n{answer_b}\n"
        )

        start = time.perf_counter()
        default_judge = {
            "winner": 1,
            "reasoning": "Selected response 1 by default.",
            "done": False,
        }
        try:
            output = await self._run_agent(
                agent_name="claims_judge",
                instruction=instruction,
                user_message=user_message,
                output_schema=ClaimsJudgeSchema,
            )
            parsed = self._parse_structured(output, ClaimsJudgeSchema, default_judge)
        except Exception as exc:
            logger.error("Claims judge failed: %s", exc)
            parsed = default_judge
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
        tool_calls: List[Dict[str, Any]],
        tool_history: List[Dict[str, Any]],
        attempt: int,
        max_attempts: int,
        variant: str,
    ) -> Tuple[Optional[str], Dict[str, Any], str]:
        claim_json = json.dumps(payload, ensure_ascii=True, indent=2)
        history_json = json.dumps(history, ensure_ascii=True)
        asked_json = json.dumps(asked_questions, ensure_ascii=True)
        tool_json = json.dumps(
            {
                "truth_check": tool_output,
                "tool_calls": _filter_tool_calls(tool_calls),
                "tool_history": _filter_tool_calls(tool_history),
            },
            ensure_ascii=True,
        )

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

        off_domain_rule = (
            "If the user's question is not about the claim data, you MUST respond with a steering "
            "question that brings them back to the claim review (status progression, timeline "
            "accuracy, documents, coverage decision, or payment reconciliation). "
            "Never return NONE in that case — the claim review must continue."
        )

        if attempt == 1:
            requirement = (
                "Generate ONE specific follow-up question that advances the claim review. "
                "Prioritise unexamined areas: timeline gaps, missing fields, status progression, "
                "coverage conflicts, or financial reconciliation. "
                f"{off_domain_rule}"
            )
        elif attempt >= max_attempts:
            requirement = (
                "You MUST output a follow-up question. "
                "If the user is off-topic, steer back to the claim with a concrete choice question "
                "(status, timeline, documents, coverage, or payments). "
                f"{off_domain_rule}"
            )
        else:
            requirement = (
                "Return ONLY the question text. Return 'NONE' only if every significant aspect "
                "of the claim has already been thoroughly covered in the conversation history. "
                f"{off_domain_rule}"
            )

        instruction = (
            "You are a senior claims QA specialist generating follow-up questions for a structured "
            "claim file review. Your mission is to keep the review moving forward toward a complete "
            "understanding of the claim. "
            "Use the claim JSON, tool outputs, tool history, history, and asked questions. "
            "Do not ask for fields already present in the claim JSON unless clarification is needed. "
            "Avoid repeating any prior questions. "
            "Avoid moral or blame framing (no 'who is wronged' questions). "
            "Use neutral, professional, fact-seeking wording. "
            f"Attempt {attempt} of {max_attempts}. "
            f"{requirement}"
        )

        user_message = (
            f"Claim JSON:\n{claim_json}\n\n"
            f"Tool context:\n{tool_json}\n\n"
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
        tool_calls: List[Dict[str, Any]],
        tool_history: List[Dict[str, Any]],
        attempt: int,
        candidate_a: Optional[str],
        candidate_b: Optional[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        tool_json = json.dumps(
            {
                "truth_check": tool_output,
                "tool_calls": _filter_tool_calls(tool_calls),
                "tool_history": _filter_tool_calls(tool_history),
            },
            ensure_ascii=True,
        )
        history_json = json.dumps(history, ensure_ascii=True)
        asked_json = json.dumps(asked_questions, ensure_ascii=True)
        instruction = (
            "You are a claims QA follow-up judge conducting a professional claim file review. "
            "Select the better follow-up question to advance the review.\n"
            "Criteria:\n"
            "1) Non-redundant with prior questions.\n"
            "2) Advances the review toward a complete understanding of the claim.\n"
            "3) Grounded in claim JSON and tool outputs — targets real gaps or discrepancies.\n"
            "4) Neutral, professional, fact-seeking wording.\n"
            "5) Steers off-topic conversations back to the claim review.\n\n"
            'Return ONLY JSON: {"winner": 1|2, "reasoning": "...", "question": "..."}. '
            "If the user question is off-topic, you MUST return a steering question that refocuses "
            "on the claim (status, timeline, documents, coverage, or payments). "
            "Only set question to empty string if both candidates are truly redundant AND the "
            "conversation already covers every significant aspect of the claim."
        )

        user_message = (
            f"Current question: {question}\n\n"
            f"Tool context:\n{tool_json}\n\n"
            f"Conversation history (Q/A):\n{history_json}\n\n"
            f"Asked questions:\n{asked_json}\n\n"
            f"Attempt {attempt}.\n\n"
            f"Follow-up 1: {candidate_a or 'NONE'}\n"
            f"Follow-up 2: {candidate_b or 'NONE'}\n"
        )

        start = time.perf_counter()
        default_followup_judge = {
            "winner": 1,
            "reasoning": "Selected follow-up 1 by default.",
            "question": candidate_a or "",
        }
        try:
            output = await self._run_agent(
                agent_name="claims_followup_judge",
                instruction=instruction,
                user_message=user_message,
                output_schema=ClaimsFollowupJudgeSchema,
            )
            parsed = self._parse_structured(
                output, ClaimsFollowupJudgeSchema, default_followup_judge
            )
        except Exception as exc:
            logger.error("Claims follow-up judge failed: %s", exc)
            parsed = default_followup_judge
            output = json.dumps(parsed)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        metrics = {
            "token_cost": _build_token_cost(user_message, output),
            "inference_time_ms": elapsed_ms,
        }
        return parsed, metrics
