"""Load quality-gate suites from plain mappings and YAML files."""

import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from agent_quality_gate.models import (
    ContextDocument,
    Expectations,
    Scenario,
    Suite,
    Thresholds,
)


class ConfigError(ValueError):
    """Raised when a suite definition is invalid."""


_MAX_FORBIDDEN_PATTERNS = 50
_MAX_FORBIDDEN_PATTERN_LENGTH = 256


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a mapping")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string")
    return value


def _string_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(f"{name} must be a list of strings")
    return tuple(value)


def _integer(value: Any, name: str) -> int:
    if type(value) is not int:
        raise ConfigError(f"{name} must be an integer")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number")
    return float(value)


def _probability(value: Any, name: str) -> float:
    parsed = _number(value, name)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise ConfigError(f"{name} must be finite and between 0 and 1")
    return parsed


def _non_negative(value: Any, name: str) -> float:
    parsed = _number(value, name)
    if not math.isfinite(parsed) or parsed < 0.0:
        raise ConfigError(f"{name} must be finite and non-negative")
    return parsed


def _context_documents(value: Any) -> tuple[ContextDocument, ...]:
    if not isinstance(value, list):
        raise ConfigError("context must be a list")
    documents: list[ContextDocument] = []
    for raw_document in value:
        document = _mapping(raw_document, "context item")
        documents.append(
            ContextDocument(
                source=_string(document.get("source"), "context.source"),
                text=_string(document.get("text"), "context.text"),
            )
        )
    return tuple(documents)


def suite_from_dict(payload: Mapping[str, Any]) -> Suite:
    """Build a typed suite from a decoded YAML or JSON mapping."""

    name = _string(payload.get("name"), "name")
    defaults = _mapping(payload.get("defaults", {}), "defaults")
    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list):
        raise ConfigError("scenarios must be a list")
    if not raw_scenarios:
        raise ConfigError("suite must define at least one scenario")

    repetitions = _integer(defaults.get("repetitions", 1), "defaults.repetitions")
    min_pass_rate = _probability(defaults.get("min_pass_rate", 1.0), "min_pass_rate")
    if repetitions < 1:
        raise ConfigError("repetitions must be at least 1")

    parsed: list[Scenario] = []
    seen_ids: set[str] = set()
    for raw_item in raw_scenarios:
        item = _mapping(raw_item, "scenario")
        scenario_id = _string(item.get("id"), "scenario.id")
        if scenario_id in seen_ids:
            raise ConfigError(f"duplicate scenario id: {scenario_id}")
        seen_ids.add(scenario_id)

        scenario_repetitions = _integer(
            item.get("repetitions", repetitions),
            "scenario.repetitions",
        )
        if scenario_repetitions < 1:
            raise ConfigError(f"scenario '{scenario_id}' repetitions must be at least 1")

        expected = _mapping(item.get("expected", {}), "expected")
        thresholds = _mapping(item.get("thresholds", {}), "thresholds")
        required_tools = _string_list(
            expected.get("required_tools", []),
            "expected.required_tools",
        )
        allowed_tools = (
            _string_list(expected["allowed_tools"], "expected.allowed_tools")
            if "allowed_tools" in expected
            else None
        )
        if allowed_tools is not None and not {tool.casefold() for tool in required_tools}.issubset(
            tool.casefold() for tool in allowed_tools
        ):
            raise ConfigError("expected.required_tools must be included in expected.allowed_tools")

        forbidden_patterns = _string_list(
            expected.get("forbidden_patterns", []),
            "expected.forbidden_patterns",
        )
        if len(forbidden_patterns) > _MAX_FORBIDDEN_PATTERNS:
            raise ConfigError(f"at most {_MAX_FORBIDDEN_PATTERNS} forbidden patterns are allowed")
        if any(len(pattern) > _MAX_FORBIDDEN_PATTERN_LENGTH for pattern in forbidden_patterns):
            raise ConfigError(
                f"forbidden patterns must be at most {_MAX_FORBIDDEN_PATTERN_LENGTH} characters"
            )
        for pattern in forbidden_patterns:
            try:
                re.compile(pattern)
            except re.error as error:
                raise ConfigError(f"invalid forbidden pattern '{pattern}': {error}") from error

        parsed.append(
            Scenario(
                id=scenario_id,
                prompt=_string(item.get("prompt"), "scenario.prompt"),
                context=_context_documents(item.get("context", [])),
                repetitions=scenario_repetitions,
                min_pass_rate=_probability(
                    item.get("min_pass_rate", min_pass_rate),
                    "min_pass_rate",
                ),
                expected=Expectations(
                    keywords=_string_list(
                        expected.get("keywords", []),
                        "expected.keywords",
                    ),
                    citations=_string_list(
                        expected.get("citations", []),
                        "expected.citations",
                    ),
                    required_tools=required_tools,
                    allowed_tools=allowed_tools,
                    forbidden_patterns=forbidden_patterns,
                ),
                thresholds=Thresholds(
                    min_grounding=_probability(
                        thresholds.get("min_grounding", 0.0),
                        "min_grounding",
                    ),
                    max_latency_ms=(
                        _non_negative(thresholds["max_latency_ms"], "max_latency_ms")
                        if "max_latency_ms" in thresholds
                        else None
                    ),
                    max_cost_usd=(
                        _non_negative(thresholds["max_cost_usd"], "max_cost_usd")
                        if "max_cost_usd" in thresholds
                        else None
                    ),
                ),
            )
        )
    return Suite(name=name, scenarios=tuple(parsed))


def load_suite(path: Path) -> Suite:
    """Decode a YAML suite file into typed models."""

    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, Mapping):
        raise ConfigError("suite file must contain a mapping")
    return suite_from_dict(payload)
