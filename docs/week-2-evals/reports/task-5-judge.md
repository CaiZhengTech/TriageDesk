# Task 5 report: LLM-as-judge (Closes #10)

Branch `feat/10-judge` off main `992a213`. Single commit `872c02d`. PR:
https://github.com/CaiZhengTech/Agentic_Project/pull/36 (open, not merged).

Note: this file previously held a stale report from an earlier task-numbering scheme (Task 4 /
issue #4, the shared LLM client + schemas work). That content is superseded by this one; the
old work it described is long since merged and unrelated to Week 2 Task 5 / issue #10.

## What was built

- `triagedesk/llm.py` — `structured_call` gained an optional `temperature: float | None = None`
  parameter. Kwargs to `c.messages.create(...)` are built once (`extra = {} if temperature is
  None else {"temperature": temperature}`) and splatted in, so every existing pipeline call site
  (precheck, classify, act, resolution — none of which pass `temperature`) is byte-for-byte
  unchanged. Only one `messages.create` call site exists in the current code (the Task 2 cache
  block already merged), so the brief's "two call sites" contingency didn't apply.
- `triagedesk/schemas.py` — added `JudgeVerdict(verdict: Literal["pass","fail","needs_review"],
  reason: str, rule_triggered: str | None = None)` exactly as specified — `verdict` is a
  constrained `Literal`, never plain `str` (binding constraint 1).
- `triagedesk/evals/judge.py` (new) — `JUDGE_SYSTEM`, `judge_reply`, `judge_run`, implemented
  verbatim from the brief. `judge_reply` is pure and mockable via `_call`; `judge_run` is the
  DB adapter the harness's lazy import expects (`session, case, run) -> (JudgeVerdict, list)`),
  reconstructing the KB context from the retrieve span's `retrieval.doc_slugs` attribute (verified
  present on that span before starting). Module docstring states reason/rule_triggered are
  debugging aids, never ground truth, never fed to the gate (binding constraint 3).
- `triagedesk/evals/harness.py` — fixed the reviewer-flagged cost-swallow finding (binding
  constraint 4, see below) and updated the module docstring (the "judge doesn't exist yet" note
  was stale now that it does).

## TDD evidence

1. Wrote `tests/unit/test_judge.py` (the brief's exact two tests) first. Ran
   `pytest tests/unit/test_judge.py -v` → failed with
   `ModuleNotFoundError: No module named 'triagedesk.evals.judge'` (confirmed red).
2. Wrote the fail-closed cost tests in `tests/unit/test_eval_metrics.py`
   (`test_response_cost_computes_known_model`,
   `test_response_cost_fails_closed_on_unknown_model`) first. Ran
   `pytest tests/unit/test_eval_metrics.py -v` → the fail-closed test failed with
   `Failed: DID NOT RAISE SuiteCostExceeded` against the pre-fix code (confirmed red).
3. Implemented `judge.py`, the `temperature` passthrough, `JudgeVerdict`, and the harness fix.
   Both test files now green; ran the full suite afterward.

## Cost-swallow fix (binding constraint 4)

`harness.py`'s `_response_cost` previously caught `CostUnknownError` from `compute_cost` and
returned `0.0` — an unpriced judge-response model would silently contribute nothing to
`total_cost`, under-counting the suite's $1 cap. Read `tracing.py`'s `record_llm_usage` first:
its idiom is to let `CostUnknownError` propagate up as a fail-closed signal (caught at
`run_ticket`'s top level and turned into `escalated/budget_breach`). The harness's own
fail-closed idiom is `raise SuiteCostExceeded(...)` when the running total exceeds the cap
(already used twice in `run_suite`). Matched that idiom directly inside `_response_cost`:

```python
def _response_cost(response) -> float:
    """Cost of one raw API response (a judge call). Fail closed, same rule as
    the per-run cap in tracing.py: an uncomputable cost is a cap breach, not
    $0 — silently zeroing it would under-count the suite's cost cap."""
    from triagedesk.tracing import CostUnknownError, compute_cost
    try:
        return compute_cost(getattr(response, "model", ""), response.usage)
    except CostUnknownError as exc:
        raise SuiteCostExceeded(
            f"judge response cost unknown ({exc}) — failing closed as a cap breach"
        ) from exc
```

This required no change to `run_suite` or `cli.py` — `cli.py::cmd_run` already catches
`SuiteCostExceeded` and exits with `COST CAP BREACH: ...`, so the fail-closed path surfaces
through the existing CLI contract unchanged.

## Final judge prompt (`JUDGE_SYSTEM`, verbatim)

```
You grade a support agent's drafted customer reply against the knowledge-base
articles it was given. You are a debugging aid, not an authority — your verdict
never overrides the deterministic metrics.

Rubric (cite the ONE most-violated rule in rule_triggered when failing):
- grounding: every concrete step/claim in the reply must come from the KB
  articles below. Invented steps, policies, or numbers => fail.
- helpfulness: the reply actually addresses the ticket, with concrete steps.
- tone: professional, no over-promising (no refunds/credits/plan changes).

Return:
- verdict: "pass" (grounded, helpful, appropriate), "fail" (a rule is clearly
  violated), or "needs_review" (genuinely ambiguous — abstain rather than guess).
- reason: one sentence.
- rule_triggered: "grounding" | "helpfulness" | "tone" | null.
```

User message template (built per call in `judge_reply`):

```
<ticket>
Subject: {ticket_subject}

{ticket_body}
</ticket>

<kb>
{kb_block}
</kb>

<agent_reply>
{customer_reply}
</agent_reply>
```

where `kb_block` is `(no KB articles were retrieved)` or one `<kb_article slug="...">` block
per doc with its title and full content.

## Test + ruff results

- `pytest -q` → **83 passed**, 1 pre-existing unrelated deprecation warning
  (`starlette.testclient`/httpx), 0 skipped (Neon test-branch integration tests ran for real —
  no Anthropic calls involved, only Postgres).
- New tests: `tests/unit/test_judge.py` (2), `tests/unit/test_eval_metrics.py` (+2:
  `test_response_cost_computes_known_model`, `test_response_cost_fails_closed_on_unknown_model`).
- `ruff check .` → **All checks passed.**

## Deviations from the brief

None in code. The brief's `judge_reply`/`judge_run`/`JUDGE_SYSTEM` and the two unit tests were
implemented verbatim. The one addition beyond the brief's literal step list is the harness fix
and its two tests, required by binding constraint 4 (not present in the original brief text,
since the brief predates the reviewer finding).

One thing worth flagging for Task 6 (calibration): `judge_run`'s `getattr(run, "ticket", None)`
branch is always `None` in practice — `Run` has no SQLAlchemy `relationship()` for `ticket`
(only the `ticket_id` FK column), so that line always falls through to
`session.get(Ticket, case.ticket_id)`. It's harmless (correct behavior, just a dead fast-path)
and matches the brief's code exactly, so I left it as specified rather than "fixing" unrequested
scope — flagging it here per the surgical-changes principle instead.

## Controller: the deferred live step

Per binding constraint 6, no live Anthropic calls were made building this branch. The brief's
live full-suite-with-judge step is now the controller's to run, from repo root with the branch
checked out:

```
export TRIAGEDESK_ENV_FILE="C:\Users\Wonton Soup\.secrets\credentials.env"
python -m triagedesk.evals.cli run
```

Expected: same deterministic summary as the Task 4/9 no-judge run, plus `eval_results
.judge_verdict` populated on every completed case. Estimated cost ~$1.2–1.6 (counts against the
≤4-live-run Week 2 budget). Spot-check that a grounded reply scores `pass` and any ungrounded
reply scores `fail`/`needs_review`.

## PR

https://github.com/CaiZhengTech/Agentic_Project/pull/36 — `Closes #10`, not merged.

## Fix loop 1: PR #36 reviewer findings (contract guard + tests)

**Findings:**

1. **Finding 1 (Important)**: `judge_run` doesn't defend its own contract. If `run.final_reply` 
   is None/empty, the prompt renders the literal string "None" and the judge grades nonsense.

2. **Finding 2 (Important)**: `judge_run` has zero tests. Edge cases like no retrieve span, 
   empty KB docs, and None/empty final_reply are uncovered.

**What changed:**

1. **Contract guard** (`triagedesk/evals/judge.py`, lines 54–57):
   - Added `ValueError` guard at the start of `judge_run`. Raises with message naming the run id 
     and reason ("no customer-facing reply to grade") when `run.final_reply` is falsy.
   - Guard fires before any DB work or prompt building — fails loudly on caller bugs.
   - Matches module style; no structural changes to the function.
   - Added `_call=structured_call` parameter to `judge_run` (line 49) to enable test injection 
     (matches `judge_reply` pattern).

2. **Unit tests** (`tests/unit/test_judge.py`, lines 65–242):
   - Built fake session/query/span stack using SimpleNamespace (mirrors existing test patterns, 
     no DB, no live calls).
   - **Test 1** (`test_judge_run_raises_on_no_final_reply`): None `final_reply` → raises 
     `ValueError` (TDD: wrote failing test first, then guard).
   - **Test 2** (`test_judge_run_raises_on_empty_final_reply`): empty string `final_reply` → 
     raises `ValueError`.
   - **Test 3** (`test_judge_run_no_retrieve_span`): no retrieve span → kb_docs empty, judge 
     still called, verdict returned (assert KB block says "no articles retrieved").
   - **Test 4** (`test_judge_run_empty_slugs_list`): retrieve span with empty slugs list → 
     same empty-KB behavior, no crash.
   - **Test 5** (`test_judge_run_happy_path_with_kb_docs`): retrieve span with 2 slugs → both 
     KbDocs fetched and passed to judge (assert slugs appear in the prompt).

**TDD evidence:**

- Wrote `test_judge_run_raises_on_no_final_reply` first; ran it against the original code 
  → **failed** (no guard, no exception raised).
- Implemented the `ValueError` guard.
- Re-ran the test → **passed**.
- Ran all judge tests → **7 passed** (2 original + 5 new).
- Ran full suite → **83 passed, 5 skipped**, no regressions.
- `ruff check .` → **All checks passed** (imports auto-fixed by ruff).

**Commit:**

`7b9b00b` — `fix: judge_run defends its contract + edge-case tests (#10)`

Tests are shallow (mocked session, no real DB) but cover the control flow guard and the 
edge cases that undefended `final_reply` was vulnerable to. Future callers (Task 6's 
kappa calibration) will now fail loudly if they call `judge_run` with a run lacking a 
customer reply, rather than silently grading "None".

## Live-run finding: dead judge (branch `fix/judge-gating`)

**The bug.** The first live suite run WITH the judge (`eval_run b58804d6`) judged 0 of 25
cases. `harness.py`'s gate was:

```python
if with_judge and run.state == "completed" and run.final_reply:
```

In this system almost nothing reaches `completed` — the gate escalates nearly everything
by design (adverse-action rule, entitlement-evidence rule, model conservatism). So the
`state == "completed"` clause made the judge dead code: it never fired. 19 of the 25 runs
in `eval_run b58804d6` had a non-empty `final_reply` and were silently never judged, which
means Task 6 (Cohen's-kappa calibration) would have had zero judge verdicts to calibrate
against.

**Why the gate was wrong.** The judge grades reply quality vs KB grounding — grounded,
helpful, appropriately toned — which is orthogonal to the gate's auto-send decision (that's
graded deterministically, by `predicted_outcome`/`outcome_correct`). An escalated run's
drafted `final_reply` is exactly what a human reviewer reads in the review queue, so it
needs the same quality grading a completed run's reply gets. The correct semantics: judge
any run with a drafted reply, regardless of `state`.

**The fix (Part 1 — gate on the artifact, not the outcome).**

```python
# Judge grades reply quality/grounding, which is orthogonal to the
# gate's auto-send decision -- an escalated run's drafted reply is
# exactly what a human reviewer reads, so it must be judged too.
# judge_run's own ValueError guard is the backstop for empty replies.
if with_judge and run.final_reply:
```

`judge_run`'s existing `ValueError` guard (from the fix-loop-1 work above) is the backstop
for runs with no reply at all — `failed` runs typically have none, so they self-exclude
without needing an explicit `state` check.

**TDD evidence (Part 1).** Wrote `tests/unit/test_harness.py` first:
`test_escalated_run_with_final_reply_is_judged` (fake run, `state="escalated"`,
non-empty `final_reply` — asserts `judge_run` was called and `judge_verdict` persisted) and
`test_run_with_no_final_reply_is_not_judged` (fake `state="failed"`, `final_reply=None` —
asserts `judge_run` was NOT called). Ran against the pre-fix code:
`test_escalated_run_with_final_reply_is_judged` **failed** (`assert 0 == 1` — zero judge
calls), confirming the exact bug shape from `b58804d6`. Applied the one-line gate change.
Both tests **passed**; full unit suite (`tests/unit`) still green, no regressions.

**The fix (Part 2 — `judge` backfill subcommand).** Since the pipeline itself isn't broken
(only the judge gate was), re-running the full live suite just to get judge verdicts would
double-pay for 25 pipeline calls already on record. Added `judge_backfill(session,
eval_run_id, *, cost_cap=JUDGE_BACKFILL_COST_CAP)` to `harness.py` (default cap $0.50,
reuses `SuiteCostExceeded`/`_response_cost`, reuses `judge_run` rather than duplicating its
logic): selects `eval_results` rows for the given `eval_run_id` with `judge_verdict IS
NULL`, skips rows whose run has no `final_reply` or can't be resolved, judges the rest,
persists `judge_verdict`/`judge_reason`/`judge_rule_triggered`, and returns a
`{n_judged, verdict_counts, total_cost}` summary. Idempotent by construction — the
`judge_verdict IS NULL` filter means a second run only picks up what the first missed or a
cost-cap breach cut short. Wired to `python -m triagedesk.evals.cli judge --eval-run <uuid>
[--cost-cap 0.50]` (`cmd_judge` in `cli.py`), which prints n judged / verdict counts / total
cost. Makes no pipeline calls — judge calls only.

**TDD evidence (Part 2).** Wrote `tests/unit/test_judge_backfill.py` first (8 tests) against
a fake SQLAlchemy-shaped session (`FakeResultQuery`/`FakeSession`, mirroring the
`test_judge.py` fake patterns) with `judge_run` monkeypatched — no live calls. Confirmed red:
`ImportError: cannot import name 'JUDGE_BACKFILL_COST_CAP'` (function didn't exist yet).
Implemented `judge_backfill`; all 8 tests passed:
`test_judges_rows_with_null_verdict_and_final_reply`,
`test_skips_row_with_no_final_reply`, `test_skips_row_with_missing_run` (dangling `run_id`
that no longer resolves), `test_idempotent_already_judged_rows_excluded_by_query`,
`test_persists_all_three_judge_fields`, `test_counts_multiple_verdicts`,
`test_respects_cost_cap` (asserts `SuiteCostExceeded` raised, same fail-closed idiom as
`run_suite`), `test_default_cost_cap_is_fifty_cents`.

**Verification.** Full unit suite: 93 passed (was 83; +2 harness gating tests, +8 backfill
tests). `ruff check .` — all checks passed.

**Commit:** `7ab06ef` — `fix: judge grades any drafted reply + judge-backfill command (#10)`
(single commit on `fix/judge-gating`, branched off main `8340251`).

**PR:** https://github.com/CaiZhengTech/Agentic_Project/pull/37 — `Refs #10 #11`, not
merged; opened for review, the controller runs the live backfill afterward against
`eval_run b58804d6` (no live calls were made building this branch, per the $0 constraint
for this work):

```
python -m triagedesk.evals.cli judge --eval-run b58804d6-df08-4882-b5ae-61850bd9e563
```
