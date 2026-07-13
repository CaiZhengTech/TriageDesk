# Task 6 report — judge calibration TOOLING (issue #11)

**Scope note:** per the controller's binding constraints, this task built the
TOOLING ONLY. No human labeling was performed, no labels were fabricated or
simulated, and no kappa number was computed or reported. The controller runs
the live export → hands the CSV to Cai for a blind labeling pass → re-runs
import + calibrate.

## Branch / commit

- Branch: `feat/11-kappa` (off `01ae5a9`, current `main` at task start)
- Commit: `84dc044fb09f3f8545e887bd672aa53513407656`
  `feat: judge calibration tooling — blind human labels + Cohen's kappa (Refs #11)`
- PR: **https://github.com/CaiZhengTech/Agentic_Project/pull/38** (not merged)

## What was built

- `triagedesk/evals/kappa.py` — `cohens_kappa(labels_a, labels_b, categories=(...))`.
  Hand-rolled, `kappa = (po - pe) / (1 - pe)`, no scipy/sklearn/numpy.
- `triagedesk/evals/calibration.py`:
  - `export_labels(session, out_csv) -> int` — blind CSV over every
    `eval_results` row with a `judge_verdict`. Columns: `result_id,
    ticket_subject, ticket_body, kb_slugs, kb_excerpts, customer_reply,
    human_label`. No `judge_verdict`/`judge_reason`/`judge_rule_triggered`
    column, and no judge text leaks into any cell (tested by scanning the
    full file body, not just the header).
  - `import_labels(session, in_csv) -> int` — idempotent upsert of
    `human_label` by `result_id`; blank = "not labeled yet" (skipped);
    raises `ValueError` on any non-blank value outside
    `{pass, fail, needs_review}`.
  - `compute_kappa_report(session) -> dict` — returns `{n, kappa,
    kappa_undefined_reason, raw_agreement, confusion, disagreements}`.
    `confusion` is the full human×judge matrix (every category present,
    even at 0). `disagreements` lists every row where
    `human_label != judge_verdict`, with `judge_reason` attached.
- `triagedesk/evals/cli.py` — three new subcommands: `label-export --out
  <csv>`, `label-import <csv>`, `calibrate`. `calibrate` writes
  `results/judge-calibration.md` (confusion matrix table + disagreements
  table), rendering the `kappa: None` case as "undefined -- \<reason\>"
  instead of crashing on `.3f` formatting of `None`.
- `results/LABELING-INSTRUCTIONS.md` — plain-language rubric for Cai,
  mirroring `judge.py`'s `JUDGE_SYSTEM` rubric (grounding / helpfulness /
  tone; pass/fail/needs_review; abstain rather than guess), explains *why*
  the export is blind, includes a worked example (VPN-ticket, pass vs.
  fail-on-invented-credit variants).
- `.gitignore` — added `judge_labels*.csv` so the label CSV (contains
  ticket text) is never committed.
- `results/judge-calibration.md` was **not** created in this PR — it's
  written by the live `calibrate` run, not faked here.

## TDD evidence

### `tests/unit/test_kappa.py` (6 tests)

Written first; ran and confirmed **failure** (`ModuleNotFoundError:
No module named 'triagedesk.evals.kappa'`) before implementing
`kappa.py`. After implementing, all 6 pass:

```
tests/unit/test_kappa.py::test_perfect_agreement_is_one PASSED
tests/unit/test_kappa.py::test_chance_level_is_zero PASSED
tests/unit/test_kappa.py::test_known_value PASSED
tests/unit/test_kappa.py::test_mismatched_lengths_raise PASSED
tests/unit/test_kappa.py::test_empty_lists_return_nan PASSED
tests/unit/test_kappa.py::test_no_variation_both_raters_single_category_is_nan_not_crash PASSED
6 passed in 0.04s
```

**Hand-computed check of `test_known_value`'s 0.583 constant** (brief's
literal value, verified against the formula, not trusted blindly):

```
a = P P P P P P F F F F   (6 pass, 4 fail)
b = P P P P P F P F F F   (["pass"]*5 + ["fail"]*1 + ["pass"]*1 + ["fail"]*3)

index:  0 1 2 3 4 5 6 7 8 9
a:      P P P P P P F F F F
b:      P P P P P F P F F F
agree:  Y Y Y Y Y N N Y Y Y   -> 8 agree, 2 disagree (indices 5, 6)

po = 8/10 = 0.8
pa(pass)=6/10=0.6, pb(pass)=6/10=0.6  (b has 6 P's: idx 0,1,2,3,4,6)
pa(fail)=4/10=0.4, pb(fail)=4/10=0.4
pe = 0.6*0.6 + 0.4*0.4 = 0.36 + 0.16 = 0.52
kappa = (0.8 - 0.52) / (1 - 0.52) = 0.28 / 0.48 = 0.58333...
round(kappa, 3) == 0.583  ✓ matches brief's literal — no correction needed
```

Also hand-verified `test_perfect_agreement_is_one` (po=1, pe=0.375 from
3-category marginals 0.5/0.25/0.25 each squared and summed → kappa=1.0)
and `test_chance_level_is_zero` (po=0.5, pe=0.5 → kappa=0) before trusting
them. All three brief-supplied constants were correct as written; the
formula was not modified except for the degenerate `pe>=1.0` branch (see
Deviations below).

### `tests/unit/test_calibration.py` (14 tests, new — not in the brief's
minimal test list; added because the binding constraints required testing
blindness, idempotency, invalid-label rejection, and the degenerate-sample
report path)

Written first against a designed interface; ran and confirmed **failure**
(`ModuleNotFoundError: No module named 'triagedesk.evals.calibration'`)
before implementing `calibration.py`. After implementing, all 14 pass on
the first run — no back-and-forth needed:

```
test_export_writes_one_row_per_judged_result PASSED
test_export_csv_never_reveals_judge_verdict PASSED
test_export_includes_kb_excerpt_for_grading_context PASSED
test_export_handles_no_retrieved_docs PASSED
test_export_returns_zero_for_no_judged_rows PASSED
test_import_writes_human_label_onto_matching_row PASSED
test_import_skips_blank_labels_cai_only_labeled_some_rows PASSED
test_import_rejects_invalid_label PASSED
test_import_is_idempotent_safe_to_rerun PASSED
test_report_basic_shape PASSED
test_report_includes_full_confusion_matrix PASSED
test_report_lists_disagreements_with_reason PASSED
test_report_handles_zero_labeled_rows_without_crashing PASSED
test_report_handles_no_variation_degenerate_sample_without_crashing PASSED
14 passed in 0.22s
```

Notably `test_export_csv_never_reveals_judge_verdict` reads the entire
written file body (not just the header row) and asserts the judge's actual
verdict string (`"fail"`) and its reason text never appear anywhere in the
CSV — the strongest test of the blind-labeling requirement.

Fake-session pattern follows the existing convention in
`tests/unit/test_judge_backfill.py` / `test_harness.py`: DB-level
filtering (`.filter(...)`, `.order_by(...)`) is trusted SQLAlchemy and the
fake just returns whatever the test pre-loaded as already matching.

### Full suite + lint

```
pytest -q            -> 113 passed, 5 skipped (integration tests needing
                         TEST_DATABASE_URL — unaffected by this change)
ruff check .          -> All checks passed!
```

CLI wiring sanity-checked without any DB access (`--help` only, since
`SessionLocal` requires `TRIAGEDESK_ENV_FILE`):

```
$ python -m triagedesk.evals.cli --help
usage: triagedesk-evals [-h] {run,judge,label-export,label-import,calibrate} ...
```

All three new subcommands registered correctly.

## Deviations from the brief

1. **CSV gained one column, `kb_excerpts`, beyond the brief's literal list**
   (`result_id, ticket_subject, ticket_body, kb_slugs, customer_reply,
   human_label`). The task's own instructions (not just the brief) asked
   for "ideally titles/content or a trimmed excerpt" of the KB docs so a
   human can grade fairly — added a `[slug] Title: trimmed content...`
   excerpt (300 chars, newline-collapsed) per retrieved doc, joined with
   ` | `.
2. **Commit message and PR use "Refs #11" not "Closes #11"** — per the
   controller's instruction that the issue should close when calibration
   actually runs with real labels, not when this tooling merges.
3. **`cohens_kappa`'s `pe >= 1.0` branch returns `float("nan")` instead of
   the brief's literal `return 1.0`.** This is the one place I deviated
   from the brief's given code, and it's a direct instance of a binding
   constraint overriding the brief: *"if a category is unused by both
   raters, kappa's formula can divide by zero — return a clear result...
   rather than crashing or silently returning 0."*

   Reasoning: `pe` can only reach `1.0` when both raters' label
   distributions are each concentrated on a single matching category (by
   Cauchy-Schwarz on a probability distribution, `sum(p_c^2) = 1` iff one
   `p_c = 1`). But if that's true for both raters on the *same* category,
   `po` is *also* forced to `1.0` — every item is that category for both
   raters. So `(po - pe)/(1 - pe)` is `0/0`: mathematically undefined, not
   a clean "perfect agreement" `1.0`. The brief's `if pe >= 1.0: return
   1.0` silently papers over this — it would report `kappa=1.0` for a
   3-row sample where both Cai and the judge happened to label everything
   `pass`, which is statistically meaningless (there's no variance for the
   metric to explain) and misleading if `n` is otherwise small (exactly
   the "small/degenerate samples" scenario the constraint names). Returning
   `NaN` keeps `cohens_kappa` mathematically honest and consistent with its
   own existing `n == 0 -> NaN` convention; `compute_kappa_report` then
   surfaces this at the report layer as `kappa: None` +
   `kappa_undefined_reason: "no variation: human and judge both used only a
   single label category across all n rows, so chance agreement is 100%
   and kappa (po - pe) / (1 - pe) is 0/0 -- mathematically undefined"`.

   This is tested explicitly:
   `test_no_variation_both_raters_single_category_is_nan_not_crash` (kappa
   layer) and
   `test_report_handles_no_variation_degenerate_sample_without_crashing`
   (report layer, also asserts `raw_agreement == 1.0` is still reported
   correctly even though `kappa` is undefined — raw agreement and kappa
   are different questions and shouldn't both collapse to the same
   failure).

No other deviations. `import_labels`'s reject-invalid-label behavior,
`export_labels`'s blind column set (minus the one addition above), and the
CLI subcommand shapes all match the brief as given.

## Verified against binding constraints

- **Build TOOLING ONLY:** no pipeline runs, no judge calls, no labeling,
  no kappa number computed or committed. ✓
- **Kappa hand-rolled, no scipy/sklearn/numpy added:** `requirements`
  files untouched; `kappa.py` has zero imports. ✓
- **Blind export:** `judge_verdict` (and `judge_reason`,
  `judge_rule_triggered`) never appear in the CSV — verified by a test
  that scans the whole file body, not just the header. ✓
- **Idempotent import + label validation:** `test_import_is_idempotent_safe_to_rerun`
  and `test_import_rejects_invalid_label`. ✓
- **Degenerate-sample kappa handled honestly:** covered above. ✓
- **Report includes n, kappa, raw agreement, full confusion matrix, and
  disagreement rows (result_id + both labels + judge's reason):** all
  five fields present in `compute_kappa_report`'s return dict and rendered
  in `_render_calibration_md`. ✓
- **$0 Anthropic budget:** no live LLM calls anywhere in `kappa.py`,
  `calibration.py`, or their tests — everything is pure functions over
  fake/CSV data. ✓
- **`results/LABELING-INSTRUCTIONS.md` committed, plain-language, mirrors
  the judge's rubric exactly (grounding/helpfulness/tone,
  pass/fail/needs_review, abstain-rather-than-guess):** done. ✓
- **`results/judge-calibration.md` not created with fake numbers:**
  omitted entirely from this PR; `calibrate` CLI writes it on the real
  run. ✓

## Controller commands (run these, in order, after this PR merges or on
this branch before merging — your call)

```
python -m triagedesk.evals.cli label-export --out judge_labels.csv
```
Prints `exported <n> rows -> judge_labels.csv (label human_label as
pass|fail|needs_review)`. Cai then labels `human_label` blind per
`results/LABELING-INSTRUCTIONS.md` (do not open the run in the console or
DB first — that defeats blindness).

```
python -m triagedesk.evals.cli label-import judge_labels.csv
```
Prints `imported <n> human labels`. Safe to re-run if Cai labels in
batches — re-importing just overwrites `human_label` on the rows filled in
so far.

```
python -m triagedesk.evals.cli calibrate
```
Prints the full JSON report (`n, kappa, kappa_undefined_reason,
raw_agreement, confusion, disagreements`) and writes
`results/judge-calibration.md`. Commit that file (not `judge_labels.csv`
— it's gitignored via `judge_labels*.csv`).

## Files touched

- `triagedesk/evals/kappa.py` (new)
- `triagedesk/evals/calibration.py` (new)
- `triagedesk/evals/cli.py` (modified — 3 new subcommands + render helper)
- `tests/unit/test_kappa.py` (new, 6 tests)
- `tests/unit/test_calibration.py` (new, 14 tests)
- `results/LABELING-INSTRUCTIONS.md` (new)
- `.gitignore` (modified — `judge_labels*.csv`)

## Note on this report file

`.superpowers/sdd/task-6-report.md` previously contained a stale report
from an earlier task-numbering scheme (pre-check/classify work, now
merged as issue #4) — that directory is entirely gitignored
(`.superpowers/sdd/.gitignore` = `*`), so it was overwritten with this
task's report rather than appended to.
