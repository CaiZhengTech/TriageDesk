# Task 2 report: prompt caching in the pipeline

**Status:** DONE
**Branch:** `feat/wk2-prompt-caching` (off `26683ff`)
**Commit:** `11451d1` — feat: prompt caching on act-loop system + tools and structured_call system
**PR:** https://github.com/CaiZhengTech/Agentic_Project/pull/31 (not merged)

## What was built

Exactly the brief's three source changes, no deviations:

1. `triagedesk/tools.py` — `TOOL_DEFS[-1]` (`submit_resolution`) gained
   `"cache_control": {"type": "ephemeral"}` after `"strict": True,`.
2. `triagedesk/pipeline/act.py` — `run_act`'s `c.messages.create(system=ACT_SYSTEM, ...)`
   changed to `system=[{"type": "text", "text": ACT_SYSTEM, "cache_control": {"type": "ephemeral"}}]`.
3. `triagedesk/llm.py` — `structured_call`'s `c.messages.create(system=system, ...)`
   changed to `system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]`.

Test changes:

4. `tests/unit/test_tracing.py` — added `test_compute_cost_bills_cache_tokens` (verification
   test, brief's exact code, 1M cache-write + 1M cache-read tokens -> $4.05).
5. `tests/unit/test_prompt_caching.py` (new) — brief's exact 3 tests, with one mechanical
   fix: the multi-name import from `tests.unit.test_act_loop` was reflowed to a parenthesized
   multi-line import (ruff `I001` unsorted-imports + `E501` line-too-long on the single-line
   version at 104 chars against a 100-char limit). No behavioral change — same six names
   imported, alphabetized within the parens by ruff's `--fix`.

## Conflict check (none found)

Read `triagedesk/tools.py`, `triagedesk/pipeline/act.py`, `triagedesk/llm.py`,
`triagedesk/tracing.py`, and the three referenced existing test files
(`test_act_loop.py`, `test_precheck_classify.py`, `test_llm_repair.py`) before touching
anything. Everything matched the brief's assumptions exactly:
- `TOOL_DEFS[-1]` was indeed `submit_resolution` with `"strict": True`.
- `compute_cost` already read `cache_creation_input_tokens` / `cache_read_input_tokens`
  with rates `cache_write: 3.75`, `cache_read: 0.30` per MTok in `PRICES_PER_MTOK`.
- `run_act` and `structured_call` signatures were unchanged elsewhere — only the internal
  `system=` shape needed to change, as the brief said.

No NEEDS_CONTEXT triggers hit. No improvising required.

## TDD evidence

**Step 1 — verify cost accounting (should pass immediately, documenting existing behavior):**
```
$ .venv/Scripts/python -m pytest tests/unit/test_tracing.py::test_compute_cost_bills_cache_tokens -v
tests/unit/test_tracing.py::test_compute_cost_bills_cache_tokens PASSED  [100%]
1 passed in 0.21s
```
Passed immediately as expected — confirms the Wk2 budget math assumption in the Global
Constraints holds; no source change was needed for this step.

**Step 2 — write failing caching tests (expected: 3 failures):**
```
$ .venv/Scripts/python -m pytest tests/unit/test_prompt_caching.py -v
tests/unit/test_prompt_caching.py::test_submit_resolution_carries_cache_breakpoint FAILED
tests/unit/test_prompt_caching.py::test_act_loop_sends_cached_system_block FAILED
tests/unit/test_prompt_caching.py::test_structured_call_sends_cached_system_block FAILED
3 failed in 2.70s
```
Failures were exactly the brief's predicted shapes: `KeyError: 'cache_control'` on the tool
dict, and `assert isinstance(system, list)` failing because `system` was still a plain string
in both `act.py` and `llm.py`.

**Step 3 — implement the three source changes, then full suite:**
```
$ .venv/Scripts/python -m pytest -q
ss.............................................................  [100%]
61 passed, 2 skipped, 1 warning in 3.75s
```
2 skips are pre-existing and unrelated to this change (not investigated further — brief did
not ask for it). `test_llm_repair.py` and `test_act_loop.py` assertions on
`output_config`/`thinking`/`tools` shape and `"temperature" not in kwargs` are untouched by
this change, as the brief predicted, and passed unchanged.

## Ruff

```
$ .venv/Scripts/python -m ruff check .
All checks passed!
```
(First run flagged `I001`/`E501` on the new test file's import block; fixed by reflowing the
import to multi-line — see "Test changes" above. Second run clean.)

## Deviations from the brief

1. **Import formatting only** in `tests/unit/test_prompt_caching.py`: the brief's literal
   single-line import from `tests.unit.test_act_loop import CLASSIFY, RETRIEVAL, TICKET,
   make_client, response, RESOLUTION_CALL` violated this repo's ruff config (line length 100,
   import sort). Reflowed to a parenthesized multi-line import with the same six names,
   ruff-sorted. No test logic changed.
2. **Skipped the optional live sanity call** (`⚠️ LIVE ($~0.03, 1 call)` step). The brief
   marks it optional/controller-only and explicitly says to skip if budget is tight; the task
   instructions for this delegation said "$0 budget for this task — everything from
   fixtures/fakes," so it was skipped rather than run. The fixture-based tests already prove
   the cache_control shapes are correct; live confirmation of actual cache hits is deferred
   to the controller's discretion, per the brief.

No other deviations. All commit message text, file paths, and code snippets match the brief
verbatim.

## PR

Not merged, per instructions. https://github.com/CaiZhengTech/Agentic_Project/pull/31

## Note on this file

This report overwrites a stale `task-2-report.md` left over from an earlier, unrelated
"Task 2" (DB models + Alembic, PR #21) — that content is superseded; PR #21's history is
still on GitHub if needed.
