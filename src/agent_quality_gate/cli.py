"""Command-line entry point for Agent Quality Gate."""

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from agent_quality_gate.engine import run_suite
from agent_quality_gate.loader import ConfigError, load_suite
from agent_quality_gate.providers import FixtureError, FixtureProvider
from agent_quality_gate.reports import write_reports


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-quality-gate",
        description="Provider-independent release gates for AI agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="evaluate a scenario suite")
    run_parser.add_argument("suite", type=Path)
    run_parser.add_argument("--fixture", required=True, type=Path)
    run_parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    return parser


def _load_fixture(path: Path) -> FixtureProvider:
    with path.open(encoding="utf-8") as handle:
        payload: Any = yaml.safe_load(handle)
    if not isinstance(payload, Mapping):
        raise FixtureError("fixture file must contain a mapping")
    return FixtureProvider.from_dict(payload)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return a process-compatible exit code."""

    args = _build_parser().parse_args(argv)
    if args.command == "run":
        try:
            suite = load_suite(args.suite)
            provider = _load_fixture(args.fixture)
            result = run_suite(suite, provider)
            write_reports(result, args.output_dir)
        except (ConfigError, FixtureError, OSError, yaml.YAMLError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.suite_name}: {len(result.scenarios)} scenario(s)")
        print(f"Reports: {args.output_dir}")
        return 0 if result.passed else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
