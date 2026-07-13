> **⚠️ RECONSTRUCTED REPORT.** The original agent report for this task was destroyed by a
> filename collision (Week 2's `task-N-report.md` files overwrote Week 1's). This document
> was rebuilt from surviving evidence: the engineering ledger, the GitHub issue closeout
> comment (#4), PR #23 and its merged diff (squash commit `208be4c`), and the code as it
> stands. Facts here are traceable to those sources; anything that could not be recovered is
> marked *(not recovered)* rather than guessed.

# Task 6 (Issue #4, part B): Pipeline stages v1 — pre-check + classify

## Status
✅ DONE — merged as part of PR #23 (squash commit `208be4c`); issue #4 closed.

## What was built

Branch `feat/04-precheck-classify` (continuation of Task 5), commits `0fe1c3f..20fb882`.

- **`triagedesk/prompts.py`** (new) — `PROMPT_VERSION = "w1-v1"` (bumped on any prompt edit,
  recorded per run), `PRECHECK_SYSTEM` (flags `injection`/`pii`/`off_topic`, treats ordinary
  frustrated/urgent language as safe), `CLASSIFY_SYSTEM` (routes into exactly one of the 10
  dataset queues plus a free-text sub-category), `ACT_SYSTEM` (written here for Task 8's later
  use — resolution types, tool-use instructions, the "never promise refunds/credits/plan
  changes yourself" rule), and `ticket_block(ticket)` (formats subject+body for the prompt).
- **`triagedesk/pipeline/__init__.py`** (new, empty).
- **`triagedesk/pipeline/precheck.py`** (new) — `run_precheck(ticket, tracer, _call=
  structured_call) -> PrecheckVerdict`, writing span `"precheck"`.
- **`triagedesk/pipeline/classify.py`** (new) — `run_classify(ticket, tracer, _call=
  structured_call) -> ClassifyResult`, writing span `"classify"`.
- **`tests/unit/test_precheck_classify.py`** (new).

## Ride-along fix (council-mandated item 1)

Same PR, same commit range: **`triagedesk/config.py`** was changed so `_ENV_FILE` reads
`os.environ.get("TRIAGEDESK_ENV_FILE")` with **no hardcoded fallback path** — Task 1's original
scaffolding had defaulted to a literal Windows path
(`C:\Users\Wonton Soup\.secrets\credentials.env`), which the project's council had flagged as an
item to fix. Squash subcommit: "fix: env-file path from TRIAGEDESK_ENV_FILE only, no hardcoded
default (#4)" (co-authored `Claude Fable 5`). Confirmed present verbatim in the current
`triagedesk/config.py`. Cai set `TRIAGEDESK_ENV_FILE` via `setx` on his machine as a result;
subagents must export it for test runs (recorded standing instruction).

## How it was verified

At merge, `tests/unit/test_precheck_classify.py` held 4 tests: the plan's 3
(`test_precheck_safe_ticket`, `test_precheck_injection_flagged`, `test_classify_records_queue`)
plus the fix loop's `test_classify_records_usage_for_every_response` — matching the current
file's test count exactly (4 tests today, confirmed by reading the file).

## Review outcome and fix loop

Ledger: "Task 6: complete (commits 0fe1c3f..20fb882 on feat/04-precheck-classify; PR #23
squash-merged as 208be4c; issue #4 CLOSED + closeout comment; review approved after 1 fix
loop)."

**Fix loop** (squash subcommit: "test: assert record_llm_usage fires once per structured_call
response (#4)"): the `FakeTracer` test double was given a `usage_calls` counter, and a new test
(`test_classify_records_usage_for_every_response`) was added driving a 2-response fake to prove
`record_llm_usage` fires once per response returned by `structured_call` — including responses
from a repair attempt, not just the final successful one.

## Findings deferred

Ledger: "Minor deferred: precheck verdict.reason not written to span attrs (brief-faithful;
Task 9 surfaces via return value)." As shipped by this task, `run_precheck`'s
`tracer.set_attributes(...)` call set only `triage.precheck.safe` and
`triage.precheck.category` — `verdict.reason` (the one-sentence human-readable explanation for
an unsafe verdict) was not written into the span's attributes. This was faithful to the plan's
own code, not an implementer shortcut; Task 9 was noted as surfacing the reason via the
function's return value instead of the trace at that point.

## Also this cycle (same PR, adjacent work)

Not part of this task's own commits, but recorded in the same closeout comment: CI had been
silently red since Task 2 (`pytest` in CI vs `python -m pytest` locally — a `sys.path`
difference causing `ModuleNotFoundError: triagedesk` in every CI run). Fixed separately in PR
#24 (`pythonpath=["."]` in `pyproject.toml`, merged `02a4cef`); `feat/04-precheck-classify` was
updated from `main` (`0fe1c3f`) so this PR's own CI would go green. Branch protection was added
on `main` at the same time, requiring the `test` check green (and the branch up to date) before
merge — the controller is now required to run `gh pr checks --watch` before every merge as a
process fix (PRs #20–#22 had been merged without checking, which is how the CI breakage went
unnoticed for two tasks).

## Later changes

The deferred minor above (`verdict.reason` missing from span attrs) **was fixed** in the Week 1
QA hardening pass (issue #28). Ledger's QA hardening entry (commit 3): "precheck verdict.reason
→ span attrs." Confirmed in the current `triagedesk/pipeline/precheck.py`:

```python
tracer.set_attributes(
    span,
    **{
        "triage.precheck.safe": verdict.safe,
        "triage.precheck.category": verdict.category,
        "triage.precheck.reason": verdict.reason,
    },
)
```

— and the current `tests/unit/test_precheck_classify.py::test_precheck_injection_flagged`
asserts on `tracer.spans[0][1].attributes["triage.precheck.reason"]`, which would not have
passed against Task 6's originally shipped `precheck.py`. This confirms both the production
code and its test were updated together, after this task, during QA hardening.

## Commits / PR

- Commits `0fe1c3f..20fb882` on `feat/04-precheck-classify` (Task 6 portion; branch started at
  Task 5).
- PR #23: "feat: shared LLM client with retries + structured output repair policy" (title
  reflects Task 5 since the PR was opened before Task 6 landed; `Closes #4`) — squash-merged
  together with Task 5 as `208be4c`. Relevant squash subcommits: "feat: pre-check + classify
  stages with mocked-LLM tests (#4)" (original, co-authored `Claude Fable 5`), "fix: env-file
  path from TRIAGEDESK_ENV_FILE only, no hardcoded default (#4)" (ride-along, co-authored
  `Claude Fable 5`), "test: assert record_llm_usage fires once per structured_call response
  (#4)" (fix loop, co-authored `Claude Fable 5`).
- Issue #4 closed by PR #23; closeout comment covers both Task 5 and Task 6 (see
  `task-5-schemas-llm-client.md`).

## Sources used

Ledger (`progress-backup.md` lines 18–24), `gh issue view 4 --comments`, `gh pr view 23 --json
title,body`, `git show --stat 208be4c` (full subcommit message list), `docs/week-1-pipeline/
PLAN.md` (Task 6 section), current `triagedesk/prompts.py`, `triagedesk/pipeline/precheck.py`,
`triagedesk/pipeline/classify.py`, `triagedesk/config.py`, `tests/unit/test_precheck_classify.py`.
