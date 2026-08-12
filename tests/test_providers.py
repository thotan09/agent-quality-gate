import pytest

from agent_quality_gate.providers import FixtureError, FixtureProvider


def test_fixture_provider_rejects_empty_scenario_responses() -> None:
    with pytest.raises(FixtureError, match="scenario 'empty' must define at least one response"):
        FixtureProvider.from_dict({"responses": {"empty": []}})


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"responses": {"case": [{"text": None}]}},
            "response.text must be a string",
        ),
        (
            {"responses": {"case": [{"text": "hello", "citations": "policy"}]}},
            "response.citations must be a list of strings",
        ),
        (
            {"responses": {"case": [{"text": "hello", "latency_ms": -1}]}},
            "response.latency_ms must be finite and non-negative",
        ),
        (
            {"responses": {"case": [{"text": "hello", "latency_ms": float("inf")}]}},
            "response.latency_ms must be finite and non-negative",
        ),
        (
            {"responses": {"case": [{"text": "hello", "cost_usd": -0.01}]}},
            "response.cost_usd must be finite and non-negative",
        ),
        (
            {"responses": {"case": [{"text": "hello", "cost_usd": float("nan")}]}},
            "response.cost_usd must be finite and non-negative",
        ),
        (
            {"responses": []},
            "responses must be a mapping",
        ),
    ],
)
def test_fixture_provider_rejects_invalid_evidence(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(FixtureError, match=message):
        FixtureProvider.from_dict(payload)


def test_fixture_provider_reports_missing_scenario() -> None:
    provider = FixtureProvider.from_dict({"responses": {"other": [{"text": "hello"}]}})
    from agent_quality_gate.loader import suite_from_dict

    scenario = suite_from_dict(
        {"name": "suite", "scenarios": [{"id": "missing", "prompt": "hello"}]}
    ).scenarios[0]

    with pytest.raises(FixtureError, match="no fixture responses for scenario 'missing'"):
        provider.generate(scenario, 0)
