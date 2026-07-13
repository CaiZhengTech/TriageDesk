> **⚠️ RECONSTRUCTED REPORT.** The original agent report for this task was destroyed by a
> filename collision (Week 2's `task-N-report.md` files overwrote Week 1's). This document
> was rebuilt from surviving evidence: the engineering ledger, the GitHub issue closeout
> comment (#3), PR #22 and its merged diff (squash commit `3fa3a70`), and the code as it
> stands. Facts here are traceable to those sources; anything that could not be recovered is
> marked *(not recovered)* rather than guessed.

# Task 4 (Issue #3): Tracing layer — span writer, run state machine, fail-closed cost cap

## Status
✅ DONE — merged as PR #22 (squash commit `3fa3a70`); issue #3 closed.

## What was built

Branch `feat/03-tracing`, commits `e2ec0f0..5059226`.

- **`triagedesk/tracing.py`** (new, 121 lines per the PR diff) — the observability spine of the
  project:
  - `PRICES_PER_MTOK` — USD-per-1M-token pricing for `claude-sonnet-4-6` only ($3 in / $15 out /
    $3.75 cache-write / $0.30 cache-read). Any model absent from this table is a deliberate,
    reviewed gap.
  - `compute_cost(model, usage) -> float` — **fails closed**: raises `CostUnknownError` if the
    model isn't priced, or if `usage` is missing `input_tokens`/`output_tokens`.
  - `CostUnknownError`, `BudgetExceededError`, `InvalidTransitionError` exception types.
  - `finish_run(session, run, state, reason=None, resolution=None)` — the sole legal way to
    leave `running`. Checks `run.state == "running"` and `state in RUN_STATES` **before**
    mutating, so a rejected transition can't half-apply. Sets `finished_at`; if a `resolution`
    is passed, copies `customer_reply`/`internal_rationale` onto the run.
  - `RunTracer` class: `.span(name)` is a context manager that inserts+commits a `Span` row
    *before* the stage body runs (incremental write — a crash mid-run still leaves a partial
    trace), sets `status="error"` on exception (re-raising), and always commits `ended_at` in a
    `finally`. `.set_attributes(span, **attrs)` merges into the JSONB `attributes` column.
    `.record_llm_usage(span, response)` stamps OTel GenAI attribute names (`gen_ai.*`) into
    JSONB, accumulates `span.cost_usd` and `run.total_cost_usd`, and raises
    `BudgetExceededError` if the running total exceeds `settings.cost_cap_usd` — **after** the
    true spend is committed, so the recorded cost stays accurate even when the run dies.
- **`tests/unit/test_tracing.py`** (new, 98 lines per the PR diff).

## How it was verified

At merge, `test_tracing.py` contained the plan's 7 tests (`test_compute_cost_sonnet`,
`test_unknown_model_fails_closed`, `test_missing_usage_fails_closed`,
`test_finish_run_sets_terminal_state`, `test_finish_run_rejects_double_transition`,
`test_finish_run_rejects_bogus_state`, `test_budget_breach_raises`) plus one fix-loop addition,
`test_budget_accumulates_across_calls` — **8 tests total at merge**. This is inferred from the
PR diff line count (98 new lines matches roughly 8 test functions of this shape) and the ledger's
explicit description of the fix loop adding exactly that one test; an exact
`pytest -v` transcript from the original session is *(not recovered)*.

## Review outcome and fix loop

Ledger: "Task 4: complete (commits e2ec0f0..5059226, PR #22 squash-merged as 3fa3a70; issue #3
closed; review approved after 1 fix loop)."

**Fix loop** (squash subcommit: "test: budget accumulation across calls + fix stale cost
comments (#3)"): added `test_budget_accumulates_across_calls` — two sequential $0.018 calls
against a $0.03 cap; the first must not raise (total $0.018), the second must raise with the
total durably recorded at $0.036 *before* the exception propagates. Also corrected stale $5/$25
per-MTok pricing comments left over from an earlier Opus-4.8 pricing draft (the project's
pinned model was switched to Sonnet 4.6 the same day it was chosen — see `CLAUDE.md`'s Global
Constraints note on the pricing revision). The GitHub issue #3 closeout comment confirms both
halves of this fix loop in the same words.

## Findings deferred

Ledger, three minors:

1. No zero-token / cache-only / exactly-at-cap boundary tests (the cap check is `>`, so an
   exactly-at-cap cost should NOT breach — this was asserted by design but not test-pinned at
   merge time).
2. `record_llm_usage` would raise a bare `AttributeError` (not the intended `CostUnknownError`)
   if the response object was missing `.model` or `.usage` entirely, rather than just having
   `None` token counts.
3. The double-transition tests don't assert the run's state is left unchanged after the raise.

## Later changes

**(1) and (2) were both fixed** in the Week 1 QA hardening pass (issue #28). Ledger's QA
hardening entry (commit 2): "`record_llm_usage` raises `CostUnknownError` (not bare
`AttributeError`) on missing `.model`/`.usage`; zero-token/cache-only/exactly-at-cap boundary
tests." This is directly visible in the current code:

```python
def record_llm_usage(self, span: Span, response) -> None:
    model = getattr(response, "model", None)
    usage = getattr(response, "usage", None)
    if model is None or usage is None:
        raise CostUnknownError(f"response missing model/usage: {response!r}")
    ...
```

— and the current `tests/unit/test_tracing.py` has four additional tests beyond the 8 attributed
above: `test_record_llm_usage_missing_usage_fails_closed`,
`test_record_llm_usage_zero_tokens_no_breach`,
`test_record_llm_usage_cache_only_computes_correct_cost`,
`test_record_llm_usage_exactly_at_cap_is_not_a_breach` — matching the QA hardening description.

**(3) is not verifiably fixed** — *(not recovered)*.

The current file also has a 13th test, `test_compute_cost_bills_cache_tokens`. *(Not recovered
which task added it — neither Task 4's ledger entry nor the QA hardening entry names it
explicitly, so it is not attributed to either here.)*

## Commits / PR

- Commits `e2ec0f0..5059226` on `feat/03-tracing`.
- PR #22: "03 - Tracing layer" (`Closes #3`) — squash-merged as `3fa3a70`. Squash subcommits:
  "feat: tracing layer - incremental spans, state machine, fail-closed cost cap (#3)" (original),
  "test: budget accumulation across calls + fix stale cost comments (#3)" (fix loop).
- Issue #3 closed by PR #22.

## Sources used

Ledger (`progress-backup.md` lines 11–13), `gh issue view 3 --comments`, `gh pr view 22 --json
title,body`, `git show --stat 3fa3a70`, `docs/week-1-pipeline/PLAN.md` (Task 4 section), current
`triagedesk/tracing.py`, `tests/unit/test_tracing.py`.
