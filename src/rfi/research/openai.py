"""Replaceable OpenAI Responses adapter for the TASK-071 investigation harness."""

from __future__ import annotations

import copy
import json
import os
import urllib.error
import urllib.request
from typing import Any

from rfi.research.contracts import (
    InvestigationSession,
    ModelBudget,
    ModelToolCall,
    ModelTurn,
    ResearchError,
)


class OpenAIResponsesInvestigator:
    """OpenAI implementation of the provider-neutral investigation model port."""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        *,
        api_key_env: str = "OPENAI_API_KEY",
        endpoint: str = "https://api.openai.com/v1/responses",
        timeout_seconds: float = 90.0,
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    @property
    def runtime_identity(self) -> str:
        """Expose non-secret provider, model, API, and prompt identity."""
        return f"openai:{self.model}:responses:task071-investigator-v1"

    def start(
        self,
        question: str,
        instructions: str,
        tools: tuple[dict[str, Any], ...],
        budget: ModelBudget,
    ) -> InvestigationSession:
        """Create one isolated Responses session without retaining a provider conversation."""
        api_key = os.environ.get(self.api_key_env, "")
        if not api_key:
            raise ResearchError(f"required credential environment is absent: {self.api_key_env}")
        return _OpenAIResponsesSession(
            self.endpoint,
            api_key,
            self.model,
            instructions,
            tools,
            budget,
            self.timeout_seconds,
            question,
        )


class _OpenAIResponsesSession:
    """Conversation-local API mechanics hidden behind normalized model turns."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        instructions: str,
        tools: tuple[dict[str, Any], ...],
        budget: ModelBudget,
        timeout_seconds: float,
        question: str,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.instructions = instructions
        self.tools = tools
        self.budget = budget
        self.timeout_seconds = timeout_seconds
        self.input: list[dict[str, Any]] = [{
            "role": "user",
            "content": (
                "Investigate this question using only the retained transcript tools:\n\n"
                + question
            ),
        }]
        self.pending_calls: set[str] = set()
        self.turn_count = 0
        self.expanded_evidence_dates: dict[str, str] = {}

    def next_turn(
        self, tool_outputs: tuple[tuple[str, dict[str, Any]], ...]
    ) -> ModelTurn:
        """Send tool results, call Responses, and normalize function calls."""
        supplied = {call_id for call_id, _payload in tool_outputs}
        if supplied != self.pending_calls:
            raise ResearchError("model session received mismatched function-call outputs")
        for call_id, payload in tool_outputs:
            evidence = payload.get("evidence")
            if isinstance(evidence, list):
                for item in evidence:
                    if not isinstance(item, dict):
                        continue
                    evidence_id, event_date = item.get("evidence_id"), item.get("event_date")
                    if isinstance(evidence_id, str) and isinstance(event_date, str):
                        self.expanded_evidence_dates[evidence_id] = event_date
            self.input.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(payload, sort_keys=True, default=str),
            })
        response = self._request()
        output = response.get("output")
        if not isinstance(output, list):
            raise ResearchError("OpenAI response lacks a valid output list")
        normalized_items = tuple(
            item for item in output if isinstance(item, dict)
        )
        self.input.extend(normalized_items)
        calls = []
        for item in normalized_items:
            if item.get("type") != "function_call":
                continue
            call_id = item.get("call_id")
            name = item.get("name")
            arguments = item.get("arguments")
            if not isinstance(call_id, str) or not isinstance(name, str):
                raise ResearchError("OpenAI function call identity is malformed")
            try:
                decoded = json.loads(str(arguments))
            except json.JSONDecodeError as error:
                raise ResearchError("OpenAI function-call arguments are malformed") from error
            if not isinstance(decoded, dict):
                raise ResearchError("OpenAI function-call arguments are not an object")
            calls.append(ModelToolCall(call_id, name, decoded))
        self.pending_calls = {item.call_id for item in calls}
        return ModelTurn(
            tuple(calls),
            normalized_items,
            str(response.get("output_text", "")),
            self._usage(response.get("usage")),
        )

    def _request(self) -> dict[str, Any]:
        self.turn_count += 1
        tool_choice: str | dict[str, str] = "required"
        if self.turn_count == self.budget.max_model_turns:
            tool_choice = {"type": "function", "name": "submit_investigation"}
        body: dict[str, Any] = {
            "model": self.model,
            "instructions": self._turn_instructions(),
            "input": self.input,
            "tools": self._turn_tools(),
            "tool_choice": tool_choice,
            "parallel_tool_calls": False,
            "max_output_tokens": self.budget.max_output_tokens_per_turn,
            "store": False,
        }
        if self.model.startswith("gpt-5"):
            body["reasoning"] = {"effort": "low"}
        payload = json.dumps(body).encode()
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read(2_000).decode("utf-8", "replace")
            raise ResearchError(
                f"OpenAI Responses request failed with HTTP {error.code}: {detail}"
            ) from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ResearchError(f"OpenAI Responses request failed: {error}") from error
        if not isinstance(value, dict):
            raise ResearchError("OpenAI Responses result is not an object")
        return value

    def _turn_tools(self) -> tuple[dict[str, Any], ...]:
        """Constrain final citations to evidence actually expanded in this session."""
        if self.turn_count != self.budget.max_model_turns:
            return self.tools
        tools = copy.deepcopy(self.tools)
        evidence_ids = sorted(self.expanded_evidence_dates)
        periods = sorted(set(self.expanded_evidence_dates.values()))
        if not evidence_ids:
            return tools
        for tool in tools:
            if tool.get("name") != "submit_investigation":
                continue
            claim = tool["parameters"]["properties"]["claims"]["items"]
            claim["properties"]["evidence_ids"]["items"]["enum"] = evidence_ids
            claim["properties"]["periods"]["items"]["enum"] = periods
        return tools

    def _turn_instructions(self) -> str:
        """Increase decision urgency monotonically without changing evidence semantics."""
        maximum = self.budget.max_model_turns
        urgency = 1.0 if maximum == 1 else (self.turn_count - 1) / (maximum - 1)
        remaining = maximum - self.turn_count
        if remaining == 0:
            direction = "Submit the best supported, partial, or insufficient result now."
        elif remaining <= 2:
            direction = (
                "Stop broad exploration; close only material evidence gaps and prepare submission."
            )
        elif remaining <= 4:
            direction = "Prioritize exact expansion and coverage gaps over additional broad search."
        else:
            direction = "Investigate efficiently and preserve enough turns for evidence expansion."
        evidence_direction = ""
        if remaining <= 2:
            admissible = ", ".join(
                f"{evidence_id}@{event_date}"
                for evidence_id, event_date in self.expanded_evidence_dates.items()
            ) or "none"
            evidence_direction = (
                " Citable expanded evidence is exactly: " + admissible
                + ". Never cite a search-only segment."
            )
        return (
            f"{self.instructions}\n\nTURN CONTROL: turn={self.turn_count}/{maximum}; "
            f"remaining_after_this={remaining}; urgency_factor={urgency:.2f}. {direction}"
            f"{evidence_direction}"
        )

    @staticmethod
    def _usage(value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        output = {}
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            item = value.get(key)
            if isinstance(item, int) and not isinstance(item, bool):
                output[key] = item
        return output
