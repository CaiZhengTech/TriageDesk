# Task 8 (Issue #6) report — act loop + tools

## Implemented

- `triagedesk/seed_accounts.json` — verbatim from brief (12 seeded customers, customer-3 = Dana, basic plan).
- `triagedesk/tools.py` — verbatim from brief: `customer_ref_for`, `lookup_account_status`, `check_entitlement`, `PLAN_ENTITLEMENTS`, `TOOL_DEFS` (3 tool schemas incl. `submit_resolution` with `strict: True`), `execute_tool` dispatcher.
- `triagedesk/pipeline/act.py` — verbatim from brief: `MAX_ITERATIONS = 5`, `AgentIncompleteError`, `ToolFailedError`, `ActOutcome` dataclass, `run_act(ticket, classify_result, retrieval, tracer, _client=None)`. Only change from the brief's literal text: `ruff check --fix` split the two-name `triagedesk.llm` import onto two lines (`from triagedesk.llm import PIPELINE_MODEL` / `from triagedesk.llm import client as default_client`) — pure formatting, no logic change.
- `tests/unit/test_act_loop.py` — the brief's 4 tests unchanged, plus 2 new fixture-driven tests (see below). 6 total.

## Fixture vs. brief

No conflicts. Verified each of the 4 fixture findings against the brief's already-written loop code before writing tests:
1. Parallel tool calls (fixture turn0: `lookup_account_status` + `check_entitlement` in one response) — the loop already iterates all `tool_uses` and appends one `tool_result` per `tool_use_id`. Added `test_parallel_tool_calls_executed_in_one_turn` using the fixture's real block IDs, asserting both tools ran and the next turn's user message carries exactly 2 tool_results keyed by those IDs.
2. Every response carries a `thinking` block — added a `thinking_block()` helper (SimpleNamespace with `type="thinking"`) and included it (with a `text_block()`) in the two new fixture-driven tests so the `.type == "tool_use"` filter has real non-tool blocks to skip.
3. `max_tokens` truncation (fixture truncation-probe: no `tool_use`, `stop_reason == "max_tokens"`) — the brief's existing `if not tool_uses: if stop_reason == "pause_turn": continue; raise AgentIncompleteError(...)` already routes this correctly since `"max_tokens" != "pause_turn"`. Added `test_max_tokens_truncation_is_incomplete` asserting `AgentIncompleteError` with no exception and exactly 1 API call.
4. Usage shape — kept the brief's `usage()` helper (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`); did not shrink it.

No brief code needed to change to satisfy the fixture — the loop's block-filtering, parallel-tool iteration, and stop_reason handling were already correct.

## Tested

`.venv/Scripts/python -m pytest tests/unit/test_act_loop.py -v` → 6 passed.

Full suite (`TRIAGEDESK_ENV_FILE` exported): `.venv/Scripts/python -m pytest -v` → **28 passed**, 1 warning (the ledgered `StarletteDeprecationWarning` from `fastapi.testclient`, pre-existing/expected). `ruff check .` → all checks passed.

## TDD evidence

Wrote `tests/unit/test_act_loop.py` before `triagedesk/pipeline/act.py` existed — first run failed with `ModuleNotFoundError: triagedesk.pipeline.act` (module missing), confirming the tests were exercising real import paths, not vacuously passing. Implemented `tools.py` + `act.py` per brief, tests then passed on first run (brief's code + fixture-driven fakes required no iteration).

## Files changed

- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\triagedesk\seed_accounts.json` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\triagedesk\tools.py` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\triagedesk\pipeline\act.py` (new)
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\tests\unit\test_act_loop.py` (new)

## Self-review

- **Completeness:** all 4 files present; 6 tests (brief's 4 + 2 fixture-driven). Names match brief exactly — `run_act`, `ActOutcome`, `AgentIncompleteError`, `ToolFailedError` all importable from `triagedesk.pipeline.act` for Task 9 to consume.
- **Fidelity:** fakes structurally mirror the fixture (parallel tool_use blocks with real IDs from turn0, thinking blocks present, max_tokens truncation shape from truncation-probe).
- **Discipline:** implementation is the brief's code verbatim (only ruff's import-line-split touched it); test additions are strictly the two fixture-driven cases called for, no scope creep.
- **Testing:** output pristine except the ledgered warning.

## Concerns

None. No blockers, no fixture/brief conflicts requiring a stop-and-report.

## Commit / PR

- Commit `203463d` — "feat: hand-written act loop + simulated account tools (#6)" on `feat/06-act-loop` (head was `dcf8a3b`, the fixture commit).
- Pushed to `origin/feat/06-act-loop`.
- PR opened (not merged): https://github.com/CaiZhengTech/Agentic_Project/pull/26

## Fix report (review findings, 2026-07-11)

Two Important findings from PR review on `203463d`, both fixed on the same branch.

### Finding 1 — order-dependent `entitlement_denied` on the adverse-action path

**What:** `run_act`'s per-turn tool loop iterated `tool_uses` in content order and
returned immediately on the first `submit_resolution` block. A response ordered
`[submit_resolution, check_entitlement]` would return before `check_entitlement`
ever ran, silently dropping the `entitlement_denied` signal — one of the gate's two
adverse-action signals — even when the plan doesn't actually cover the feature.

**Why it matters:** the adverse-action rule (project CLAUDE.md) depends on
`entitlement_denied` being reliably set whenever `check_entitlement` returns
`covered: false`, regardless of what order the model emits tool_use blocks in.
Block order is a model-output detail, not something the loop should be able to
depend on for correctness.

**Fix (`triagedesk/pipeline/act.py`):** split `tool_uses` into `submit` (the single
`submit_resolution` block, if present) and `others` (everything else). All `others`
are now executed first, unconditionally, updating `entitlement_denied` as before.
Only after that loop does the code check `submit is not None` and return the
`ActOutcome` — so a same-turn `check_entitlement` always runs before
`submit_resolution` is honored, no matter which block came first in
`response.content`. Tracing calls (`tracer.set_attributes`), the `results`
tool_result construction, and the assistant/user message append on the
non-terminal path are all unchanged in behavior — only the control flow was
reordered.

### Finding 2 — no test pinned the LLM call config

**What:** `FakeMessages.create` captured full call kwargs (`client.messages.calls`)
but no test asserted on them, so a regression to the model name, `max_tokens`,
thinking config, output effort, or tool schema wiring would pass silently.

**Fix (`tests/unit/test_act_loop.py`):** added assertions to the existing
`test_happy_path_lookup_then_resolve` on `client.messages.calls[0]`: `model ==
PIPELINE_MODEL` (imported from `triagedesk.llm`), `max_tokens == 4096`, `thinking
== {"type": "adaptive"}`, `output_config == {"effort": "high"}`, `len(tools) == 3`,
and that the `submit_resolution` tool def has `strict: True`.

### New regression test

Added `test_submit_resolution_with_parallel_entitlement_check`: a single fake
response with content ordered `[thinking, submit_resolution ("solve"),
check_entitlement]` — submit deliberately BEFORE the entitlement check. Monkeypatches
`triagedesk.pipeline.act.execute_tool` (same pattern as the existing
`test_tool_error_retries_once_then_escalates`) to return `covered: False` for
`check_entitlement` and count invocations. Asserts: outcome resolution type is
`"solve"`, `entitlement_denied is True`, and the entitlement tool was actually
called exactly once — i.e. it wasn't skipped by the early-return.

### Commands run

```
export TRIAGEDESK_ENV_FILE="C:\Users\Wonton Soup\.secrets\credentials.env"
.venv/Scripts/python -m pytest tests/unit/test_act_loop.py -v   # 7 passed
.venv/Scripts/python -m pytest -q                                # 29 passed, 1 ledgered warning
.venv/Scripts/python -m ruff check .                              # All checks passed!
```

### Result

- `tests/unit/test_act_loop.py`: 7 passed (was 6; added the new regression test).
- Full suite: 29 passed, only the pre-existing ledgered `StarletteDeprecationWarning`.
- `ruff check .`: all checks passed, no new lint debt.
- Commit `a324592` — "fix: execute parallel tools before honoring submit_resolution
  (adverse-action hardening) (#6)" on `feat/06-act-loop`, pushed to
  `origin/feat/06-act-loop`.

### Files changed

- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\triagedesk\pipeline\act.py`
- `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project\tests\unit\test_act_loop.py`
