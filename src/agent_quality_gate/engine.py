"""Run provider-independent quality evaluations."""

import re

import regex

from agent_quality_gate.models import (
    AgentResponse,
    MetricResult,
    RunResult,
    Scenario,
    ScenarioResult,
    Suite,
    SuiteResult,
)
from agent_quality_gate.providers import AgentProvider

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_SAFETY_PATTERN_TIMEOUT_SECONDS = 0.02
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "be",
        "by",
        "for",
        "in",
        "is",
        "it",
        "may",
        "of",
        "on",
        "or",
        "the",
        "to",
        "when",
        "with",
    }
)


def _content_tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_PATTERN.findall(text.casefold()) if token not in _STOP_WORDS}


def _coverage(required: tuple[str, ...], observed: set[str]) -> float:
    if not required:
        return 1.0
    matched = sum(value.casefold() in observed for value in required)
    return matched / len(required)


def _evaluate_response(scenario: Scenario, response: AgentResponse) -> tuple[MetricResult, ...]:
    text = response.text.casefold()

    keyword_score = _coverage(
        scenario.expected.keywords,
        {
            keyword.casefold()
            for keyword in scenario.expected.keywords
            if keyword.casefold() in text
        },
    )
    keyword_metric = MetricResult(
        name="keywords",
        passed=keyword_score == 1.0,
        score=keyword_score,
        threshold=1.0,
        details="required concept coverage",
    )

    observed_citations = {citation.casefold() for citation in response.citations}
    citation_score = _coverage(scenario.expected.citations, observed_citations)
    citation_metric = MetricResult(
        name="citations",
        passed=citation_score == 1.0,
        score=citation_score,
        threshold=1.0,
        details="required source citation coverage",
    )

    observed_tools = {call.name.casefold() for call in response.tool_calls}
    tool_score = _coverage(scenario.expected.required_tools, observed_tools)
    allowed_tools = (
        {tool.casefold() for tool in scenario.expected.allowed_tools}
        if scenario.expected.allowed_tools is not None
        else None
    )
    unexpected_tools = observed_tools - allowed_tools if allowed_tools is not None else set()
    tool_metric = MetricResult(
        name="tools",
        passed=tool_score == 1.0 and not unexpected_tools,
        score=tool_score if not unexpected_tools else 0.0,
        threshold=1.0,
        details=(
            "required tools observed"
            if not unexpected_tools
            else f"unexpected tools: {', '.join(sorted(unexpected_tools))}"
        ),
    )

    matched_patterns: list[str] = []
    timed_out_patterns: list[str] = []
    for pattern in scenario.expected.forbidden_patterns:
        try:
            if regex.search(
                pattern,
                text,
                regex.IGNORECASE,
                timeout=_SAFETY_PATTERN_TIMEOUT_SECONDS,
            ):
                matched_patterns.append(pattern)
        except TimeoutError:
            timed_out_patterns.append(pattern)
    safety_passed = not matched_patterns and not timed_out_patterns
    if timed_out_patterns:
        safety_details = f"forbidden pattern evaluation timed out: {', '.join(timed_out_patterns)}"
    elif matched_patterns:
        safety_details = f"matched forbidden patterns: {', '.join(matched_patterns)}"
    else:
        safety_details = "no forbidden patterns detected"
    safety_metric = MetricResult(
        name="safety",
        passed=safety_passed,
        score=1.0 if safety_passed else 0.0,
        threshold=1.0,
        details=safety_details,
    )

    response_tokens = _content_tokens(response.text)
    context_tokens = _content_tokens(" ".join(document.text for document in scenario.context))
    grounding_score = (
        len(response_tokens & context_tokens) / len(response_tokens) if response_tokens else 0.0
    )
    grounding_metric = MetricResult(
        name="grounding",
        passed=grounding_score >= scenario.thresholds.min_grounding,
        score=grounding_score,
        threshold=scenario.thresholds.min_grounding,
        details="lexical support from supplied context",
    )

    latency_threshold = scenario.thresholds.max_latency_ms
    latency_metric = MetricResult(
        name="latency",
        passed=latency_threshold is None or response.latency_ms <= latency_threshold,
        score=response.latency_ms,
        threshold=latency_threshold,
        details="observed latency in milliseconds",
    )

    cost_threshold = scenario.thresholds.max_cost_usd
    cost_metric = MetricResult(
        name="cost",
        passed=cost_threshold is None or response.cost_usd <= cost_threshold,
        score=response.cost_usd,
        threshold=cost_threshold,
        details="estimated response cost in USD",
    )

    return (
        keyword_metric,
        citation_metric,
        tool_metric,
        safety_metric,
        grounding_metric,
        latency_metric,
        cost_metric,
    )


def run_suite(suite: Suite, provider: AgentProvider) -> SuiteResult:
    """Execute every scenario and return the aggregate release decision."""

    scenario_results: list[ScenarioResult] = []
    for scenario in suite.scenarios:
        runs: list[RunResult] = []
        for repetition in range(scenario.repetitions):
            response = provider.generate(scenario, repetition)
            metrics = _evaluate_response(scenario, response)
            runs.append(
                RunResult(
                    repetition=repetition + 1,
                    passed=all(metric.passed for metric in metrics),
                    response=response,
                    metrics=metrics,
                )
            )
        pass_rate = sum(run.passed for run in runs) / len(runs)
        scenario_results.append(
            ScenarioResult(
                scenario_id=scenario.id,
                passed=pass_rate >= scenario.min_pass_rate,
                pass_rate=pass_rate,
                required_pass_rate=scenario.min_pass_rate,
                runs=tuple(runs),
            )
        )

    results = tuple(scenario_results)
    return SuiteResult(
        suite_name=suite.name,
        passed=all(scenario.passed for scenario in results),
        scenarios=results,
    )
