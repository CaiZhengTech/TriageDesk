> **⚠️ RECONSTRUCTED REPORT.** The original agent report for this task was destroyed by a
> filename collision (Week 2's `task-N-report.md` files overwrote Week 1's). This document
> was rebuilt from surviving evidence: the engineering ledger, the GitHub issue closeout
> comment (#4), PR #23 and its merged diff (squash commit `208be4c`), the plan document's own
> superseded-code callout, and the code as it stands. Facts here are traceable to those
> sources; anything that could not be recovered is marked *(not recovered)* rather than guessed.

# Task 5 (Issue #4, part A): Shared LLM client + schemas — and the origin of the SDK-reality rule

## Status
✅ DONE — merged as part of PR #23 (squash commit `208be4c`). This is the task the project's
standing **SDK-reality rule** traces back to.

## What was built

Branch `feat/04-precheck-classify`, commits `cb66aca..8e3e55e`.

- **`triagedesk/schemas.py`** (new) — `QUEUES` (tuple of the 10 real dataset queue labels),
  `Queue` (matching `Literal`), `PrecheckVerdict` (`safe: bool`, optional
  `category: Literal["injection","pii","off_topic"]`, optional `reason`), `ClassifyResult`
  (`queue: Queue`, free-text `category`), `Resolution` (`resolution_type:
  Literal["solve","deny","needs_human"]`, `customer_reply`, `internal_rationale` — the `deny`
  variant is what the adverse-action gate later keys on).
- **`triagedesk/llm.py`** (new) — `PIPELINE_MODEL = "claude-sonnet-4-6"`, a module-level
  `client = Anthropic(max_retries=3, timeout=60.0)`, `structured_call(...)`, and exception types
  `RepairFailedError` / `LLMRefusalError`.
- **`tests/unit/test_llm_repair.py`** (new).

## The big story: `structured_call` was broken against the real SDK despite 4 green mocked tests

This is the incident the project's `CLAUDE.md` calls out by name and the plan's Global
Constraints now enshrine as a standing rule. It is documented in three independent places
(ledger, issue #4 closeout comment, and a callout left directly in `docs/week-1-pipeline/
PLAN.md` above the Task 5 code block) that agree on the mechanism.

**As planned**, `structured_call` used `anthropic.messages.parse(output_format=schema)` and
branched on `response.parsed_output is None` to decide whether to trigger the one-repair
re-prompt. All 4 of the plan's mocked tests (first-try success, one-repair-then-success,
repair-failure-escalates, refusal-raises) passed — because the hand-written fakes simulated a
response shape (`parsed_output=None`) that the real SDK never actually produces.

**What review found**, reading the installed SDK's actual source (`anthropic==0.116.0`):

1. `messages.parse()` validates the model's output **eagerly, inside the SDK call**, and raises
   a `pydantic_core.ValidationError` *before ever returning* on a validation failure. The
   `if response.parsed_output is None` branch was therefore dead code — the repair path and
   `LLMRefusalError` could never fire, because the function would have already raised (an
   unhandled exception) rather than returning a response object to branch on.
2. The planned repair turn appended a second `user`-role message directly after the first,
   without an intervening `assistant` turn — the Messages API requires alternating roles and
   would 400 on two consecutive `user` messages.
3. `output_format=` is a deprecated parameter on the installed SDK version.

**The redesign** (commit `8e3e55e`, squash subcommit: "fix: structured_call — self-validated
output_config.format, reachable repair path (#4)"): switched from `messages.parse()` to
`messages.create()` with `output_config={"format": {"type": "json_schema", "schema": ...}}`
(constrained decoding) and validates the returned text **ourselves** via
`schema.model_validate_json(text)` — so a validation failure is the codebase's own control flow,
not an exception the SDK throws away the response for. The repair turn now appends the
assistant's prior response before the next user turn (satisfying role alternation) and includes
the real Pydantic validation errors in the repair prompt so the model knows what to fix. Both
exception types were given a shared `StructuredCallError` base carrying `.responses`, so even a
failed attempt's token usage stays recordable by the caller.

Re-review explicitly re-verified the redesigned code against the installed SDK's real types
(not just against the plan's assumed shapes) before approving.

**Consequence — the SDK-reality rule.** This is recorded as the root-cause incident behind the
standing rule now in `docs/week-1-pipeline/PLAN.md`'s Global Constraints: *before writing code
against any new Anthropic SDK surface (endpoint, stop reason, block type, tool-use shape), run a
live smoke call first and commit the observed response shape as a test fixture; build mocks from
the fixture, never from remembered/planned API shapes.* Task 8 (the act loop) was explicitly
gated on this rule as a direct result. The plan document itself carries a permanent callout
above the old Task 5 code block flagging it as superseded, pointing to `triagedesk/llm.py` at
commit `8e3e55e` as authoritative.

Root cause, in the issue #4 closeout comment's own words: *"code and tests written from
remembered API shapes, with fakes simulating a state the real SDK never produces."*

## How it was verified

At merge, `tests/unit/test_llm_repair.py` held the 4 tests the PR #23 body enumerates:
`test_first_try_success`, `test_one_repair_then_success`, `test_repair_failure_escalates`,
`test_refusal_raises` — "All 4 new unit tests pass" (PR #23 body's test plan) against the
redesigned `structured_call`, re-verified post-redesign. A 5th test present in the file today,
`test_schema_objects_forbid_additional_properties`, was **not** part of this task — it was added
later by Task 9 (confirmed by Task 9's own surviving report: "count went 4→5"), covering a
different, later-discovered API constraint (`additionalProperties: false`).

## Review outcome

Ledger: "Task 5: complete (commits cb66aca..8e3e55e on feat/04-precheck-classify; PR #23 OPEN
pending Task 6 — issue #4 spans both; review approved after 1 major fix loop)." — the fix loop
described above.

## Findings deferred

Ledger: "Minor deferred: text-join silently yields `""` on non-text content (falls into the
repair path — implicit but handled)." `structured_call`'s `"".join(b.text for b in
response.content if b.type == "text")` produces an empty string if the response contains no text
blocks (e.g., only tool_use or thinking blocks); an empty string fails Pydantic validation and is
correctly routed into the repair path, but not via an explicit, named check.

## Later changes (not part of this task)

Comparing the current `triagedesk/llm.py` to what shipped here:

- **`temperature` parameter** — the current `structured_call` accepts an optional
  `temperature: float | None = None`, passed through to the API only when explicitly set. This
  was added for the Week 2 judge (spec: "pinned model, temp 0"), not part of Task 5's original
  interface.
- **Prompt-cache control** — the current code sends `system` as a list of content blocks with
  `"cache_control": {"type": "ephemeral"}`, rather than the plain string Task 5 shipped. This is
  Week 2's prompt-caching work, not Task 5.
- **`_strict_schema()`** — the current file recursively stamps `additionalProperties: false`
  onto every `"object"` node in the JSON schema sent to the API. This was added in **Task 9**
  (issue #7), after a live E2E run 400'd because Pydantic's `model_json_schema()` doesn't emit
  that field — not part of Task 5.

None of these later additions change the interface Task 5 committed to (`structured_call`'s
required parameters, `RepairFailedError`, `LLMRefusalError`) — they are additive.

## Commits / PR

- Commits `cb66aca..8e3e55e` on `feat/04-precheck-classify` (Task 5 portion; the branch
  continued into Task 6 before the PR was opened/merged).
- PR #23: "feat: shared LLM client with retries + structured output repair policy" (`Closes #4`)
  — squash-merged together with Task 6 as `208be4c`. Relevant squash subcommits: "feat: shared
  LLM client with retries + structured output repair policy (#4)" (original), "fix:
  structured_call — self-validated output_config.format, reachable repair path (#4)" (the major
  fix loop, co-authored `Claude Fable 5`).
- Issue #4 closed by PR #23 (closeout comment covers both Task 5 and Task 6; see
  `task-6-precheck-classify.md`).

## Sources used

Ledger (`progress-backup.md` line 14–17), `gh issue view 4 --comments`, `gh pr view 23 --json
title,body`, `git show --stat 208be4c` (full subcommit message list), `docs/week-1-pipeline/
PLAN.md` (Task 5 section and its "SUPERSEDED IN REVIEW" callout), current `triagedesk/llm.py`,
`triagedesk/schemas.py`, `tests/unit/test_llm_repair.py`, `docs/week-1-pipeline/reports/
task-9-gate-cli-e2e-checkpoint.md` (for the 4→5 test-count pointer).
