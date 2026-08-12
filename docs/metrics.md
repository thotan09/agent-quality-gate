# Metric semantics

The MVP intentionally uses transparent deterministic metrics. Every score can be
reproduced locally without network access or a model-as-judge.

| Metric | Score | Pass condition |
|---|---|---|
| Keywords | Required phrases found / required phrases | Score equals `1.0` |
| Citations | Required source IDs present / required source IDs | Score equals `1.0` |
| Tools | Required tool coverage | Coverage is complete and the configured allow-list is respected |
| Safety | Binary | No forbidden regex matches response text and no evaluation times out |
| Grounding | Supported content tokens / response content tokens | Score is at least `min_grounding` |
| Latency | Observed milliseconds | At or below `max_latency_ms`, when configured |
| Cost | Estimated USD | At or below `max_cost_usd`, when configured |

## Grounding baseline

Grounding lowercases text, extracts alphanumeric tokens, removes a compact stop-word
set, and measures how many response content tokens occur in supplied context. This
provides a deterministic smoke signal for unsupported vocabulary.

It does **not** understand entailment, negation, paraphrases, temporal facts, or
numeric contradictions. A response can share words with context while making an
unsupported claim. Production programs should combine this baseline with citation
verification, domain checks, semantic graders, red-team tests, and human review.

## Repeated-run policy

A response repetition passes only if every metric passes. Scenario pass rate is:

```text
passing repetitions / configured repetitions
```

A scenario passes when this value is greater than or equal to `min_pass_rate`.
Empty expectations are treated as satisfied; absent latency and cost thresholds do
not gate the run.

## Tool policy semantics

`required_tools` controls minimum tool coverage. `allowed_tools` controls the
maximum boundary and deliberately distinguishes omission from an empty list:

- omitted `allowed_tools` means additional observed tools are not restricted;
- `allowed_tools: []` means any observed tool fails the run;
- a non-empty `allowed_tools` list rejects every observed name outside it.

When `allowed_tools` is configured, all required tool names must be members of
that list. Names are compared case-insensitively.

## Bounded safety-pattern evaluation

The loader accepts at most 50 forbidden patterns, limits each pattern to 256
characters, and rejects invalid syntax before execution. Runtime searches use
the `regex` engine with a 20 ms timeout per pattern. A timeout produces a failed
safety metric with explicit evidence; it never passes as a non-match. These
bounds contain accidental or adversarial backtracking while keeping the policy
decision fail-closed.

## Interpreting thresholds

Start with observable business risk rather than arbitrary high scores. Use fixture
runs to validate policy mechanics, then collect representative live traces before
setting semantic or reliability thresholds. Record threshold changes in review so
teams cannot silently weaken the release gate.
