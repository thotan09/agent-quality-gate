"""Deterministic and pluggable agent response providers."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from agent_quality_gate.models import AgentResponse, Scenario, ToolCall


class FixtureError(ValueError):
    """Raised when deterministic fixture data is incomplete or invalid."""


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FixtureError(f"{name} must be a mapping")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise FixtureError(f"{name} must be a string")
    return value


def _string_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise FixtureError(f"{name} must be a list of strings")
    return tuple(value)


def _non_negative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FixtureError(f"{name} must be a number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0:
        raise FixtureError(f"{name} must be finite and non-negative")
    return parsed


def _tool_calls(value: Any) -> tuple[ToolCall, ...]:
    if not isinstance(value, list):
        raise FixtureError("response.tool_calls must be a list")
    parsed: list[ToolCall] = []
    for raw_call in value:
        call = _mapping(raw_call, "tool call")
        arguments = _mapping(call.get("arguments", {}), "tool call arguments")
        parsed.append(
            ToolCall(
                name=_string(call.get("name"), "tool call name"),
                arguments=dict(arguments),
            )
        )
    return tuple(parsed)


class AgentProvider(Protocol):
    """Contract implemented by fixture and live agent adapters."""

    def generate(self, scenario: Scenario, repetition: int) -> AgentResponse:
        """Return one response for a scenario repetition."""


@dataclass(frozen=True, slots=True)
class FixtureProvider:
    """Replay deterministic responses for offline tests and CI."""

    responses: Mapping[str, tuple[AgentResponse, ...]]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FixtureProvider":
        """Build a fixture provider from decoded YAML or JSON."""

        raw_responses = _mapping(payload.get("responses"), "responses")
        parsed: dict[str, tuple[AgentResponse, ...]] = {}
        for raw_scenario_id, raw_items in raw_responses.items():
            scenario_id = _string(raw_scenario_id, "response scenario id")
            if not isinstance(raw_items, list):
                raise FixtureError(f"scenario '{scenario_id}' responses must be a list")
            if not raw_items:
                raise FixtureError(f"scenario '{scenario_id}' must define at least one response")

            responses: list[AgentResponse] = []
            for raw_item in raw_items:
                item = _mapping(raw_item, "response")
                responses.append(
                    AgentResponse(
                        text=_string(item.get("text"), "response.text"),
                        citations=_string_list(
                            item.get("citations", []),
                            "response.citations",
                        ),
                        tool_calls=_tool_calls(item.get("tool_calls", [])),
                        latency_ms=_non_negative(
                            item.get("latency_ms", 0.0),
                            "response.latency_ms",
                        ),
                        cost_usd=_non_negative(
                            item.get("cost_usd", 0.0),
                            "response.cost_usd",
                        ),
                    )
                )
            parsed[scenario_id] = tuple(responses)
        return cls(responses=parsed)

    def generate(self, scenario: Scenario, repetition: int) -> AgentResponse:
        """Replay a response, cycling when repetitions exceed fixture count."""

        try:
            responses = self.responses[scenario.id]
        except KeyError as error:
            raise FixtureError(f"no fixture responses for scenario '{scenario.id}'") from error
        return responses[repetition % len(responses)]
