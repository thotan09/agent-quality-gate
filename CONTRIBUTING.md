# Contributing

Thank you for improving Agent Quality Gate.

## Development setup

```bash
uv sync --locked --group dev
```

## Change workflow

1. Open an issue or describe the quality risk being addressed.
2. Add one failing behavioral test and run it to confirm the expected RED state.
3. Implement the smallest change that makes the test pass.
4. Refactor only while the focused and full suites remain green.
5. Update examples and documentation when the public contract changes.
6. Run all local quality gates before opening a pull request.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=agent_quality_gate --cov-branch --cov-fail-under=90
uv run python -m build
```

Do not commit API keys, real customer prompts, production traces, credentials, or
other confidential data. Use deterministic synthetic fixtures.

## Commit and pull request expectations

- Keep commits focused and explain the engineering outcome.
- Include RED and GREEN test evidence in the pull request description.
- Call out compatibility or schema changes explicitly.
- Avoid vendor-specific behavior in the core evaluator.
- Maintain Python 3.11 and 3.12 compatibility.
