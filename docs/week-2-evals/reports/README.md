# Week 2 — task reports

Engineering evidence per task: what was built, the TDD proof (failing test first), review
findings, fix loops, and live-run results. Written by the implementing agent, then checked
by an independent reviewer before merge.

| Report | Issue | What it covers |
|---|---|---|
| [`task-2-prompt-caching.md`](task-2-prompt-caching.md) | — | Cache the stable prompt prefixes; cuts live run cost 30–50% |
| [`task-3-golden-set.md`](task-3-golden-set.md) | #8 | The 25-case golden set + the pinned-ID fix that made the soft-denial trap actually trap |
| [`task-4-eval-harness.md`](task-4-eval-harness.md) | #9 | Deterministic metrics + calibration table; the timezone crash the first live run exposed |
| [`task-5-judge.md`](task-5-judge.md) | #10 | LLM-as-judge (temp 0, enum verdict) + the "dead judge" discovery |
| [`task-6-calibration-kappa.md`](task-6-calibration-kappa.md) | #11 | Blind labeling export, hand-rolled Cohen's kappa, the calibration pool |

**Task 1 (SDK spike)** has no report — it was a controller-run live probe (4 API calls, 2¢).
Its output *is* the committed fixture `tests/fixtures/sdk_structured_output_caching.json`,
which proved that an unconstrained verdict field lets the model invent a label ("poor")
and that prompt caching populates the usage fields as expected.

**Task 7 (CI eval gate, issue #12)** is not built yet — it's the Week 2 kill-criterion
checkpoint.

## The through-line worth reading

Each of these reports contains at least one thing that only a *live* run could reveal,
after green mocked tests said everything was fine: strict schemas needing
`additionalProperties: false`, a naive/aware datetime crash, a judge that could never fire,
a trap ticket backed by a customer who was legitimately entitled to what he asked for. That
pattern — verify against reality, capture the evidence, encode the lesson as a permanent
rule — is the project's actual thesis. See [`../STORY.md`](../STORY.md).
