import json
import logging
from typing import List, Dict, Any, Optional
import os

from anthropic import Anthropic

logger = logging.getLogger(__name__)

class GmailAgent:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")

    def _clean_and_parse_json(self, text: str) -> Any:
        """
        Robustly extract and parse JSON from LLM output.
        Handles Markdown fences and potential extra text.
        """
        # Remove Markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        text = text.strip()
        
        # Try cleaning control characters if needed
        # (Using strict=False in json.loads usually helps, but we can be explicit if needed)
        
        return json.loads(text, strict=False)

    def generate_followup_questions(self, interest: str, previous_answers: List[str] = []) -> List[str]:
        """
        Generate 2 follow-up questions based on the user's interest and previous answers.
        """
        prompt = f"""You are an intelligent assistant helping a user filter their Gmail inbox.
        The user's primary interest is: "{interest}".
        
        previous answers (if any): {previous_answers}

        Your goal is to understand what specific type of emails they want to prioritize within this interest.
        Generate exactly 2 short, distinct follow-up questions to ask the user.
        Return ONLY a JSON array of strings, e.g., ["Question 1?", "Question 2?"].
        Do not include any other text.
        """

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                temperature=0.5,
                system="You are a helpful AI assistant. Output only valid JSON. No markdown fences.",
                messages=[{"role": "user", "content": prompt}]
            )
            content = message.content[0].text
            return self._clean_and_parse_json(content)
        except Exception as e:
            logger.error(f"Failed to generate questions: {e}")
            return [
                f"What specific topics within {interest} matter most?",
                "Are you looking for newsletters, personal updates, or transactional emails?"
            ]

    def generate_summaries(self, emails: List[Dict[str, Any]], interest: str, answers: List[str]) -> Dict[str, str]:
        """
        Generate two distinct summaries (Action-focused vs. Insight-focused).
        """
        email_text = "\n".join([
            f"- From: {e.get('from')}\n  Subject: {e.get('subject')}\n  Body: {e.get('body', e.get('snippet'))[:500]}"
            for e in emails[:20] # Limit to 20 emails for deep analysis to save tokens
        ])

        prompt = f"""You are an expert email analyst.
        User Interest: {interest}
        User Context/Answers: {answers}

        Here are the user's recent emails (truncated content):
        {email_text}

        Task:
        1. Generate 'Summary A': Focus strictly on ACTIONABLE items, deadlines, and urgent tasks.
        2. Generate 'Summary B': Focus on INSIGHTS, trends, and key information (newsletters, updates).

        Return ONLY a JSON object with keys "summary_a" and "summary_b".
        Example: {{"summary_a": "Action items...", "summary_b": "Insights..."}}
        """

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.5,
                system="You are a helpful AI assistant. Output only valid JSON. No markdown fences.",
                messages=[{"role": "user", "content": prompt}]
            )
            return self._clean_and_parse_json(message.content[0].text)
        except Exception as e:
            logger.error(f"Failed to generate summaries: {e}")
            return {
                "summary_a": "Error generating action summary.",
                "summary_b": "Error generating insight summary."
            }

    def judge_and_rank(self, emails: List[Dict[str, Any]], summary_a: str, summary_b: str, interest: str, answers: List[str]) -> Dict[str, Any]:
        """
        Judge the two summaries and the emails to produce a final report.
        """
        prompt = f"""You are a 'Judge' AI.
        User Interest: {interest}
        User Context: {answers}

        Summary A (Action): {summary_a}
        Summary B (Insight): {summary_b}

        Task:
        1. Decide which summary style is more relevant to the user's interest/context, or merge them if both are vital.
        2. Select the top 5 most relevant emails from the list provided below.
        3. Explain your reasoning.

        Email List (for selection context):
        {json.dumps([{k: v for k, v in e.items() if k in ['message_id', 'subject', 'from', 'received_at']} for e in emails[:20]])}

        Return a JSON object with this exact structure:
        {{
            "final_summary": "The combined or selected best summary text...",
            "top_email_ids": ["id1", "id2", ...],
            "reasoning": "Why you chose this focus..."
        }}
        """

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                system="You are a judge AI. Output only valid JSON. No markdown fences.",
                messages=[{"role": "user", "content": prompt}]
            )
            return self._clean_and_parse_json(message.content[0].text)
        except Exception as e:
            logger.error(f"Failed to judge summaries: {e}")
            return {
                "final_summary": summary_a + "\n\n" + summary_b,
                "top_email_ids": [],
                "reasoning": "Fallback due to error."
            }
