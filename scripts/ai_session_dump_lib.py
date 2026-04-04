"""Build merged AI session dump JSON (Caddy warn/error stream + AI session stream).

Shared by redis-log-sink graceful shutdown and scripts/dump-ai-data-session.py.

Schema version 2.0.0 adds:
- caller: Agent attribution (agent, role, stage, attempt, model)
- tool_calls: List of tool invocations with args, results, reason taxonomy
- question/questions: Single question or list of questions
- reasoning: Agent reasoning string
- plan: Agent plan or step list
- New event kinds for claims and Gmail multi-agent steps
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping

import redis

SCHEMA_VERSION = "2.0.0"

DEFAULT_CADDY_STREAM_KEY = "caddy:warn_error_logs"
DEFAULT_AI_STREAM_KEY = "ai:session_events"


def utc_filename_timestamp() -> str:
    """UTC timestamp safe for filenames (no colons), e.g. 2026-03-21T14-30-00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _parse_recorded_sort_key(recorded_at: str) -> tuple[float, str]:
    s = recorded_at.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt.timestamp(), recorded_at)
    except ValueError:
        return (0.0, recorded_at)


def normalize_caddy_entry(
    event_id: str, fields: Mapping[str, str]
) -> dict[str, Any] | None:
    ts = fields.get("ts") or datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "ts": fields.get("ts", ts),
        "level": fields.get("level", ""),
        "logger": fields.get("logger", ""),
        "msg": fields.get("msg", ""),
        "raw": fields.get("payload", ""),
    }
    return {
        "event_id": event_id,
        "recorded_at": ts if isinstance(ts, str) else str(ts),
        "source": "caddy",
        "kind": "http_warn_error",
        "backend": "n/a",
        "payload": payload,
    }


_VALID_SOURCES = frozenset({"caddy", "ai_service", "ai_service_adk", "backend"})
_VALID_KINDS = frozenset(
    {
        # HTTP/Caddy events
        "http_warn_error",
        # Gmail events
        "gmail_summary",
        "gmail_questions",
        "gmail_step_questions",
        "gmail_step_summary_action",
        "gmail_step_summary_insight",
        "gmail_step_classification",
        "gmail_step_judge",
        "gmail_step_action",
        "gmail_step_insight",
        "gmail_step_triage",
        # Calendar events
        "calendar_question",
        "calendar_create",
        # Local Q&A events
        "local_qa_greeting",
        "local_qa_rejected",
        "local_qa_answer",
        # Claims events
        "claims_truth_check",
        "claims_candidate",
        "claims_judge",
        "claims_followup_candidate",
        "claims_followup_judge",
        "claims_followup",
        "claims_annotation_export",
        "claims_annotation_results",
        # Tool invocation events
        "tool_invoked",
        # Generic fallback
        "generic_ai",
    }
)
_VALID_BACKENDS = frozenset({"crewai", "google_adk", "n/a", "local_vllm"})


def normalize_ai_entry(
    event_id: str, fields: Mapping[str, str]
) -> dict[str, Any] | None:
    """Normalize AI stream fields written by ai-service / ai-service-adk.

    Handles both legacy format (event_json/body) and current format (payload field).
    Extracts new fields: caller, tool_calls, question(s), reasoning, plan, session_id.
    """
    if "payload" not in fields:
        raw = fields.get("event_json") or fields.get("body")
        if not raw:
            return None
        try:
            inner = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(inner, dict):
            return None
        recorded_at = str(
            inner.get("recorded_at") or datetime.now(timezone.utc).isoformat()
        )
        source = str(inner.get("source") or "")
        kind = str(inner.get("kind") or "")
        backend = str(inner.get("backend") or "")
        payload = inner.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        ev: dict[str, Any] = {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "source": source,
            "kind": kind,
            "backend": backend,
            "payload": payload,
        }
        u = inner.get("username")
        if isinstance(u, str) and u:
            ev["username"] = u
        for opt in ("correlation_id", "request_id", "session_id"):
            v = inner.get(opt)
            if isinstance(v, str) and v:
                ev[opt] = v
        # Extract new fields from inner
        _extract_new_fields(ev, inner)
        if not (
            ev["source"] in _VALID_SOURCES
            and ev["kind"] in _VALID_KINDS
            and ev["backend"] in _VALID_BACKENDS
        ):
            return None
        return ev

    try:
        payload_obj = json.loads(fields["payload"])
    except json.JSONDecodeError:
        payload_obj = {"raw": fields["payload"]}
    if not isinstance(payload_obj, dict):
        payload_obj = {"value": payload_obj}

    recorded_at = fields.get("recorded_at") or datetime.now(timezone.utc).isoformat()
    ev: dict[str, Any] = {
        "event_id": event_id,
        "recorded_at": recorded_at,
        "source": fields.get("source", ""),
        "kind": fields.get("kind", ""),
        "backend": fields.get("backend", ""),
        "payload": payload_obj,
    }
    username = fields.get("username")
    if isinstance(username, str) and username:
        ev["username"] = username
    for opt in ("correlation_id", "request_id", "session_id"):
        v = fields.get(opt)
        if isinstance(v, str) and v:
            ev[opt] = v
    # Extract new fields from stream fields
    _extract_new_fields(ev, fields)
    if not (
        ev["source"] in _VALID_SOURCES
        and ev["kind"] in _VALID_KINDS
        and ev["backend"] in _VALID_BACKENDS
    ):
        return None
    return ev


def _extract_new_fields(ev: dict[str, Any], fields: Mapping[str, Any]) -> None:
    """Extract caller, tool_calls, question(s), reasoning, plan from fields."""
    # caller: JSONB agent attribution
    caller = fields.get("caller")
    if isinstance(caller, str):
        try:
            caller = json.loads(caller)
        except json.JSONDecodeError:
            caller = None
    if isinstance(caller, dict) and caller:
        ev["caller"] = caller

    # tool_calls: JSONB array of tool invocations
    tool_calls = fields.get("tool_calls")
    if isinstance(tool_calls, str):
        try:
            tool_calls = json.loads(tool_calls)
        except json.JSONDecodeError:
            tool_calls = None
    if isinstance(tool_calls, list) and tool_calls:
        ev["tool_calls"] = tool_calls

    # question: single question string
    question = fields.get("question")
    if isinstance(question, str) and question:
        ev["question"] = question

    # questions: array of question strings
    questions = fields.get("questions")
    if isinstance(questions, str):
        try:
            questions = json.loads(questions)
        except json.JSONDecodeError:
            questions = None
    if isinstance(questions, list) and questions:
        ev["questions"] = questions

    # reasoning: agent reasoning string
    reasoning = fields.get("reasoning")
    if isinstance(reasoning, str) and reasoning:
        ev["reasoning"] = reasoning

    # plan: JSONB agent plan or step list
    plan = fields.get("plan")
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError:
            plan = None
    if isinstance(plan, (dict, list)) and plan:
        ev["plan"] = plan


def _collect_sources(events: list[dict[str, Any]]) -> list[str]:
    order = ["caddy", "ai_service", "ai_service_adk", "backend"]
    seen: set[str] = set()
    out: list[str] = []
    for s in order:
        if any(e.get("source") == s for e in events) and s not in seen:
            out.append(s)
            seen.add(s)
    for e in events:
        src = e.get("source")
        if isinstance(src, str) and src not in seen:
            out.append(src)
            seen.add(src)
    return out


def read_stream(
    client: redis.Redis,
    key: str,
    *,
    normalize: Any,
) -> list[dict[str, Any]]:
    rows = client.xrange(key, min="-", max="+")
    events: list[dict[str, Any]] = []
    for msg_id, field_map in rows:
        eid = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
        decoded = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in field_map.items()
        }
        ev = normalize(eid, decoded)
        if ev:
            events.append(ev)
    return events


def build_session_dump_document(
    client: redis.Redis,
    *,
    caddy_stream_key: str,
    ai_stream_key: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    caddy_events = read_stream(
        client, caddy_stream_key, normalize=normalize_caddy_entry
    )
    ai_events = read_stream(client, ai_stream_key, normalize=normalize_ai_entry)
    merged = caddy_events + ai_events
    merged.sort(
        key=lambda e: (
            _parse_recorded_sort_key(str(e.get("recorded_at", "")))[0],
            str(e.get("event_id", "")),
        )
    )
    sources = _collect_sources(merged)
    if not sources:
        sources = []

    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sources": sources,
        "events": merged,
    }
    if session_id:
        doc["session_id"] = session_id

    annotations: dict[str, Any] = {}
    for env_key, ann_key in (
        ("GIT_SHA", "git_sha"),
        ("IMAGE_TAG", "image_tag"),
    ):
        val = os.getenv(env_key)
        if val:
            annotations[ann_key] = val
    if annotations:
        doc["annotations"] = annotations
    return doc


def write_session_dump_json(
    doc: dict[str, Any],
    dump_dir: str,
    *,
    timestamp: str | None = None,
) -> str:
    """Write `{timestamp}-data-session.json` under dump_dir; return absolute path."""
    os.makedirs(dump_dir, exist_ok=True)
    ts = timestamp or utc_filename_timestamp()
    name = f"{ts}-data-session.json"
    path = os.path.join(dump_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return os.path.abspath(path)
