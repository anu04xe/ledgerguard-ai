import json
import os
from typing import Any, Dict

from google import genai
from google.genai import types

from app.agents.tools import LedgerTools


MODEL = "gemini-3.6-flash"


class LedgerInvestigator:
    """
    Agentic Gemini investigator.

    Gemini can request read-only investigation tools.
    Python executes those tools and returns the results.

    The deterministic reconciliation engine remains the source
    of financial truth.
    """

    def __init__(self, tools: LedgerTools):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set."
            )

        self.client = genai.Client(api_key=api_key)
        self.tools = tools

        self.tool_functions = [
            types.FunctionDeclaration(
                name="get_order",
                description=(
                    "Retrieve the complete order record by order ID."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "order_id": types.Schema(
                            type=types.Type.STRING,
                            description="The order ID to inspect.",
                        )
                    },
                    required=["order_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_gateway",
                description=(
                    "Retrieve the complete gateway transaction "
                    "by gateway reference."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "gateway_ref": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "The gateway reference to inspect."
                            ),
                        )
                    },
                    required=["gateway_ref"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_settlement",
                description=(
                    "Retrieve a settlement record by settlement ID."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "settlement_id": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "The settlement ID to inspect."
                            ),
                        )
                    },
                    required=["settlement_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_settlements",
                description=(
                    "Search all settlement records associated "
                    "with a gateway reference."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "gateway_ref": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "The gateway reference to search for."
                            ),
                        )
                    },
                    required=["gateway_ref"],
                ),
            ),
        ]

        self.tool = types.Tool(
            function_declarations=self.tool_functions
        )

    def _execute_tool(
        self,
        name: str,
        args: Dict[str, Any],
    ) -> Any:

        if name == "get_order":
            return self.tools.get_order(
                args["order_id"]
            )

        if name == "get_gateway":
            return self.tools.get_gateway(
                args["gateway_ref"]
            )

        if name == "get_settlement":
            return self.tools.get_settlement(
                args["settlement_id"]
            )

        if name == "search_settlements":
            return self.tools.search_settlements(
                args["gateway_ref"]
            )

        return {
            "error": f"Unknown tool: {name}"
        }

    def investigate(
        self,
        case: Dict[str, Any],
    ) -> Dict[str, Any]:

        tool_trace = []

        prompt = f"""
You are LedgerGuard AI, a financial reconciliation
investigation agent.

Investigate the exception using the supplied case and
your read-only investigation tools.

IMPORTANT ARCHITECTURE RULES:

The deterministic reconciliation engine is the source of
truth for financial matching decisions.

Your job is to investigate and explain the exception,
not override it.

The exception field contains the deterministic engine's
classification.

Use tools when you need to verify or retrieve
additional evidence.

You MUST NOT:
- invent transactions
- invent IDs
- invent amounts
- invent dates
- modify financial values
- claim that an exception is a successful match
- assume missing records exist

Clearly distinguish:
1. Confirmed facts.
2. Evidence supporting the exception.
3. Remaining uncertainty.
4. Recommended operational action.

Before producing the final answer, investigate the case
using the available tools when appropriate.

Return JSON only using this structure:

{{
  "finding": "brief conclusion",
  "reasoning": "concise explanation",
  "confidence": 0.0,
  "recommended_action": "one concrete action",
  "evidence_used": [
    "specific evidence actually inspected"
  ],
  "requires_human_review": true
}}

confidence must be between 0 and 1.

CASE:

{json.dumps(case, indent=2, default=str)}
"""

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=prompt
                    )
                ],
            )
        ]

        # Limit tool calls to control API usage.
        for _ in range(4):

            response = self.client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[self.tool],
                    temperature=0.1,
                ),
            )

            function_calls = []

            for candidate in response.candidates or []:
                content = candidate.content

                if not content:
                    continue

                for part in content.parts or []:
                    if part.function_call:
                        function_calls.append(
                            part.function_call
                        )

            # No tool call means Gemini has produced
            # its final investigation.
            if not function_calls:

                text = response.text.strip()

                if text.startswith("```"):
                    text = text.replace(
                        "```json",
                        "",
                    )
                    text = text.replace(
                        "```",
                        "",
                    )
                    text = text.strip()

                try:
                    result = json.loads(text)

                    # Keep trace metadata separate from
                    # the financial investigation itself.
                    result["_tool_trace"] = tool_trace

                    return result

                except json.JSONDecodeError:
                    return {
                        "finding": (
                            "AI returned an invalid "
                            "structured response."
                        ),
                        "reasoning": text,
                        "confidence": 0.0,
                        "recommended_action": (
                            "Human review required."
                        ),
                        "evidence_used": [],
                        "requires_human_review": True,
                        "_tool_trace": tool_trace,
                    }

            # Preserve Gemini's function-call message.
            contents.append(
                response.candidates[0].content
            )

            tool_parts = []

            for call in function_calls:

                args = dict(call.args or {})

                tool_result = self._execute_tool(
                    call.name,
                    args,
                )

                tool_trace.append(
                    {
                        "tool": call.name,
                        "arguments": args,
                        "result": tool_result,
                    }
                )

                tool_parts.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={
                            "result": tool_result
                        },
                    )
                )

            # Gemini expects the function response
            # as a user message in this API flow.
            contents.append(
                types.Content(
                    role="user",
                    parts=tool_parts,
                )
            )

        return {
            "finding": (
                "Investigation exceeded the maximum "
                "number of tool calls."
            ),
            "reasoning": (
                "The investigation was stopped to "
                "limit agent execution."
            ),
            "confidence": 0.0,
            "recommended_action": (
                "Human review required."
            ),
            "evidence_used": [],
            "requires_human_review": True,
            "_tool_trace": tool_trace,
        }