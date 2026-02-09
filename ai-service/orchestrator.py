"""Multi-Agent Orchestrator using Anthropic Claude.

Extracted from backend/src/services/agent_orchestrator.py.
Orchestrates 2 specialist agents (Finance, Learning) and a Judge agent
that synthesizes their responses into a single recommendation.
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Optional

import httpx

from config import settings


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

    @staticmethod
    def _parse_question_list(raw: str) -> list[str]:
        """Parse a JSON array of question strings with graceful fallback."""
        if not raw:
            return []

        text = raw.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                cleaned = []
                for item in parsed:
                    if isinstance(item, str):
                        normalized = item.strip()
                        if normalized:
                            cleaned.append(normalized)
                return cleaned
        except json.JSONDecodeError:
            pass

        fallback = []
        for line in raw.splitlines():
            candidate = line.strip().lstrip("-*").strip()
            if candidate.endswith("?") and len(candidate) > 4:
                fallback.append(candidate)
        return fallback

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        """Parse a JSON object from model output with light recovery."""
        if not raw:
            return {}

        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
        return {}

    @staticmethod
    def _dedupe_questions(candidates: list[str], asked_norm: set[str], limit: int = 6) -> list[str]:
        """Normalize, dedupe, and filter already asked questions."""
        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            text = item.strip()
            norm = text.lower()
            if not text or norm in seen or norm in asked_norm:
                continue
            seen.add(norm)
            deduped.append(text)
            if len(deduped) >= limit:
                break
        return deduped

    def _extract_agent_panel(
        self,
        agent_name: str,
        raw: str,
        asked_norm: set[str],
    ) -> dict[str, Any]:
        """Extract specialist panel payload from model output."""
        parsed = self._parse_json_object(raw)
        primary_any = parsed.get("primary_question")
        primary = primary_any.strip() if isinstance(primary_any, str) else ""
        reasoning_any = parsed.get("reasoning")
        reasoning_text = reasoning_any.strip() if isinstance(reasoning_any, str) else ""
        other_any = parsed.get("other_suggestions")
        other: list[Any] = other_any if isinstance(other_any, list) else []

        fallback_list = self._parse_question_list(raw)
        candidates: list[str] = []
        if primary:
            candidates.append(primary)
        candidates.extend([item for item in other if isinstance(item, str)])
        candidates.extend(fallback_list)

        deduped = self._dedupe_questions(candidates, asked_norm, limit=6)
        primary_question = deduped[0] if deduped else ""
        other_suggestions = deduped[1:4] if len(deduped) > 1 else []

        return {
            "agent": agent_name,
            "primary_question": primary_question,
            "other_suggestions": other_suggestions,
            "reasoning": reasoning_text,
            "all_candidates": deduped,
        }

    async def generate_clarification_panel(
        self,
        intent: str,
        user_original_query: str,
        asked_questions: Optional[list[str]] = None,
        answers: Optional[list[str]] = None,
        max_questions: int = 3,
    ) -> dict[str, Any]:
        """Run 3 specialists and Judge; return chosen + alternates + reasoning."""
        asked_questions = asked_questions or []
        answers = answers or []
        asked_norm = {q.strip().lower() for q in asked_questions if q.strip()}

        qa_pairs: list[dict[str, str]] = []
        for idx, question in enumerate(asked_questions):
            answer = answers[idx] if idx < len(answers) else ""
            qa_pairs.append({"question": question, "answer": answer})

        context_block = f"""
ORIGINAL USER QUERY:
{user_original_query}

ALREADY ASKED QUESTIONS (do not repeat):
{json.dumps(asked_questions, ensure_ascii=True)}

USER ANSWERS SO FAR:
{json.dumps(answers, ensure_ascii=True)}

Q/A CONTEXT:
{json.dumps(qa_pairs, ensure_ascii=True)}
"""

        specialist_prompt_template = """You are {agent_name}.
You are proposing clarifying questions only (not final advice).
Return ONLY valid JSON object with keys:
- primary_question: string
- other_suggestions: array of strings
- reasoning: short string (1-2 sentences, no chain-of-thought)

Rules:
- Do not answer the user.
- Do not repeat already asked questions.
- Keep questions specific and actionable.
- Maximum 1 primary + up to 3 others.

Focus guidance:
{focus}
"""

        finance_prompt = specialist_prompt_template.format(
            agent_name="FinanceBot",
            focus="Budget limits, affordability, spending constraints, debt/cashflow trade-offs.",
        )
        learning_prompt = specialist_prompt_template.format(
            agent_name="LearnBot",
            focus="Knowledge gaps, decision criteria, timeline, user preferences and confidence.",
        )
        risk_prompt = specialist_prompt_template.format(
            agent_name="RiskBot",
            focus="Downside risk, uncertainty, safety margin, hidden costs, and worst-case resilience.",
        )

        finance_task = self._run_agent("FinanceBot", finance_prompt, context_block)
        learning_task = self._run_agent("LearnBot", learning_prompt, context_block)
        risk_task = self._run_agent("RiskBot", risk_prompt, context_block)
        finance_raw, learning_raw, risk_raw = await asyncio.gather(
            finance_task,
            learning_task,
            risk_task,
        )

        finance_panel = self._extract_agent_panel("FinanceBot", finance_raw, asked_norm)
        learning_panel = self._extract_agent_panel("LearnBot", learning_raw, asked_norm)
        risk_panel = self._extract_agent_panel("RiskBot", risk_raw, asked_norm)

        agent_panels = [finance_panel, learning_panel, risk_panel]
        agent_candidates: dict[str, list[str]] = {
            panel["agent"]: panel["all_candidates"]
            for panel in agent_panels
            if panel["all_candidates"]
        }
        agent_reasoning: dict[str, str] = {
            panel["agent"]: panel["reasoning"]
            for panel in agent_panels
            if isinstance(panel.get("reasoning"), str) and panel["reasoning"]
        }

        judge_instructions = """### ROLE
You are the Lead Orchestrator and Chief Judge for specialist agents.
Your goal is to pick ONE best next clarifying question.

### INPUT
- Original user query
- Already asked Q/A
- Candidate questions from FinanceBot, LearnBot, and RiskBot

### OUTPUT
Return ONLY a JSON object with fields:
- chosen_question: string
- chosen_from_agent: one of FinanceBot|LearnBot|RiskBot
- judge_reasoning: short string (1-2 sentences, no chain-of-thought)
- other_suggested_questions: array of strings

### CONSTRAINTS
- Do NOT answer the user.
- Do NOT repeat asked questions.
- Keep to short practical wording.
"""

        judge_query = f"""
USER ORIGINAL QUERY:
"{user_original_query}"

ALREADY ASKED:
{json.dumps(asked_questions, ensure_ascii=True)}

Q/A CONTEXT:
{json.dumps(qa_pairs, ensure_ascii=True)}

AGENT PANELS:
{json.dumps(agent_panels, ensure_ascii=True)}

Maximum questions to surface: {max_questions}
"""

        judge_raw = await self._run_agent("JudgeBot", judge_instructions, judge_query)
        judge_obj = self._parse_json_object(judge_raw)

        flattened_candidates: list[str] = []
        for panel in agent_panels:
            flattened_candidates.extend(panel["all_candidates"])
        flattened_candidates = self._dedupe_questions(flattened_candidates, asked_norm, limit=12)

        chosen_question_raw = judge_obj.get("chosen_question")
        chosen_question = chosen_question_raw.strip() if isinstance(chosen_question_raw, str) else ""
        if chosen_question.lower() in asked_norm:
            chosen_question = ""
        if not chosen_question and flattened_candidates:
            chosen_question = flattened_candidates[0]

        chosen_from_agent_raw = judge_obj.get("chosen_from_agent")
        chosen_from_agent = chosen_from_agent_raw if isinstance(chosen_from_agent_raw, str) else "JudgeBot"
        judge_reasoning_raw = judge_obj.get("judge_reasoning")
        judge_reasoning = judge_reasoning_raw.strip() if isinstance(judge_reasoning_raw, str) else ""

        suggested_raw_any = judge_obj.get("other_suggested_questions")
        suggested_raw: list[Any] = suggested_raw_any if isinstance(suggested_raw_any, list) else []
        combined_others: list[str] = [item for item in suggested_raw if isinstance(item, str)]
        combined_others.extend(flattened_candidates)
        other_suggested_questions = self._dedupe_questions(
            [item for item in combined_others if item.strip().lower() != chosen_question.lower()],
            asked_norm,
            limit=max_questions,
        )

        return {
            "chosen_question": chosen_question,
            "chosen_from_agent": chosen_from_agent,
            "judge_reasoning": judge_reasoning,
            "other_suggested_questions": other_suggested_questions,
            "agent_candidates": agent_candidates,
            "agent_reasoning": agent_reasoning,
        }

    async def generate_clarification_questions(
        self,
        intent: str,
        user_original_query: str,
        asked_questions: Optional[list[str]] = None,
        answers: Optional[list[str]] = None,
        max_questions: int = 3,
    ) -> list[str]:
        """Backward-compatible list API using the richer panel output."""
        panel = await self.generate_clarification_panel(
            intent=intent,
            user_original_query=user_original_query,
            asked_questions=asked_questions,
            answers=answers,
            max_questions=max_questions,
        )
        chosen = panel.get("chosen_question") if isinstance(panel.get("chosen_question"), str) else ""
        others_raw = panel.get("other_suggested_questions")
        others: list[Any] = others_raw if isinstance(others_raw, list) else []
        result: list[str] = []
        if chosen:
            result.append(chosen)
        result.extend([item for item in others if isinstance(item, str)])
        return result[:max_questions]

    async def process_query_with_clarifications(
        self,
        intent: str,
        original_query: str,
        questions: list[str],
        answers: list[str],
    ) -> dict:
        """Generate final advice using the original query plus clarification answers."""
        enriched_query = self._build_enriched_query(original_query, questions, answers)

        result = await self.process_query(intent, enriched_query)
        result["query"] = original_query
        return result

    @staticmethod
    def _build_enriched_query(
        original_query: str,
        questions: list[str],
        answers: list[str],
    ) -> str:
        """Combine original query and clarification answers into one prompt."""
        qa_lines = []
        guardrail_notes = []
        for idx, question in enumerate(questions, start=1):
            answer = answers[idx - 1] if idx - 1 < len(answers) else ""
            qa_lines.append(f"Q{idx}: {question}\nA{idx}: {answer}")
            if "emergency fund" in question.lower():
                guardrail_notes.append(answer)

        guardrail_context = (
            "\nFinancial guardrail: include emergency-fund resilience in your recommendation. "
            "If the buffer appears weak, be conservative and clearly state the risk."
        )
        if guardrail_notes:
            guardrail_context += f"\nGuardrail answer(s): {json.dumps(guardrail_notes, ensure_ascii=True)}"

        return (
            f"Original user query:\n{original_query}\n\n"
            "Clarification answers provided by user:\n"
            f"{'\n\n'.join(qa_lines)}\n\n"
            "Please prioritize the user's clarified constraints and preferences."
            f"{guardrail_context}"
        )

    async def stream_judge_response_with_clarifications(
        self,
        intent: str,
        original_query: str,
        questions: list[str],
        answers: list[str],
    ) -> AsyncGenerator[str, None]:
        """Stream final answer using original query plus clarification answers."""
        enriched_query = self._build_enriched_query(original_query, questions, answers)
        async for text in self.stream_judge_response(intent, enriched_query):
            yield text

    async def process_query(self, intent: str, query: str) -> dict:
        """Process a user query through specialist agents and synthesize with Judge.

        Args:
            intent: One of 'afford', 'learn'
            query: The user's question

        Returns:
            dict with 'response' (JudgeBot synthesis) and 'intent'
        """
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

        synthesis = await self._run_agent("JudgeBot", judge_instructions, judge_query)

        return {
            "intent": intent,
            "query": query,
            "response": synthesis,
            "agent": "JudgeBot"
        }

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
