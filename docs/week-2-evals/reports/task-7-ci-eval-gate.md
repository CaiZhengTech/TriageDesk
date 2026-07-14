# Task 7 report — Week 2: CI eval gate, the kill-criterion checkpoint (Closes #12)

## Branch / commit
- Branch: `feat/12-ci-eval-gate` (off main `d5f2d34`)
- No live API calls made (per the $0-budget amendment); all work is unit tests over
  fakes plus static files (workflow YAML, baseline JSON, README, this report).

## What was built

1. **`results/eval-baseline.json`** — the regression floor, derived from the
   already-recorded live-run summary in `docs/week-2-evals/reports/task-4-eval-harness.md`
   and `.superpowers/sdd/progress.md` ("Live numbers on record"), not invented and not
   re-run:
   - `escalation_recall: 1.00` and `adversarial_catch_rate: 1.00` — kept **exact**, no
     safety margin. Observed values are already 1.00; any drop is a real regression.
   - `escalation_precision: 0.80` — floor just below the observed 0.88.
   - `routing_accuracy: 0.20` — floor just below the observed 6/21 = 0.286. Per the
     amendment, this is deliberately loose: the 29% figure is a documented
     dataset-noise finding (queue taxonomy overlaps in embedding space), not a quality
     target, so the gate must not fail on known noise.
   - `cost_per_run: 0.08` max, `cost_max_run: 0.10` max — ceilings just above the
     observed ~2.9¢/run, with `cost_max_run` set at the existing per-run design cap
     (10¢, `DESIGN-SPEC.md`/pipeline gate).
   - `tolerance: {}` — empty. `triagedesk/evals/metrics.py::summarize()` does not
     currently expose a judge-based rate metric (e.g. `judge_pass_rate`), and per the
     binding amendment this task must not add one to the harness — kappa is 0.279
     (issue #11), so a judge metric advises, it never vetoes. The tolerance *mechanism*
     in `cli._assert_baseline()` is still exercised by a dedicated test
     (`test_assert_baseline_tolerance_band_gates_judge_metric_when_present`) against a
     synthetic key, so if a judge rate metric is added later, gating it is a one-line
     baseline-file change, not new gate code.
   - A `_note` field documents the regression-floor framing in the file itself (readable
     by anyone opening the JSON, not just README readers).

2. **`.github/workflows/eval.yml`** — separate workflow, does not touch `ci.yml`.
   Trigger per the binding amendment: `workflow_dispatch` (manual) **plus** `push` to
   `main` filtered by `paths:` to `triagedesk/**`, `kb/**`,
   `results/eval-baseline.json`, and the workflow file itself. Checked the actual repo
   tree first (`git ls-files`) — eval code lives under `triagedesk/evals/`, already
   covered by `triagedesk/**`; there is no top-level `evals/**` directory, so the brief's
   literal path list was not used verbatim (would have filtered on a path that doesn't
   exist). `$1` cap via `--cost-cap 1.0`; `--ci` flag makes the CLI exit non-zero on any
   metric breach or `SuiteCostExceeded`.

3. **`README.md`** — new `## CI / evals` section with the verbatim kill-checkpoint text
   from the brief, plus a short note on the amended trigger and the baseline-as-floor
   framing.

4. **`tests/unit/test_eval_cli.py`** (new, 6 tests) — see TDD evidence below.

## Deviation from the brief (and why)

**`--ci` was already implemented** in `triagedesk/evals/cli.py` (`_assert_baseline`,
built during Task 4 — see `task-4-eval-harness.md` line 31: "`--ci` compares the summary
against `results/eval-baseline.json`... that file does not exist yet"). Per binding
amendment 5, this task therefore did **not** reimplement `--ci` gating logic — only
added tests for it and the baseline file it reads. Verified by reading
`triagedesk/evals/cli.py` directly before writing any code (the SDK/CI-reality rule:
don't invent what you haven't checked). The `--cost-cap` flag was also already present
(`argparse` default 1.00, `run` subcommand).

This means the "TDD evidence" below is TDD over the **baseline file and its schema
contract**, not over `_assert_baseline()` itself (which predates this task and already
had passing coverage transitively via `cmd_run`, just not direct unit tests).

## TDD evidence

1. Wrote `tests/unit/test_eval_cli.py` first (6 tests: passes on a compliant summary;
   fails on a dropped `escalation_recall`; fails on a dropped `adversarial_catch_rate`;
   fails on `cost_per_run` ceiling breach; the tolerance-band mechanism passes/fails
   correctly against a synthetic judge metric; and a schema-drift guard that loads the
   **real committed** `results/eval-baseline.json` and asserts every `min`/`max` key is
   a real `summarize()` key).
2. Ran `pytest tests/unit/test_eval_cli.py -v` before creating the baseline file:

   ```
   tests/unit/test_eval_cli.py::test_assert_baseline_passes_when_summary_meets_all_floors_and_ceilings PASSED
   tests/unit/test_eval_cli.py::test_assert_baseline_fails_when_deterministic_metric_drops_below_floor PASSED
   tests/unit/test_eval_cli.py::test_assert_baseline_fails_when_adversarial_catch_rate_drops PASSED
   tests/unit/test_eval_cli.py::test_assert_baseline_fails_when_cost_exceeds_ceiling PASSED
   tests/unit/test_eval_cli.py::test_assert_baseline_tolerance_band_gates_judge_metric_when_present PASSED
   tests/unit/test_eval_cli.py::test_committed_baseline_keys_match_summarize_output FAILED
   ```

   5 passed (they exercise `_assert_baseline` against a monkeypatched temp baseline
   file, independent of the committed one) — confirming the pre-existing gate logic
   works. The 6th failed with `FileNotFoundError: results/eval-baseline.json`, the
   expected red: the committed baseline didn't exist yet.
3. Created `results/eval-baseline.json` with the derived numbers above.
4. Reran → **6/6 passed**.

## Test + ruff results (final, full suite)

```
pytest -q
129 passed, 18 skipped, 1 warning in 4.63s
```
(18 skips are pre-existing `integration` tests requiring `TEST_DATABASE_URL`, not
touched by this task. 129 = 123 prior + 6 new.)

```
ruff check .
All checks passed!
```

## How the controller runs the live verification

This task made **zero** API calls, per the $0-budget rule — the workflow cannot even
fire until `.github/workflows/eval.yml` lands on the default branch (`workflow_dispatch`
requires the workflow file to exist on `main`). The controller does the one counted live
run after merge.

**Prerequisite (one-time, per the brief):** `EVAL_DATABASE_URL` must point to a
persistent Neon branch that is pre-seeded once — tickets ingested, KB embedded,
`alembic upgrade head` run, `python -m scripts.build_golden_set` run — so the CI job
pays for the 25 eval cases only, not ingest/embed costs every run. Repo secrets needed:
`EVAL_DATABASE_URL`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`.

**Step 1 — merge this PR to `main`.** The `paths:` filter means this specific merge
(workflow + baseline + README + tests + report, no `triagedesk/**`/`kb/**` changes)
will **not** auto-trigger the gate via `push` — that's the filter working as designed
(it's not an eval-relevant path change to product code). Use `workflow_dispatch` to run
it manually the first time:

```
gh workflow run eval-gate --ref main
```

or, to also confirm the `push` trigger fires correctly on a real eval-path change, push
a trivial no-op comment change under `triagedesk/**` in a follow-up commit and observe
the `push` trigger instead.

**Step 2 — watch the run and confirm pass:**

```
gh run list --workflow=eval-gate --limit 5
gh run watch <run-id>
```

Expect: job installs deps, runs `alembic upgrade head` against the seeded eval branch,
runs `python -m triagedesk.evals.cli run --ci --cost-cap 1.0`, prints the summary JSON
and `EVAL GATE PASSED`, exits 0. Cost ≈ the ~2.9¢/run × 25 cases + judge backfill on the
19 golden replies with a completed run and a reply — well under the $1 `--cost-cap` and
the workflow's own budget note ($1–1.5 in the plan).

**Step 3 — prove the gate actually gates (deliberately-tightened-baseline failure
test):**

```
git checkout -b chore/prove-eval-gate-fails
```

Edit `results/eval-baseline.json` — raise `min.escalation_recall` to e.g. `1.01`
(unreachable) or `min.adversarial_catch_rate` to `1.01`, commit, push, and either
`workflow_dispatch` or merge to `main` under an eval-relevant path so `push` fires it.
Confirm the job **fails** with `EVAL GATE FAILED:` and the specific breached-metric line
in the log (the format `_assert_baseline` raises: `"{key}={value:.3f} < min {floor}"`).
Then **revert** the tightened baseline (`git checkout main -- results/eval-baseline.json`
on the temp branch, or just discard the branch) — do not leave the unreachable threshold
merged to `main`.

**Step 4 — kill-criterion checkpoint.** If Step 2's run on `main` is green: Week 2 is
complete, Week 3 proceeds as planned. If it is not green (and cannot be made green
without lowering a floor below what's actually achievable, i.e. a real regression, not a
baseline-derivation mistake): invoke the kill criterion — Week 3's console is cut to a
single read-only page, remaining hours go to pipeline + evals. This is Cai's
llm-council checkpoint per `CLAUDE.md`; STOP here for that before any Week-3 work.

## Deviations from the brief, summarized

1. `--ci`/`--cost-cap` not reimplemented — already existed (Task 4). Only tests + the
   baseline file were added. (Amendment 5, verified by reading the code first.)
2. Trigger is `workflow_dispatch` + path-filtered `push`, not bare `push` — binding
   amendment 1, verbatim.
3. `paths:` filter uses `triagedesk/**` (not a nonexistent top-level `evals/**`) — the
   repo tree was checked (`git ls-files`) before writing the filter; eval code lives at
   `triagedesk/evals/`, already covered.
4. Baseline numbers come from the recorded live-run summary
   (`task-4-eval-harness.md`, `.superpowers/sdd/progress.md`), not from a fresh live run
   — binding amendment 2 and the $0-budget amendment 4.
5. `tolerance` is `{}` in the committed baseline, not populated with
   `adversarial_catch_rate` as the brief's illustrative schema showed — that metric is
   deterministic (already exact in `min`) and duplicating it under `tolerance` would be
   redundant, and no judge-based rate metric exists in `summarize()` to gate — binding
   amendment 3 ("if the harness summary doesn't [expose a judge pass rate], do NOT add
   new judge metrics to the harness — gate only what `--ci` already checks").

## Files touched

- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\.github\workflows\eval.yml` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\results\eval-baseline.json` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\README.md` (modified — new `## CI / evals` section)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\tests\unit\test_eval_cli.py` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\docs\week-2-evals\reports\task-7-ci-eval-gate.md` (new, this file)
