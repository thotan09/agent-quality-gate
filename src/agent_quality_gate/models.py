"""Typed configuration and result models used by the quality gate."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ContextDocument:
    """A source document supplied to an agent scenario."""

    source: str
    text: str


@dataclass(frozen=True, slots=True)
class Expectations:
    """Observable behavior expected from an agent response."""

    keywords: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] | None = None
    forbidden_patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Numeric release thresholds for a scenario."""

    min_grounding: float = 0.0
    max_latency_ms: float | None = None
    max_cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class Scenario:
    """One repeatable agent-quality scenario."""

    id: str
    prompt: str
    context: tuple[ContextDocument, ...]
    repetitions: int
    min_pass_rate: float
    expected: Expectations = field(default_factory=Expectations)
    thresholds: Thresholds = field(default_factory=Thresholds)


@dataclass(frozen=True, slots=True)
class Suite:
    """A named collection of quality scenarios."""

    name: str
    scenarios: tuple[Scenario, ...]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool invocation observed in an agent response."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Provider-independent response data consumed by evaluators."""

    text: str
    citations: tuple[str, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    latency_ms: float = 0.0
    cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class MetricResult:
    """One quality metric decision and its evidence."""

    name: str
    passed: bool
    score: float
    threshold: float | None
    details: str


@dataclass(frozen=True, slots=True)
class RunResult:
    """Evaluation results for one scenario repetition."""

    repetition: int
    passed: bool
    response: AgentResponse
    metrics: tuple[MetricResult, ...]


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Aggregated repeated-run result for one scenario."""

    scenario_id: str
    passed: bool
    pass_rate: float
    required_pass_rate: float
    runs: tuple[RunResult, ...]


@dataclass(frozen=True, slots=True)
class SuiteResult:
    """Top-level release-gate decision."""

    suite_name: str
    passed: bool
    scenarios: tuple[ScenarioResult, ...]
