import json
import os
from typing import Any, Dict

from google import genai


class LedgerInvestigator:
    """
    Gemini-powered investigator.

    IMPORTANT:
    Gemini does not determine financial truth.
    It analyzes evidence supplied by the deterministic engine.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set."
            )

        self.client = genai.Client(api_key=api_key)

    def investigate(self, case: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are LedgerGuard AI, a financial reconciliation investigation agent.

Your job is to investigate an exception using ONLY the evidence provided.

You MUST NOT invent transactions, IDs, amounts, dates, or evidence.

You MUST NOT modify financial values.

You MUST NOT assume that two records match merely because they look similar.

Analyze the supplied case and return JSON only.

Required JSON structure:

{{
  "finding": "brief conclusion",
  "reasoning": "concise explanation",
  "confidence": 0.0,
  "recommended_action": "one concrete action",
  "evidence_used": [
    "specific evidence from the supplied records"
  ],
  "requires_human_review": true
}}

Rules:

- confidence must be between 0 and 1
- requires_human_review should be true when the evidence is insufficient
- distinguish between confirmed facts and plausible explanations
- never invent missing records
- never claim a transaction is valid without supporting evidence

CASE:

{json.dumps(case, indent=2, default=str)}
"""

        response = self.client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        text = response.text.strip()

        # Handle accidental markdown fences.
        if text.startswith("```"):
            text = text.replace("```json", "")
            text = text.replace("```", "")
            text = text.strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            return {
                "finding": "AI returned an invalid structured response.",
                "reasoning": text,
                "confidence": 0.0,
                "recommended_action": "Human review required.",
                "evidence_used": [],
                "requires_human_review": True,
            }

        return result

