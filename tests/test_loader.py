from pathlib import Path

import pytest

from agent_quality_gate.loader import ConfigError, load_suite, suite_from_dict


def test_suite_from_dict_applies_suite_defaults() -> None:
    suite = suite_from_dict(
        {
            "name": "support-agent",
            "defaults": {"repetitions": 3, "min_pass_rate": 0.75},
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
                }
            ],
        }
    )

    assert suite.name == "support-agent"
    assert suite.scenarios[0].repetitions == 3
    assert suite.scenarios[0].min_pass_rate == 0.75
    assert suite.scenarios[0].context[0].source == "returns-policy"


def test_suite_from_dict_rejects_zero_repetitions() -> None:
    with pytest.raises(ConfigError, match="repetitions must be at least 1"):
        suite_from_dict(
            {
                "name": "invalid-suite",
                "defaults": {"repetitions": 0},
                "scenarios": [{"id": "case", "prompt": "hello"}],
            }
        )


def test_load_suite_decodes_yaml(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        """
name: smoke-suite
scenarios:
  - id: greeting
    prompt: Say hello
    expected:
      keywords: [hello]
""".strip(),
        encoding="utf-8",
    )

    suite = load_suite(suite_path)

    assert suite.name == "smoke-suite"
    assert suite.scenarios[0].expected.keywords == ("hello",)


def test_suite_from_dict_rejects_scenario_zero_repetitions() -> None:
    with pytest.raises(ConfigError, match="scenario 'case' repetitions must be at least 1"):
        suite_from_dict(
            {
                "name": "invalid-suite",
                "scenarios": [{"id": "case", "prompt": "hello", "repetitions": 0}],
            }
        )


def test_suite_from_dict_rejects_duplicate_scenario_ids() -> None:
    with pytest.raises(ConfigError, match="duplicate scenario id: repeated"):
        suite_from_dict(
            {
                "name": "invalid-suite",
                "scenarios": [
                    {"id": "repeated", "prompt": "first"},
                    {"id": "repeated", "prompt": "second"},
                ],
            }
        )


def test_suite_from_dict_rejects_invalid_forbidden_pattern() -> None:
    with pytest.raises(ConfigError, match="invalid forbidden pattern"):
        suite_from_dict(
            {
                "name": "invalid-suite",
                "scenarios": [
                    {
                        "id": "broken-regex",
                        "prompt": "hello",
                        "expected": {"forbidden_patterns": ["["]},
                    }
                ],
            }
        )


def test_suite_from_dict_rejects_empty_suite() -> None:
    with pytest.raises(ConfigError, match="suite must define at least one scenario"):
        suite_from_dict({"name": "empty", "scenarios": []})


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
@pytest.mark.parametrize("location", ["defaults", "scenario"])
def test_suite_from_dict_rejects_invalid_min_pass_rate(value: float, location: str) -> None:
    scenario: dict[str, object] = {"id": "case", "prompt": "hello"}
    payload: dict[str, object] = {"name": "invalid", "scenarios": [scenario]}
    if location == "defaults":
        payload["defaults"] = {"min_pass_rate": value}
    else:
        scenario["min_pass_rate"] = value

    with pytest.raises(ConfigError, match="min_pass_rate must be finite and between 0 and 1"):
        suite_from_dict(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("min_grounding", -0.01, "min_grounding must be finite and between 0 and 1"),
        ("min_grounding", 1.01, "min_grounding must be finite and between 0 and 1"),
        ("min_grounding", float("nan"), "min_grounding must be finite and between 0 and 1"),
        ("max_latency_ms", -1, "max_latency_ms must be finite and non-negative"),
        ("max_latency_ms", float("inf"), "max_latency_ms must be finite and non-negative"),
        ("max_cost_usd", -0.01, "max_cost_usd must be finite and non-negative"),
        ("max_cost_usd", float("nan"), "max_cost_usd must be finite and non-negative"),
    ],
)
def test_suite_from_dict_rejects_invalid_thresholds(
    field: str,
    value: float,
    message: str,
) -> None:
    with pytest.raises(ConfigError, match=message):
        suite_from_dict(
            {
                "name": "invalid",
                "scenarios": [
                    {
                        "id": "case",
                        "prompt": "hello",
                        "thresholds": {field: value},
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "name": "invalid",
                "scenarios": [
                    {
                        "id": "case",
                        "prompt": "hello",
                        "expected": {"keywords": "hello"},
                    }
                ],
            },
            "expected.keywords must be a list of strings",
        ),
        (
            {
                "name": "invalid",
                "defaults": {"repetitions": 1.5},
                "scenarios": [{"id": "case", "prompt": "hello"}],
            },
            "defaults.repetitions must be an integer",
        ),
        (
            {
                "name": "invalid",
                "scenarios": [{"id": "case", "prompt": None}],
            },
            "scenario.prompt must be a string",
        ),
        (
            {
                "name": "invalid",
                "scenarios": [
                    {
                        "id": "case",
                        "prompt": "hello",
                        "context": [{"source": "policy", "text": 42}],
                    }
                ],
            },
            "context.text must be a string",
        ),
        (
            {"name": "invalid", "scenarios": "not-a-list"},
            "scenarios must be a list",
        ),
    ],
)
def test_suite_from_dict_rejects_malformed_schema(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ConfigError, match=message):
        suite_from_dict(payload)


def test_suite_from_dict_rejects_required_tool_outside_empty_allow_list() -> None:
    with pytest.raises(
        ConfigError,
        match=r"expected\.required_tools must be included in expected\.allowed_tools",
    ):
        suite_from_dict(
            {
                "name": "invalid",
                "scenarios": [
                    {
                        "id": "case",
                        "prompt": "hello",
                        "expected": {
                            "required_tools": ["lookup"],
                            "allowed_tools": [],
                        },
                    }
                ],
            }
        )


def test_suite_from_dict_compares_required_and_allowed_tools_case_insensitively() -> None:
    suite = suite_from_dict(
        {
            "name": "tool-policy",
            "scenarios": [
                {
                    "id": "case",
                    "prompt": "hello",
                    "expected": {
                        "required_tools": ["Lookup_Order"],
                        "allowed_tools": ["lookup_order"],
                    },
                }
            ],
        }
    )

    assert suite.scenarios[0].expected.required_tools == ("Lookup_Order",)


@pytest.mark.parametrize(
    ("patterns", "message"),
    [
        (["blocked"] * 51, "at most 50 forbidden patterns"),
        (["a" * 257], "forbidden patterns must be at most 256 characters"),
    ],
)
def test_suite_from_dict_bounds_forbidden_pattern_work(
    patterns: list[str],
    message: str,
) -> None:
    with pytest.raises(ConfigError, match=message):
        suite_from_dict(
            {
                "name": "invalid",
                "scenarios": [
                    {
                        "id": "case",
                        "prompt": "hello",
                        "expected": {"forbidden_patterns": patterns},
                    }
                ],
            }
        )
