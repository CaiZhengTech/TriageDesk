# Week 1 QA Hardening — Report

Branch `chore/week1-qa` (base `add1784`) → PR [#29](https://github.com/CaiZhengTech/Agentic_Project/pull/29)
("Week 1 QA hardening: gate entitlement evidence, fail-closed typing, test gaps, CI (#28)").
Refs #28 (not Closes — Week-2 items remain on that issue).

All work was pure logic/tests/config. No live Anthropic API calls were made anywhere in this
task; every test uses fakes/monkeypatch/fixture shapes, matching the constraints in the brief.

---

## Commit 1 — `4dca30d` — Gate structural fix (council mandate)

**Defect:** `gate.decide()` escalated on `resolution_type=="deny"` or `entitlement_denied`, but
a soft denial written into `customer_reply` with `resolution_type=="solve"` and *no*
`check_entitlement` call ever made would pass the adverse-action check and (with good
similarity/margin) auto-resolve. The adverse-action guarantee was enforced by model
cooperation, not gate structure.

**Signature adaptation note:** the task brief described `gate.decide()` as currently taking
"the resolution, entitlement_denied flag, retrieval similarity, and classification margin" as
separate parameters. The actual code takes `outcome: ActOutcome` as one object (which itself
carries `resolution` and `entitlement_denied`), plus `retrieval_similarity` and `margin` as
independent kwargs. I preserved this exact style: `entitlement_checked` was added as a new
independent keyword-only parameter to `decide()` (mirroring how `retrieval_similarity`/`margin`
are independent of `outcome`), rather than folding it into `outcome` reads. `runner.py` passes
it through explicitly (`entitlement_checked=outcome.entitlement_checked`), matching the brief's
"pass the new field through from ActOutcome to decide()" instruction literally.

**Fix implemented:**
- `triagedesk/pipeline/act.py`: `ActOutcome` gains `entitlement_checked: bool` (True iff at
  least one `check_entitlement` tool call executed during the loop, regardless of result). Set
  alongside `entitlement_denied` tracking in the tool-execution loop. Recorded as span attribute
  `triage.act.entitlement_checked` next to `triage.act.entitlement_denied`.
- `triagedesk/pipeline/gate.py`: `decide()` gains `entitlement_checked: bool` (keyword-only).
  New ordering (adverse-action still absolutely first):
  1. `resolution_type=="deny"` OR `entitlement_denied` → escalate `adverse_action`
  2. `resolution_type=="needs_human"` → escalate `agent_requested_human`
  3. **NEW:** `resolution_type=="solve"` and NOT `entitlement_checked` → escalate,
     reason `no_entitlement_evidence`
  4. thresholds (similarity/margin) as before
  `entitlement_checked` is also included in `GateDecision.signals`, so it flows into the gate
  span's trace attrs via the existing `**decision.signals` merge in `runner.py` — the gate's
  inputs are evidence and must be visible in traces.
- `triagedesk/pipeline/runner.py`: passes `entitlement_checked=outcome.entitlement_checked`
  into `decide()`.

**TDD evidence — failing test BEFORE the fix:**

Added `test_solve_without_entitlement_evidence_escalates` to `tests/unit/test_gate.py` (only
this test — no other changes yet), then ran it against the unmodified code:

```
$ .venv/Scripts/python -m pytest tests/unit/test_gate.py -v
...
tests/unit/test_gate.py::test_solve_without_entitlement_evidence_escalates FAILED [100%]

================================== FAILURES ===================================
______________ test_solve_without_entitlement_evidence_escalates ______________

    def test_solve_without_entitlement_evidence_escalates():
>       d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("solve"),
                   entitlement_checked=False)
E       TypeError: decide() got an unexpected keyword argument 'entitlement_checked'

tests\unit\test_gate.py:64: TypeError
=========================== short test summary info ===========================
FAILED tests/unit/test_gate.py::test_solve_without_entitlement_evidence_escalates
========================= 1 failed, 8 passed in 2.06s ==========================
```

Then implemented the fix and updated all existing call sites:
- `tests/unit/test_gate.py`: `outcome()` helper gains a `checked=True` default param; all
  existing `decide()` calls pass `entitlement_checked=True` explicitly to preserve their
  original intent (auto-resolve / threshold / adverse-action paths unaffected); the new test
  uses `checked=False, entitlement_checked=False`; `test_confident_solve_auto_resolves`'s
  `signals` assertion updated to include the new `entitlement_checked` key.
- `tests/unit/test_runner.py`: `outcome()` helper gains the same `checked=True` default. Added
  `test_solve_without_entitlement_evidence_escalates` — act returns solve without entitlement
  evidence → run ends `escalated`/`no_entitlement_evidence`.
- `tests/unit/test_act_loop.py`: added
  `test_entitlement_checked_reflects_check_entitlement_tool_execution` — asserts
  `entitlement_checked` is `True` after a `check_entitlement` tool execution and `False` when
  only `lookup_account_status` ran.

**Post-fix run** (gate + runner + act-loop): 29 passed.

**Design note (preserved in commit message):** this deliberately makes auto-resolve stricter —
a solve with no entitlement evidence escalates even for tickets where no feature is involved.
Fail-closed is the project's default posture; Week 2's calibration table will quantify the
auto-resolve rate and the threshold review can revisit.

---

## Commit 2 — `bfe7505` — Tracing fail-closed typing + cost edge tests

**Defect:** `RunTracer.record_llm_usage` read `response.model` / `response.usage` as bare
attribute access before calling `compute_cost`. A response missing either attribute entirely
(not just missing fields inside `.usage`, which `compute_cost` already guarded via `getattr`)
raised a plain `AttributeError`, not `CostUnknownError` — breaking the literal fail-closed
invariant, since `AttributeError` isn't caught by the runner's `(BudgetExceededError,
CostUnknownError)` handler and would fall through to the generic `Exception` branch (`failed`,
not `escalated`/`budget_breach`).

**Fix:** `record_llm_usage` now does `getattr(response, "model", None)` /
`getattr(response, "usage", None)` and raises `CostUnknownError` explicitly if either is
`None`, before calling `compute_cost`. `CostUnknownError`'s existing import/location in
`triagedesk/tracing.py` was kept — no duplicate exception created.

**Tests added to `tests/unit/test_tracing.py`:**
- `test_record_llm_usage_missing_usage_fails_closed` — malformed response (no `.usage` at all)
  → `CostUnknownError`
- `test_record_llm_usage_zero_tokens_no_breach` — zero-token usage → cost `0.0`, no breach
- `test_record_llm_usage_cache_only_computes_correct_cost` — usage with only
  `cache_creation_input_tokens`/`cache_read_input_tokens` (0 input/output) → cost computed
  correctly ($0.00405 for 1000/1000 cache-write/cache-read tokens)
- `test_record_llm_usage_exactly_at_cap_is_not_a_breach` — cost exactly equal to
  `cost_cap_usd` does NOT raise `BudgetExceededError` (asserts the deliberate `>` boundary, not
  `>=`)

**Test added to `tests/unit/test_runner.py`:** `test_cost_unknown_maps_to_escalated_budget_breach`
— pins that `CostUnknownError` raised from a stage maps to `escalated`/`budget_breach` at the
runner level (it shares the handler with `BudgetExceededError`).

**Run:** tracing + runner tests: 25 passed.

---

## Commit 3 — `04d61ea` — Remaining test-gap and polish minors

1. `tests/unit/test_runner.py`: added `test_agent_requested_human_escalates` — gate returns
   `agent_requested_human` → run ends `escalated`/`agent_requested_human` (runner-level).
2. `tests/unit/test_act_loop.py`: added `test_pause_turn_continues_loop_without_tool_use` — a
   response with `stop_reason=="pause_turn"` and no tool_use blocks (built with the same
   `thinking_block()`/`text_block()`/`response()` helpers the neighboring tests use, which
   mirror the committed fixture's field shapes) must append the assistant turn and continue,
   not raise `AgentIncompleteError`. Asserts a second call is made and the paused turn's
   assistant message is in the second call's `messages`.
3. `triagedesk/pipeline/precheck.py`: `verdict.reason` is now written into the precheck span
   attrs as `triage.precheck.reason`, alongside the existing `safe`/`category` attrs. Assertion
   added to `test_precheck_injection_flagged` in `tests/unit/test_precheck_classify.py`.
4. `triagedesk/cli.py`: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` moved from
   module level into `main()`, guarded with `if hasattr(sys.stdout, "reconfigure"):`.
5. `scripts/ingest_tickets.py`: CSV now opened with `newline=""` per the `csv` module docs.
6. `kb/reporting-security-concerns.md`: 5 occurrences of ASCII `->` replaced with `→` to match
   the rest of the KB corpus (verified via grep that every other KB doc already uses `→` and
   none use `->`). Cosmetic only — the doc is already embedded in the DB; not re-embedded per
   the brief's explicit instruction (Week 2 re-embeds if ever needed).

**Run:** runner + act-loop + precheck/classify + ingest-parsing tests: 30 passed.

---

## Commit 4 — `b7defe2` — CI hardening

`.github/workflows/ci.yml`:
1. Added workflow-level `concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }`.
2. Added `gitleaks/gitleaks-action@v2` as a step inside the existing `test` job (not a new job
   — branch protection requires the `test` check by name, so a separate job would not be
   covered and could fail silently), placed before the `pytest` step.
3. `actions/checkout@v4` now passes `fetch-depth: 0` so gitleaks has full commit history to
   scan.

Verified with `yaml.safe_load` that the file parses correctly. Confirmed on the live PR:
`gh pr checks 29` → `test  pass  47s`.

---

## Commit 5 — `8bf8cea` — Plan reconciliation note

Added a `> **SUPERSEDED IN QA (2026-07-12):** ...` blockquote immediately before the
`gate.py` code block in Task 9 of
`docs/week-1-pipeline/PLAN.md` (Step 4, right after the
`` `triagedesk/pipeline/gate.py`: `` file-path label), matching the exact placement and style
of the two existing "SUPERSEDED IN REVIEW" blockquotes found in the same file (for `llm.py`
and `act.py`).

**PR number:** used placeholder `#29` when writing this commit, anticipating this repo's next
PR number. The actual PR created was **#29** — an exact match, so **no follow-up/amend commit
was needed**.

---

## Finish — full verification

**Full suite:**

```
$ .venv/Scripts/python -m pytest -q
ss.........................................................              [100%]
57 passed, 2 skipped, 1 warning in 3.02s
```

(2 skips are pre-existing DB-integration tests requiring `TEST_DATABASE_URL`, not touched by
this work.)

**Ruff:**

```
$ .venv/Scripts/python -m ruff check .
All checks passed!
```

**PR:** https://github.com/CaiZhengTech/Agentic_Project/pull/29 — CI green (`test` check
passed).

---

## Deviations from the brief

1. **`decide()` parameter design (Commit 1).** The brief's "Context you need" section described
   `gate.decide()`'s *current* signature inaccurately (as if `resolution`/`entitlement_denied`
   were already separate top-level params). The task instructions explicitly told me to read
   the actual code and adapt, preserving style — this was flagged in advance as an
   approximation, not a real conflict, so I did not stop for `NEEDS_CONTEXT`. I implemented
   `entitlement_checked` as a new independent keyword-only parameter on `decide()` (matching
   the existing pattern for `retrieval_similarity`/`margin`), with `runner.py` passing
   `outcome.entitlement_checked` through explicitly — satisfying the brief's literal
   instruction ("`decide()` gains an `entitlement_checked: bool` parameter" / "pass the new
   field through from ActOutcome to decide()") while matching the file's existing style.
2. **`entitlement_checked` included in `GateDecision.signals`.** The brief said to "record the
   new signal in whatever GateDecision/span attrs pattern exists" without specifying exactly
   where. Since `signals` is the mechanism that already carries `retrieval_similarity` and
   `classification_margin` into the gate span's trace attrs via `**decision.signals`, I added
   `entitlement_checked` there too, so it's visible in traces the same way the other gate
   inputs are. This required updating `test_confident_solve_auto_resolves`'s exact-equality
   `signals` assertion.
3. Nothing else deviated from the brief's exact instructions. No ACCEPTED-from-#28 items,
   thresholds, dev DB, or `act.py`'s `str(result)` serialization were touched.
