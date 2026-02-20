"""
Multi-Agent Orchestrator using Anthropic Claude.

Orchestrates 2 specialist agents (Finance, Learning) and a Judge agent
that synthesizes their responses into a single recommendation.
"""

import asyncio
import json
from typing import Optional, AsyncGenerator

import httpx

from src.core.config import settings

# MEGA TODO: THIS ALL SHOULD GO TO @ai-service and ai service should be used, as a separate service, i guess pixi env fixing broke context vile vibing and forgot about this constratints
class AgentOrchestrator:
    """Orchestrates multiple AI agents for the #ai channel."""

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazily initialize the Anthropic HTTP client."""
        if not self._initialized:
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key not configured")
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
            self._initialized = True

    def _build_messages(self, instructions: str, query: str) -> list:
        return [
            {
                "role": "user",
                "content": f"{instructions}\n\nUser query: {query}"
            }
        ]

    def _extract_text(self, data: dict) -> str:
        try:
            return data["content"][0]["text"]
        except Exception:
            return ""

    def _payload(self, messages: list, temperature: float = 0.7, max_tokens: int = 500) -> dict:
        return {
            "model": settings.CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

    async def _call_claude(self, messages: list, temperature: float = 0.7, max_tokens: int = 500) -> str:
        self._ensure_initialized()
        url = f"{settings.ANTHROPIC_API_BASE}/v1/messages"
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        assert self.client is not None
        response = await self.client.post(url, headers=headers, json=self._payload(messages, temperature, max_tokens))
        response.raise_for_status()
        data = response.json()
        return self._extract_text(data)

    async def _stream_claude(
        self, messages: list, temperature: float = 0.7, max_tokens: int = 500
    ) -> AsyncGenerator[str, None]:
        self._ensure_initialized()
        url = f"{settings.ANTHROPIC_API_BASE}/v1/messages"
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = self._payload(messages, temperature, max_tokens)
        payload["stream"] = True

        assert self.client is not None
        async with self.client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "content_block_delta":
                    text = data.get("delta", {}).get("text", "")
                    if text:
                        yield text
    
    async def _run_agent(self, name: str, instructions: str, query: str) -> str:
        """Run a single agent with the given instructions and query."""
        try:
            messages = self._build_messages(instructions, query)
            return await self._call_claude(messages, temperature=0.7, max_tokens=500)
        except Exception as e:
            return f"[{name} unavailable: {str(e)}]"

    async def process_query(self, intent: str, query: str) -> dict:
        """
        Process a user query through specialist agents and synthesize with Judge.

        Args:
            intent: One of 'afford', 'learn'
            query: The user's question

        Returns:
            dict with 'response' (JudgeBot synthesis) and 'intent'
        """
        # Agent instructions based on their specialties
        finance_instructions = """You are FinanceBot, a financial advisor specializing in personal finance.
Analyze the user's query from a financial perspective:
- Assess affordability and budget implications
- Consider ROI, financing options, and payment plans
- Provide practical money-saving tips
- Be concise and actionable (max 150 words)."""

        learning_instructions = """You are LearnBot, an educational resource curator.
Analyze the user's query from a learning perspective:
- Recommend relevant courses, tutorials, or books
- Suggest skills they might need to develop
- Point to free and paid learning resources
- Be concise and actionable (max 150 words)."""

        # Run both specialists in parallel
        finance_task = self._run_agent("FinanceBot", finance_instructions, query)
        learning_task = self._run_agent("LearnBot", learning_instructions, query)

        responses = await asyncio.gather(
            finance_task,
            learning_task,
            return_exceptions=True
        )

        # Handle any exceptions
        finance_response = responses[0] if not isinstance(responses[0], Exception) else "[FinanceBot unavailable]"
        learning_response = responses[1] if not isinstance(responses[1], Exception) else "[LearnBot unavailable]"

        # Judge agent synthesizes all responses
        judge_instructions = """You are JudgeBot, a synthesis expert.
You receive analyses from 2 specialist agents (Finance, Learning) and must:
1. Synthesize their insights into ONE coherent recommendation
2. Prioritize based on the user's stated intent
3. Highlight the most actionable next steps
4. Be helpful, clear, and concise (max 250 words)
5. If an agent's response is unavailable, work with what you have

Format your response as a helpful, conversational message without mentioning the other agents by name."""

        intent_context = {
            "afford": "The user's primary concern is AFFORDABILITY and financial feasibility.",
            "learn": "The user's primary concern is LEARNING and skill development.",
        }

        judge_query = f"""User's intent: {intent_context.get(intent, "General assistance")}
User's question: {query}

Expert Analyses:
---
FINANCIAL PERSPECTIVE:
{finance_response}

LEARNING PERSPECTIVE:
{learning_response}
---

Synthesize these into one actionable recommendation for the user."""

        synthesis = await self._run_agent("JudgeBot", judge_instructions, judge_query)

        return {
            "intent": intent,
            "query": query,
            "response": synthesis,
            "agent": "JudgeBot"
        }
    #TODO: INstructions are set per agent could be a const for now or a conffig as json file that is loaded at init, this way we can update instructions without code changes and also add more agents in the future without changing code, just config and instructions
    async def stream_judge_response(self, intent: str, query: str) -> AsyncGenerator[str, None]:
        """Stream the Judge response after collecting specialist analyses."""
        finance_instructions = """You are FinanceBot, a financial advisor specializing in personal finance.
Analyze the user's query from a financial perspective:
- Assess affordability and budget implications
- Consider ROI, financing options, and payment plans
- Provide practical money-saving tips
- Be concise and actionable (max 150 words)."""

        learning_instructions = """You are LearnBot, an educational resource curator.
Analyze the user's query from a learning perspective:
- Recommend relevant courses, tutorials, or books
- Suggest skills they might need to develop
- Point to free and paid learning resources
- Be concise and actionable (max 150 words)."""

        finance_task = self._run_agent("FinanceBot", finance_instructions, query)
        learning_task = self._run_agent("LearnBot", learning_instructions, query)

        responses = await asyncio.gather(
            finance_task,
            learning_task,
            return_exceptions=True
        )

        finance_response = responses[0] if not isinstance(responses[0], Exception) else "[FinanceBot unavailable]"
        learning_response = responses[1] if not isinstance(responses[1], Exception) else "[LearnBot unavailable]"

        judge_instructions = """You are JudgeBot, a synthesis expert.
You receive analyses from 2 specialist agents (Finance, Learning) and must:
1. Synthesize their insights into ONE coherent recommendation
2. Prioritize based on the user's stated intent
3. Highlight the most actionable next steps
4. Be helpful, clear, and concise (max 250 words)
5. If an agent's response is unavailable, work with what you have

Format your response as a helpful, conversational message without mentioning the other agents by name."""

        intent_context = {
            "afford": "The user's primary concern is AFFORDABILITY and financial feasibility.",
            "learn": "The user's primary concern is LEARNING and skill development.",
        }

        judge_query = f"""User's intent: {intent_context.get(intent, "General assistance")}
User's question: {query}

Expert Analyses:
---
FINANCIAL PERSPECTIVE:
{finance_response}

LEARNING PERSPECTIVE:
{learning_response}
---

Synthesize these into one actionable recommendation for the user."""

        messages = self._build_messages(judge_instructions, judge_query)
        async for text in self._stream_claude(messages, temperature=0.7, max_tokens=500):
            yield text


# Singleton instance
orchestrator = AgentOrchestrator()
