> **⚠️ RECONSTRUCTED REPORT.** The original agent report for this task was destroyed by a
> filename collision (Week 2's `task-N-report.md` files overwrote Week 1's). This document
> was rebuilt from surviving evidence: the engineering ledger, the GitHub issue closeout
> comment (#2), PR #21 and its merged diff (squash commit `67d6f3b`), and the code as it
> stands. Facts here are traceable to those sources; anything that could not be recovered is
> marked *(not recovered)* rather than guessed.

# Task 3 (Issue #2, part B): Dataset ingest script

## Status
✅ DONE — merged as part of PR #21 (squash commit `67d6f3b`); issue #2 closed.

## What was built

Branch `feat/02-db-ingest` (continuation of Task 2), commits `680b6b1..e31f45e`.

- **`scripts/__init__.py`** (new, empty) — makes `scripts` importable from tests.
- **`scripts/ingest_tickets.py`** (new) — `row_to_ticket(row: dict) -> Ticket | None`, a pure
  function: returns `None` for non-English rows (`row["language"] != "en"`) and for rows with
  an empty/whitespace body; otherwise builds a `Ticket` with `source="kaggle"`, `language="en"`.
  `main()` is a CLI (`python -m scripts.ingest_tickets [--limit N] [--csv PATH]`) that streams
  the Kaggle CSV via `csv.DictReader`, batches commits every 1000 inserted rows, and prints a
  running count.
- **`tests/unit/test_ingest_parsing.py`** (new) — 3 unit tests against `row_to_ticket`:
  `test_english_row_maps_to_ticket`, `test_german_row_is_skipped`, `test_empty_body_is_skipped`.
  This matches the plan exactly and matches the current file's test count (3).

## How it was verified

`pytest tests/unit/test_ingest_parsing.py -v` — 3 passed *(exact pass/fail transcript at merge
time not recovered verbatim; the plan specifies these 3 test names and current code/tests match
them exactly, so the count is verifiable from the surviving code, not just claimed)*.

**Real ingest run against the dev Neon branch:** **11,922 English tickets** inserted. The
GitHub issue #2 closeout comment states this was independently proven exact by the reviewer,
who separately parsed the CSV: 11,923 English-language rows total, exactly 1 with an empty
body → 11,922 net inserted. This figure is also recorded in the project's `CLAUDE.md` status
line ("11,922 tickets live").

## Review outcome and fix loop

Ledger: "Task 3: complete (commits 680b6b1..e31f45e on feat/02-db-ingest; PR #21 squash-merged
as 67d6f3b; issue #2 closed; review approved after 1 fix loop)."

**Fix loop:** the script's docstring documented direct invocation (`python
scripts/ingest_tickets.py`), which is broken — it can't import the `triagedesk` package run
that way. Fixed to document the working form: `python -m scripts.ingest_tickets` (commit
`e31f45e`, squashed subject: "fix: document working -m invocation for ingest script (#2)"). The
plan's later script invocations (for Tasks 7/9's `scripts/embed_kb.py` and
`scripts/compute_centroids.py`) were also corrected on `main` at the same time to prevent a
repeat of the same mistake.

## Findings deferred

Ledger records three minor findings, all noted as **verbatim from the plan's own reference
code** (i.e., not implementer-introduced defects):

1. The ingest loop has no rollback/close guard on a mid-loop exception (a crash partway through
   leaves the session open / partially committed).
2. The CSV was opened without `newline=""` (the canonical `csv` module recommendation on
   Windows/CRLF-containing fields).
3. `--limit 0` is treated as "no limit" because the check is `if args.limit and inserted >=
   args.limit` — `0` is falsy in Python, so `--limit 0` silently ingests everything instead of
   nothing.

## Later changes

- **(2) was fixed** in the Week 1 QA hardening pass (issue #28): the ledger's QA-hardening
  entry explicitly lists "ingest newline=''" as one of its commit-3 fixes. Confirmed in the
  current `scripts/ingest_tickets.py`: `open(args.csv, encoding="utf-8", newline="")`.
- **(1) and (3) remain as originally shipped** as far as this reconstruction can verify — the
  current file still has no try/except around the insert loop and still uses the falsy
  `if args.limit and ...` check. *(Not recovered whether either was revisited outside the QA
  hardening pass; current code shows no fix.)*

## Commits / PR

- Commits `680b6b1..e31f45e` on `feat/02-db-ingest` (Task 3 portion; branch started at Task 2).
- PR #21: "feat: DB schema v1 + Alembic + ticket read endpoint (#2, part A)" (title reflects
  Task 2 since the PR was opened before Task 3 landed) — squash-merged together with Task 2 as
  `67d6f3b`. Squash message subcommits: "feat: DB schema v1 + alembic + ticket read endpoint
  (#2)" (Task 2), "feat: Kaggle dataset ingest script (#2)" (this task), "fix: document working
  -m invocation for ingest script (#2)" (this task's fix loop).
- Issue #2 closed by PR #21; closeout comment covers both halves (see
  `task-2-db-models-alembic.md`).

## Sources used

Ledger (`progress-backup.md` lines 6–10), `gh issue view 2 --comments`, `git show --stat
67d6f3b` (subcommit messages), `docs/week-1-pipeline/PLAN.md` (Task 3 section), current
`scripts/ingest_tickets.py`, `tests/unit/test_ingest_parsing.py`, `CLAUDE.md` status line.
