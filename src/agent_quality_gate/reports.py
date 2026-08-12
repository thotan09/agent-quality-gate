"""Serialize suite results for CI systems and human review."""

import json
from dataclasses import asdict
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

from agent_quality_gate.models import SuiteResult


def write_reports(result: SuiteResult, output_dir: Path) -> None:
    """Write JSON, JUnit XML, and standalone HTML reports."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "results.json"
    json_path.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    suite_element = ET.Element(
        "testsuite",
        {
            "name": result.suite_name,
            "tests": str(len(result.scenarios)),
            "failures": str(sum(not scenario.passed for scenario in result.scenarios)),
        },
    )
    for scenario in result.scenarios:
        case = ET.SubElement(
            suite_element,
            "testcase",
            {"name": scenario.scenario_id, "classname": result.suite_name},
        )
        if not scenario.passed:
            failure = ET.SubElement(case, "failure", {"message": "quality gate failed"})
            failure.text = (
                f"pass rate {scenario.pass_rate:.3f}; required {scenario.required_pass_rate:.3f}"
            )
    ET.ElementTree(suite_element).write(
        output_dir / "junit.xml",
        encoding="utf-8",
        xml_declaration=True,
    )

    rows = []
    for scenario in result.scenarios:
        status = "PASS" if scenario.passed else "FAIL"
        rows.append(
            "<tr>"
            f"<td><code>{escape(scenario.scenario_id)}</code></td>"
            f"<td class='{status.lower()}'>{status}</td>"
            f"<td>{scenario.pass_rate:.0%}</td>"
            f"<td>{scenario.required_pass_rate:.0%}</td>"
            f"<td>{len(scenario.runs)}</td>"
            "</tr>"
        )
    suite_status = "PASS" if result.passed else "FAIL"
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(result.suite_name)} · Agent Quality Gate</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{
  max-width: 980px; margin: 0 auto; padding: 3rem 1.25rem;
  background: #08111f; color: #dbeafe;
}}
header {{ padding: 2rem; border: 1px solid #1e3a5f; border-radius: 18px; background: #0c1b31; }}
h1 {{ margin: 0 0 .5rem; }}
table {{ width: 100%; margin-top: 2rem; border-collapse: collapse; background: #0c1b31; }}
th, td {{ padding: .9rem 1rem; text-align: left; border-bottom: 1px solid #1e3a5f; }}
.pass {{ color: #4ade80; font-weight: 700; }}
.fail {{ color: #fb7185; font-weight: 700; }}
.badge {{
  display: inline-block; padding: .35rem .7rem;
  border-radius: 999px; background: #132a49;
}}
code {{ color: #93c5fd; }}
</style>
</head>
<body>
<header>
<span class="badge">Agent Quality Gate</span>
<h1>{escape(result.suite_name)}</h1>
<p>Release decision: <strong class="{suite_status.lower()}">{suite_status}</strong></p>
</header>
<table>
<thead><tr>
<th>Scenario</th><th>Status</th><th>Pass rate</th><th>Required</th><th>Runs</th>
</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</body>
</html>
"""
    (output_dir / "report.html").write_text(html, encoding="utf-8")
