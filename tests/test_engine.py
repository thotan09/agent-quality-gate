from pytest import MonkeyPatch

import agent_quality_gate.engine as engine
from agent_quality_gate.engine import run_suite
from agent_quality_gate.loader import suite_from_dict
from agent_quality_gate.providers import FixtureProvider


def test_run_suite_passes_a_grounded_safe_tool_response() -> None:
    suite = suite_from_dict(
        {
            "name": "support-agent",
            "scenarios": [
                {
                    "id": "refund-policy",
                    "prompt": "Can I return an opened item?",
                    "context": [
                        {
                            "source": "returns-policy",
                            "text": "Opened items may be returned within 30 days with a receipt.",
                        }
                    ],
                    "expected": {
                        "keywords": ["30 days", "receipt"],
                        "citations": ["returns-policy"],
                        "required_tools": ["lookup_order"],
                        "allowed_tools": ["lookup_order"],
                        "forbidden_patterns": ["ignore policy"],
                    },
                    "thresholds": {
                        "min_grounding": 0.5,
                        "max_latency_ms": 500,
                        "max_cost_usd": 0.01,
                    },
                }
            ],
        }
    )
    provider = FixtureProvider.from_dict(
        {
            "responses": {
                "refund-policy": [
                    {
                        "text": (
                            "Opened items may be returned within 30 days "
                            "when a receipt is provided."
                        ),
                        "citations": ["returns-policy"],
                        "tool_calls": [{"name": "lookup_order", "arguments": {"id": "A-1"}}],
                        "latency_ms": 120,
                        "cost_usd": 0.002,
                    }
                ]
            }
        }
    )

    result = run_suite(suite, provider)

    assert result.passed is True
    scenario = result.scenarios[0]
    assert scenario.pass_rate == 1.0
    metrics = {metric.name: metric for metric in scenario.runs[0].metrics}
    assert metrics["keywords"].passed is True
    assert metrics["citations"].passed is True
    assert metrics["tools"].passed is True
    assert metrics["safety"].passed is True
    assert metrics["grounding"].score >= 0.5
    assert metrics["latency"].passed is True
    assert metrics["cost"].passed is True


def test_configured_empty_allowed_tools_rejects_any_tool_call() -> None:
    suite = suite_from_dict(
        {
            "name": "tool-boundary",
            "scenarios": [
                {
                    "id": "no-tools",
                    "prompt": "answer without tools",
                    "expected": {"allowed_tools": []},
                }
            ],
        }
    )
    provider = FixtureProvider.from_dict(
        {
            "responses": {
                "no-tools": [
                    {
                        "text": "done",
                        "tool_calls": [{"name": "shell", "arguments": {}}],
                    }
                ]
            }
        }
    )

    result = run_suite(suite, provider)

    tools = next(metric for metric in result.scenarios[0].runs[0].metrics if metric.name == "tools")
    assert tools.passed is False
    assert tools.details == "unexpected tools: shell"
    assert result.passed is False


def test_run_suite_fails_stop_word_only_response_with_positive_grounding_gate() -> None:
    suite = suite_from_dict(
        {
            "name": "grounding-gate",
            "scenarios": [
                {
                    "id": "empty-answer",
                    "prompt": "State the policy",
                    "context": [{"source": "policy", "text": "Returns take 30 days."}],
                    "thresholds": {"min_grounding": 0.1},
                }
            ],
        }
    )
    provider = FixtureProvider.from_dict({"responses": {"empty-answer": [{"text": "and the or"}]}})

    result = run_suite(suite, provider)

    grounding = next(
        metric for metric in result.scenarios[0].runs[0].metrics if metric.name == "grounding"
    )
    assert grounding.score == 0.0
    assert grounding.passed is False
    assert result.passed is False


def test_forbidden_pattern_timeout_fails_closed(monkeypatch: MonkeyPatch) -> None:
    suite = suite_from_dict(
        {
            "name": "safety-gate",
            "scenarios": [
                {
                    "id": "redos",
                    "prompt": "answer",
                    "expected": {"forbidden_patterns": ["(a+)+$"]},
                }
            ],
        }
    )
    provider = FixtureProvider.from_dict({"responses": {"redos": [{"text": "safe response"}]}})

    def raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise TimeoutError

    monkeypatch.setattr(engine.regex, "search", raise_timeout)

    result = run_suite(suite, provider)

    safety = next(
        metric for metric in result.scenarios[0].runs[0].metrics if metric.name == "safety"
    )
    assert safety.passed is False
    assert "timed out" in safety.details
    assert result.passed is False


def test_catastrophic_forbidden_pattern_is_bounded_in_practice() -> None:
    suite = suite_from_dict(
        {
            "name": "redos-gate",
            "scenarios": [
                {
                    "id": "redos",
                    "prompt": "answer",
                    "expected": {"forbidden_patterns": ["^(a|aa)+$"]},
                }
            ],
        }
    )
    provider = FixtureProvider.from_dict({"responses": {"redos": [{"text": "a" * 5_000 + "!"}]}})

    result = run_suite(suite, provider)

    safety = next(
        metric for metric in result.scenarios[0].runs[0].metrics if metric.name == "safety"
    )
    assert safety.passed is False
    assert "timed out" in safety.details
