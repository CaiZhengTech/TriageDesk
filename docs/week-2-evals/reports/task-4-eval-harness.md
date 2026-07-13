# Task 4 report — Week 2: deterministic eval harness + calibration table (Closes #9)

> Note: this file's path is reused from Week 1's Task 4 (tracing layer, PR #22,
> superseded content below). This report is for the Week 2 plan's Task 4
> (`docs/week-2-evals/PLAN.md`), GitHub issue #9.

## Branch / commit / PR
- Branch: `feat/09-eval-harness` (off main `bcda2e2`)
- Commit: `70ba218` — "feat: deterministic eval harness + calibration table (Closes #9)"
- PR: https://github.com/CaiZhengTech/Agentic_Project/pull/33 (open, not merged, not run live)

## What was built
- `triagedesk/evals/metrics.py` — pure functions over `CaseResult`: `routing_accuracy`,
  `escalation_precision_recall`, `adversarial_catch_rate`, `cost_stats`,
  `latency_percentiles` (linear-interpolation percentile), `calibration_table`
  (5 retrieval-similarity buckets: [0,.30) [.30,.45) [.45,.60) [.60,.80) [.80,1.01)),
  `summarize` (flat dict, all metrics + calibration list). No DB, no API, no I/O.
- `triagedesk/evals/harness.py` — `run_suite(session, *, cost_cap=1.00, with_judge=True)
  -> (eval_run_id, summary)`. Iterates `eval_cases` in id order, calls
  `runner.run_ticket` per case (LIVE), reads predicted queue off the `classify` span
  (`triage.classify.queue`), maps `run.state` → `route|escalate|failed`, builds a
  `CaseResult`, persists one `EvalResult` row per case with
  `escalation_reason`/`retrieval_similarity`/`classification_margin`/`routing_correct`/
  `outcome_correct` populated from `run.gate_signals` — this is what makes the per-case
  gate-reason breakdown (the entitlement-veto diagnostic the council amendment asked for)
  queryable straight out of `eval_results`. Enforces `SuiteCostExceeded` at a $1 default
  suite cap, checked after each run and again after any judge call.
- `triagedesk/evals/cli.py` — `python -m triagedesk.evals.cli run [--no-judge]
  [--cost-cap N] [--ci]`. Prints `eval_run <uuid>`, the flat summary (JSON, calibration
  excluded), then the calibration table as a formatted block. `--ci` compares the summary
  against `results/eval-baseline.json` (min/max/tolerance) — that file does not exist yet;
  per the task amendments no baseline is committed from this task (Task 7's job).

## One deviation from the brief (flagged, not a NEEDS_CONTEXT — mechanical fix)
The brief's `harness.py` has `from triagedesk.evals.judge import judge_run` at the **top
of `run_suite()`**, unconditional on `with_judge`. `triagedesk.evals.judge` is Task 5 and
does not exist in this repo yet (confirmed: `triagedesk/evals/` currently only has
`__init__.py`, `adversarial.py`, `golden_expectations.json` before this task's additions).
As written, that import would raise `ModuleNotFoundError` on *every* call to `run_suite`,
including `run_suite(..., with_judge=False)` — which is exactly the mode the brief's own
next step specifies for the controller's live checkpoint (`--no-judge`, "to isolate
deterministic cost first"). Implementing the brief literally would make its own documented
next step crash.

Fix: moved the import to inside the `if with_judge and run.state == "completed" and
run.final_reply:` block, i.e. only imported where it's actually used. No other logic,
signature, or persisted-field change. Verified `triagedesk.evals.harness` and
`triagedesk.evals.cli` both import cleanly with no live calls (see Test evidence).

## TDD evidence
1. Wrote `tests/unit/test_eval_metrics.py` (brief's 6 tests verbatim) first.
2. Ran `pytest tests/unit/test_eval_metrics.py -v` → **collection error**,
   `ModuleNotFoundError: No module named 'triagedesk.evals.metrics'` (module didn't exist
   yet — confirms the test actually exercises the missing implementation).
3. Implemented `triagedesk/evals/metrics.py` verbatim from the brief.
4. Reran → **6/6 passed**.
5. Implemented `harness.py` (with the judge-import fix above) and `cli.py`.
6. Ran the full suite and ruff; fixed lint findings (see below); reran both to green.

## Test + ruff results (final)
```
pytest -q
........................................................................ [ 96%]
...                                                                      [100%]
75 passed, 1 warning in 4.71s
```
(warning is a pre-existing, unrelated Starlette/httpx deprecation notice from
`fastapi.testclient`, not touched by this task.)

```
ruff check .
All checks passed!
```

Lint fixes applied beyond the brief's literal code (needed to reach "pristine"):
- `metrics.py::escalation_precision_recall` — wrapped 3 lines that exceeded the
  100-char line-length limit (`tp`/`fp`/`fn` sum expressions).
- `cli.py::cmd_run` — `raise SystemExit(...)` inside an `except SuiteCostExceeded`
  block needed `from exc` (ruff B904).
- `tests/unit/test_eval_metrics.py` — import block re-sorted by `ruff check --fix`
  (I001) and two long inline-comment lines (E501) split/shortened. No test logic changed.

Sanity check (no live calls): `triagedesk.evals.harness` and `triagedesk.evals.cli` both
import successfully in isolation, confirming the deferred judge import doesn't break
module load or the `--no-judge` path.

## Controller: exact command for the live checkpoint run
Per the binding council amendments, this task did **not** run the live suite. The
controller runs it:

```
export TRIAGEDESK_ENV_FILE="C:\Users\Wonton Soup\.secrets\credentials.env"
python -m triagedesk.evals.cli run --no-judge
```

Expected: prints `eval_run <uuid>`, a flat JSON summary (routing accuracy, escalation
precision/recall, adversarial catch rate, cost per run, p50/p95 latency), and the
calibration table; `eval_results` gains 25 rows. Sanity-check: adversarial catch rate
ideally 1.0, and the entitlement trap (case for ticket 90003) escalates via
`no_entitlement_evidence` or `adverse_action`. **4 of the 25 golden cases are expected to
FAIL** (tickets 12027, 565, 4646, 2342 — `expected_outcome: "route"` in
`golden_expectations.json`, but current thresholds are near-unreachable per the council's
Stage-B diagnostic, so they'll escalate instead) — this is the harness reporting real
signal, not a bug; it must not crash. This run doubles as the entitlement-veto isolation
diagnostic and seeds the Task 7 baseline numbers. Cost cap defaults to $1.00 (harness) on
top of the existing $0.10 per-run cap.

## Files touched
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\triagedesk\evals\metrics.py` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\triagedesk\evals\harness.py` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\triagedesk\evals\cli.py` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\tests\unit\test_eval_metrics.py` (new)

---

## Live-run fix 1: timezone-aware/naive datetime crash

**The bug:** First live eval run crashed in `_latency_ms(run)` with `TypeError: can't subtract offset-naive and offset-aware datetimes`. Root cause: `run.created_at` from Postgres `server_default=func.now()` is timezone-naive (timestamp-without-tz column), while `run.finished_at` set by Python's `finish_run()` is timezone-aware (UTC). Both represent UTC clock time; the subtraction just needs normalization.

**Fix:** Added `_as_utc()` helper to normalize naive datetimes to UTC before subtraction. Applies `dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt`.

**Evidence:** 
- Test reproduction: `test_latency_ms_naive_and_aware_datetimes()` in `tests/unit/test_eval_metrics.py` — naive + aware combo case.
- Symmetric case: `test_latency_ms_both_naive_datetimes()` — all-naive path still works.
- Commit: `6afabcb` — "fix: normalize tz-awareness in harness latency computation (#9)"
- PR: https://github.com/CaiZhengTech/Agentic_Project/pull/34 (open, not merged)
- Suite: 74 passed, 0 failures; ruff all checks pass.
