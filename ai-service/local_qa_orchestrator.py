"""CrewAI local Q&A orchestration for art and photography prompts."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator, Optional

import httpx

from config import settings

try:
    from crewai import Agent, Crew, LLM, Process, Task
except Exception:  # pragma: no cover - graceful fallback when dependency missing
    Agent = Crew = LLM = Process = Task = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_ART_KEYWORDS = (
    "art",
    "artist",
    "artwork",
    "photo",
    "photography",
    "camera",
    "lens",
    "lighting",
    "composition",
    "portrait",
    "landscape",
    "exposure",
    "iso",
    "aperture",
    "shutter",
    "color grading",
    "retouch",
    "editing",
)

_DEFAULT_FALLBACK = (
    "Welcome to the studio! Local AI is warming up right now. "
    "Please try again in a moment."
)

_STREAM_SYSTEM_PROMPT = (
    "You are a Photography & Art Consultant. "
    "Give technically accurate, practical guidance for art and photography. "
    "Be concise, specific, and helpful."
)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class LocalQAOrchestrator:
    """Routes local Q&A to CrewAI backed by a local vLLM endpoint."""

    def __init__(self) -> None:
        self._llm: Optional[Any] = None
        self._llm_model_name: Optional[str] = None
        self._last_model_mismatch: Optional[tuple[str, str]] = None

    def _ensure_llm(self, model_name: str) -> Any:
        if self._llm is not None and self._llm_model_name == model_name:
            return self._llm
        if LLM is None:
            raise RuntimeError("CrewAI is not installed.")
        self._llm = LLM(
            model=f"openai/{model_name}",
            base_url=settings.LOCAL_QA_VLLM_BASE_URL,
            api_key=settings.LOCAL_QA_API_KEY,
        )
        self._llm_model_name = model_name
        return self._llm

    async def _fetch_served_model_ids(self) -> list[str]:
        base = settings.LOCAL_QA_VLLM_BASE_URL.rstrip("/")
        url = f"{base}/models"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
            if response.status_code != 200:
                return []
            payload = response.json()
            data = payload.get("data", []) if isinstance(payload, dict) else []
            model_ids: list[str] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    model_ids.append(model_id.strip())
            return model_ids
        except Exception:
            return []

    async def _resolve_model_name(self) -> Optional[str]:
        configured = settings.LOCAL_QA_MODEL_NAME.strip()
        served_model_ids = await self._fetch_served_model_ids()
        if not served_model_ids:
            return None

        if configured and configured in served_model_ids:
            return configured

        selected = served_model_ids[0]
        mismatch = (configured, selected)
        if configured and configured != selected and self._last_model_mismatch != mismatch:
            logger.warning(
                "Configured LOCAL_QA_MODEL_NAME=%r not found in served models %r; using %r.",
                configured,
                served_model_ids,
                selected,
            )
            self._last_model_mismatch = mismatch
        return selected

    async def is_local_ai_online(self) -> bool:
        return bool(await self._fetch_served_model_ids())

    async def resolve_model_name(self) -> Optional[str]:
        return await self._resolve_model_name()

    def is_supported_topic(self, query: str) -> bool:
        text = query.lower()
        return any(keyword in text for keyword in _ART_KEYWORDS)

    def fallback_message(self) -> str:
        return _DEFAULT_FALLBACK

    def _build_stream_messages(
        self,
        query: str,
        history: Optional[list[dict[str, str]]] = None,
    ) -> list[dict[str, str]]:
        query_text = _normalize_text(query)
        messages: list[dict[str, str]] = [{"role": "system", "content": _STREAM_SYSTEM_PROMPT}]
        cleaned_history: list[dict[str, str]] = []

        for item in history or []:
            role = _normalize_text(item.get("role", "")).lower()
            content = _normalize_text(item.get("content", ""))
            if role not in {"user", "assistant", "system"}:
                continue
            if not content:
                continue
            cleaned_history.append({"role": role, "content": content})

        if cleaned_history and cleaned_history[-1]["role"] == "user" and cleaned_history[-1]["content"] == query_text:
            cleaned_history = cleaned_history[:-1]

        for item in cleaned_history[-12:]:
            messages.append(item)
        messages.append({"role": "user", "content": query_text})
        return messages

    async def stream_answer_query_tokens(
        self,
        query: str,
        history: Optional[list[dict[str, str]]] = None,
        *,
        model_name: Optional[str] = None,
    ) -> AsyncIterator[str]:
        resolved_model = model_name or await self._resolve_model_name()
        if not resolved_model:
            raise RuntimeError("Local model is unavailable.")

        url = f"{settings.LOCAL_QA_VLLM_BASE_URL.rstrip('/')}/chat/completions"
        payload = {
            "model": resolved_model,
            "messages": self._build_stream_messages(query, history),
            "temperature": 0.4,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {settings.LOCAL_QA_API_KEY}"}

        timeout = httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode(errors="ignore")
                    raise RuntimeError(
                        f"Local vLLM streaming failed ({response.status_code}): {body[:500]}"
                    )

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = choices[0] if isinstance(choices[0], dict) else {}
                    delta = choice.get("delta") if isinstance(choice, dict) else None

                    token = None
                    if isinstance(delta, dict):
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            token = content
                    if token is None and isinstance(choice, dict):
                        text = choice.get("text")
                        if isinstance(text, str) and text:
                            token = text
                    if token:
                        yield token

    async def generate_greeting(self) -> tuple[str, str]:
        model_name = await self._resolve_model_name()
        if not model_name:
            return self.fallback_message(), "System"
        try:
            llm = self._ensure_llm(model_name)
            if Agent is None or Crew is None or Task is None or Process is None:
                raise RuntimeError("CrewAI runtime is unavailable.")

            greeter = Agent(
                role="Studio Greeter",
                goal="Provide a warm and concise welcome to an art and photography studio chat.",
                backstory=(
                    "You welcome users to a local creative assistant. "
                    "You keep responses short and professional."
                ),
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )
            task = Task(
                description=(
                    "Greet the user in one short sentence. "
                    "Ask how you can help with art or photography."
                ),
                expected_output="A single concise greeting sentence.",
                agent=greeter,
            )
            crew = Crew(agents=[greeter], tasks=[task], process=Process.sequential, verbose=False)
            result = crew.kickoff()
            raw = _normalize_text(str(getattr(result, "raw", result)))
            return (raw or "Hello, how can I help you with art or photography today?"), "Studio Greeter"
        except Exception:
            logger.exception("Local greeting generation failed, using deterministic fallback.")
            return "Hello, how can I help you with art or photography today?", "System"

    async def answer_query(self, query: str, history: Optional[list[dict[str, str]]] = None) -> tuple[str, str]:
        model_name = await self._resolve_model_name()
        if not model_name:
            return self.fallback_message(), "System"
        try:
            llm = self._ensure_llm(model_name)
            if Agent is None or Crew is None or Task is None or Process is None:
                raise RuntimeError("CrewAI runtime is unavailable.")

            cleaned_history = []
            for item in history or []:
                role = _normalize_text(item.get("role", ""))
                content = _normalize_text(item.get("content", ""))
                if role and content:
                    cleaned_history.append(f"{role}: {content}")
            history_block = "\n".join(cleaned_history[-12:]) if cleaned_history else "No prior messages."

            specialist = Agent(
                role="Photography & Art Consultant",
                goal="Provide practical, technically accurate advice for art and photography.",
                backstory=(
                    "You are an experienced photographer and digital art mentor. "
                    "You give direct, specific recommendations with concise steps."
                ),
                llm=llm,
                allow_delegation=False,
                verbose=False,
            )
            task = Task(
                description=(
                    "Given the conversation history and user query, answer with practical guidance. "
                    "Keep response clear and concise.\n\n"
                    f"Conversation history:\n{history_block}\n\n"
                    f"User query:\n{query}"
                ),
                expected_output="A concise practical answer focused on art or photography.",
                agent=specialist,
            )
            crew = Crew(
                agents=[specialist],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            result = crew.kickoff()
            raw = _normalize_text(str(getattr(result, "raw", result)))
            if not raw:
                return "I can help with art and photography questions. Please share more detail.", "Photography & Art Consultant"
            return raw, "Photography & Art Consultant"
        except Exception:
            logger.exception("Local query generation failed, using deterministic fallback.")
            return self.fallback_message(), "System"


local_qa_orchestrator = LocalQAOrchestrator()
