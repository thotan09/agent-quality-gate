import json
from pathlib import Path

from pytest import CaptureFixture

from agent_quality_gate.cli import main


def test_cli_run_writes_json_junit_and_html_reports(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        """
name: release-gate
scenarios:
  - id: grounded-answer
    prompt: What is the return window?
    context:
      - source: policy
        text: Returns are accepted within 30 days.
    expected:
      keywords: [30 days]
      citations: [policy]
    thresholds:
      min_grounding: 0.4
      max_latency_ms: 300
""".strip(),
        encoding="utf-8",
    )
    fixture_path = tmp_path / "responses.yaml"
    fixture_path.write_text(
        """
responses:
  grounded-answer:
    - text: Returns are accepted within 30 days.
      citations: [policy]
      latency_ms: 90
      cost_usd: 0
""".strip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(
        [
            "run",
            str(suite_path),
            "--fixture",
            str(fixture_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["scenarios"][0]["scenario_id"] == "grounded-answer"
    assert "testsuite" in (output_dir / "junit.xml").read_text(encoding="utf-8")
    html = (output_dir / "report.html").read_text(encoding="utf-8")
    assert "release-gate" in html
    assert "PASS" in html


def test_cli_returns_configuration_error_for_invalid_suite(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    suite_path = tmp_path / "invalid.yaml"
    suite_path.write_text("name: empty\nscenarios: []\n", encoding="utf-8")
    fixture_path = tmp_path / "responses.yaml"
    fixture_path.write_text("responses: {}\n", encoding="utf-8")

    exit_code = main(
        [
            "run",
            str(suite_path),
            "--fixture",
            str(fixture_path),
        ]
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "ERROR: suite must define at least one scenario" in captured.err


def test_cli_returns_gate_failure_and_junit_failure(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        """
name: failing-gate
scenarios:
  - id: answer
    prompt: answer
    expected:
      keywords: [required]
""".strip(),
        encoding="utf-8",
    )
    fixture_path = tmp_path / "responses.yaml"
    fixture_path.write_text(
        """
responses:
  answer:
    - text: wrong
""".strip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(
        [
            "run",
            str(suite_path),
            "--fixture",
            str(fixture_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 1
    junit = (output_dir / "junit.xml").read_text(encoding="utf-8")
    assert "quality gate failed" in junit
    assert 'failures="1"' in junit
