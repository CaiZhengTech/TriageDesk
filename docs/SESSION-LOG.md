# Session Log

Chronological record of what happened in each working session — decisions made, what
changed, what was left open. **Append a new entry at the top after every session.**

*(This is the "what happened when" record. For "where are we right now / how do I resume",
read the current week's `HANDOFF.md`. For "what did task N build", read that week's
`reports/`. One fact, one home.)*

---

## Session — 2026-07-17 (night) · Wk3 Tasks 5 + 7 — deploy-prep + demo protection; #16 CLOSED; all Week-3 CODE done

**Where it started:** continue past Task 4 (#14 closed earlier today) into Tasks 5–7.
**Where it ended:** **all Week-3 code is merged and gate-verified.** Only Task 6 remains —
the live deploy, a JOINT session needing Cai's Railway/Vercel accounts. Resume:
`week-3-console/HANDOFF.md` (the full deploy checklist is at the top).

### What happened
1. **Task 5 — deploy-prep** (PR #54, `d1275f7`): fail-closed CORS (empty origins ⇒ no
   middleware at all, never a wildcard; only the methods/headers the console uses) + a
   stdlib JSON log formatter behind `LOG_JSON`. Review APPROVE with 1 Important — the CORS
   tests preflighted a GET, not the browser-real `POST /api/review/{id}` with
   `X-Admin-Token` — fixed in-PR (haiku fixer), re-review APPROVE with the reviewer
   empirically proving both regression directions. Its auto-triggered gate run was
   **cancelled as superseded** (~$0, batching rule).
2. **CI raced itself once:** PR #54's first CI run failed on a duplicate-key error in an
   integration test — root-caused to a reviewer subagent running the suite locally while
   CI's integration tests were mid-flight on the SAME shared Neon test branch (teardown-only
   cleanup + pinned-ID inserts don't advance the sequence). Re-run green. New ledger rule:
   never run local integration tests while a CI run is in_progress.
3. **Task 7 — demo protection** (PR #55, `f37ceec`): `demo.py` (pool query, injectable-clock
   rate limiter, tz-explicit UTC daily-cap pre-check), the 404→429→402→202 guard chain with
   "before spending" semantics unit-tested (run_ticket asserted NOT called on every blocked
   branch), the demo console page with the exact council-mandated pause banner, and
   `scripts/smoke.py` for Task 6. Review APPROVE with 2 Importants sharing one root cause —
   **a check-then-act race on the daily cap** (N concurrent requests could all pass the
   pre-check before any committed a cost) — fixed in-PR with a serialized-dispatch lock
   (demo concurrency = 1, a feature at $1/day). The re-reviewer independently reproduced
   the race: without the lock [202,202] 5/5 runs; with it [202,402] 5/5. **#16 CLOSED.**
4. **The wave's ONE billed gate run went GREEN** (29621157110, **$0.911**): Tasks 5+7's
   `triagedesk/**` changes moved no guarded numbers. Batching worked as designed — two
   API-path merges, one bill.
5. **Interruption handled:** the Task-7 re-reviewer died mid-verification (session limit);
   state was verified (tree clean, branch intact) and the same agent resumed from its
   transcript rather than re-dispatched — no duplicated work.
6. Per-task deliverables posted immediately both times (#15 comment, #16 closeout comment +
   close, two STORY chapters, ledger rows + minors).

### Spend
**$0.911 this session** (the one wave gate run). Total ≈ **$9.5 of $20**.

### Open
- **Task 6 — the live deploy** (Railway + Neon + Vercel + smoke): checklist with exact
  env-vars and the `--proxy-headers` gotcha at the top of `week-3-console/HANDOFF.md`.
  Needs Cai. Closes #15 and Week 3.
- Standing: seed prod demo pool at deploy; dedicated Neon eval branch; second rater (#19).

---

## Session — 2026-07-17 (evening) · Wk3 Task 4 — the review-queue PAGE; #14 CLOSED; PITCH restructured for interviews

**Where it started:** resume at Wk3 Task 4 (the review-queue page); Cai flagged an upcoming
interview and asked for strong docs + a clean, legible issue log + a well-formatted PITCH.
**Where it ended:** **#14 CLOSED — the console is feature-complete** (run list · run detail ·
review queue). Next: Task 5 (deploy-prep code), batched with Task 7. Resume:
`week-3-console/HANDOFF.md`.

### What happened
1. **Session-start verify:** gate run **29555275667 confirmed GREEN** (PR #52's API wave,
   11m18s); recorded its actual cost **$0.887** ($0.726 base + $0.161 judge) in the ledger.
2. **Task 4 — the review-queue page** (PR #53, `4f51143`): a thin Next.js page — server
   component fetches `GET /api/review-queue`; a client component owns the operator-token
   field (`sessionStorage` → `X-Admin-Token`); one row component per case with a required
   note + approve/reject. The fetch helper returns a *labeled* result so the UI reacts
   precisely to Task 3's four statuses (201/401/409/503). Implementer verified all five
   paths through a **real browser** (agent-browser) against ~223 dev-DB escalated runs.
   Review APPROVE-WITH-MINORS; the one Minor (a dead `row-escalated` CSS class on a
   `<section>`) was fixed in-PR with a `.review-card` border. Console-only ⇒ **$0 gate**.
   **#14 closed** (both halves done).
3. **Honest, correctly-scoped gap recorded:** the console→API cross-origin POST needs a
   CORS preflight the real app doesn't answer yet — that's **Task 5's** job (CORSMiddleware),
   flagged in the report/PR, not worked around.
4. **PITCH restructured for interview use** (`cf3294f`, direct to main): a "how to use this
   file" jump table, the one-liners grouped into scannable themed sections (every quote
   preserved verbatim), two new Week-3 one-liners (the ops console + the review queue), and
   refreshed numbers (202 tests, ~$8.6 spend). Standing STORY chapter + #14 closeout posted.
5. **Process note (own it):** the first Task-4 subagent shared the working tree; a docs
   `git commit` for the PITCH landed on the feature branch by mistake. Reconciled cleanly —
   rebased the stray commit off the branch, cherry-picked PITCH onto main, force-pushed so
   PR #53 showed only console files. Lesson for Tasks 5–7: isolate implementers in a
   worktree, or do zero git writes while a background agent holds the shared tree.

### Spend
**$0 this session** (Task 4 console-only; the $0.887 gate was last session's run, now just
finalized in the ledger). Total ≈ **$8.6 of $20**.

### Open
- **Task 5 (deploy-prep: CORS + JSON logs)** is the next action — dispatch recipe at the top
  of `week-3-console/HANDOFF.md`. **Batch Task 5 + Task 7 API merges** (one gate run). Then
  Task 6 (live deploy — needs Cai's Railway/Vercel accounts).

---

## Session — 2026-07-17 (later) · Week 3 begins — plan + runs API + console pages + review-queue API; stopped before Task 4 by request

**Where it started:** Week 3 unblocked (#45 closed earlier the same day).
**Where it ended:** **#13 CLOSED (both halves); #14 half done (API merged, page not
started — Cai asked to stop before Task 4).** Resume: `week-3-console/HANDOFF.md`.

### What happened
1. **Week 3 plan written** (`docs/week-3-console/PLAN.md`, 7 tasks for issues #13–#16)
   with a new binding **gate-cost rule**: API-path merges are batched and superseded
   queued eval-gate runs cancelled — one billed run per merge wave.
2. **Task 1 — runs read API** (PR #50, `360b1d0`): `GET /api/runs` + `GET /api/runs/{id}`
   in a new `console_queries.py`; the naive/aware timestamp gotcha neutralized in one
   tested helper; failed runs structurally unfilterable. Review clean. Its gate run was
   cancelled as superseded ($0).
3. **Task 2 — the console** (PR #51, `9f41aaa`): Next.js 15 scaffold in `console/`,
   run list + run detail (flat trace table, rationale captioned "post-hoc — not
   evidence"), zero extra dependencies. Review found 1 Important (no error boundary →
   framework crash page on API-down) → haiku fixer added `error.tsx` → re-approved.
   **#13 closed.** Honest footnote: dev DB has ZERO completed runs (everything
   escalates by design) — completed-row styling is code-verified only.
4. **Task 3 — review-queue API** (PR #52, `f760367`): `review_decisions` table
   (Alembic, unique verdict per run), `GET /api/review-queue` (escalated + undecided,
   oldest first), `POST /api/review/{run_id}` behind the operator token — **fails
   closed: 503 when no token is configured**, checked before any comparison. Review
   clean. Its merge triggered the session's one billed gate run (29555275667,
   ~$0.90, in flight at session end — VERIFY GREEN at next session start).
5. Per-task deliverables (issue comments, STORY chapters, ledger) posted immediately
   after each task — Cai's re-confirmed standing rule.

### Spend
~**$0.90 this session** (the one API-wave gate run; pending exact figure). Total ≈
**$8.6 of $20**.

### Open
- **Task 4 (queue page) is the next action** — dispatch recipe at the top of
  `week-3-console/HANDOFF.md`. Then Tasks 5→7 (batch their API merges!), then the
  Task 6 live deploy (needs Cai's Railway/Vercel accounts).

---

## Session — 2026-07-17 · Labeling round 2 lands — the recalibration measures the HUMAN, and Week 2.5 CLOSES

**Where it started:** everything done except Cai's fresh labeling of `judge_labels_v2.csv`.
**Where it ended:** **#45 CLOSED — Week 2.5 complete. Week 3 is GO.**

### What happened
1. Cai labeled all 41 v2 rows (34 pass / 5 fail / 2 needs_review) → `label-import` +
   `calibrate` scoped to batch `69b3fa3d` ($0). **Official v2 kappa: 0.133** (raw 0.488,
   weighted 0.164, CI [−0.05, 0.35]) — LOWER than v1's 0.279, despite the judge improving.
2. **Root-caused instead of shrugged at (again):** the human moved, not the judge.
   Cai's round-1 vs round-2 labels on the SAME replies: self-agreement kappa **0.212** —
   lower than the judge's agreement with either round (14/41 flips, 9 fail→pass; round 2
   markedly more lenient, and the 34/41-pass skew depresses kappa via prevalence).
   The judge fix's improvement is INVARIANT: v2 beats v1 against both rounds
   (0.279→0.418 and 0.038→0.133). Full 2×2 table: `results/judge-calibration.md`.
3. **One real residual judge blind spot found:** negative entitlement claims ("custom
   integrations are not in your Pro plan" — TRUE per `PLAN_ENTITLEMENTS`) failed as
   "invented policy": the judge doesn't do closed-world inference over the entitlement
   list. Cai's round-2 passes are correct on those rows; a candidate judge-v3 fix
   (declare the list exhaustive) is recorded — deferred, judge still advises only.
4. **Consequence, decided calmly:** single-rater calibration has hit its reliability
   ceiling — the next step is a second rater (chore #19) / adjudicated gold labels, not
   judge tuning. `tolerance: {}` (judge never vetoes) unchanged. #45 closed with the
   full analysis; HANDOFF/PITCH/CLAUDE.md updated; **Week 3 unblocked.**

### Spend
**$0 this session** (import + calibrate are DB + math). Total unchanged ≈ **$7.7 of $20**.

### Open
- Week 3 (issues #13–#16). Standing cheap items: Neon eval branch; second rater (#19).

---

## Session — 2026-07-16/17 · Week 2.5 hardening EXECUTED — all three tasks done; awaiting Cai's blind relabel

**Where it started:** council checkpoint done (2026-07-14), hardening plan on `main`
(#44, issue #45), Task 1 implemented but unreviewed on its branch.
**Where it ended:** **all three hardening tasks complete.** Tasks 1–2 merged with clean
subagent reviews (PRs #46, #47); Task 3 (controller-only, live) executed end-to-end:
thresholds derived from held-out data (PR #48), judge-v2 backfill + preview kappa,
baseline re-derived from the live run (PR #49) and validated green. **One human action
open: Cai's fresh blind labeling of `judge_labels_v2.csv` (41 rows) → official v2 kappa.**

### What happened
1. **Task 1 (metric integrity) reviewed + merged** (`4932aea`, PR #46) — review clean.
   Headline `adversarial_catch_rate` is now reason-aware with a documented equivalence
   policy; `adversarial_catch_rate_strict` = 3/5 = 0.60 is the honest diagnostic; cap
   became a pre-check; judge cost its own line item.
2. **Task 2 (calibration scoping, weighted kappa+CI, judge tool-evidence, pinned temp,
   golden view) implemented + reviewed + merged** (`3f2cebd`, PR #47) — review clean.
   `JUDGE_PROMPT_VERSION = 2`; the `eval_results_golden` view is documented in
   DATA-SCHEMA.md as the only sanctioned non-Python read path.
3. **Thresholds re-derived from the held-out pool** (PR #48, `f112e29`): the signals
   carry NO reply-quality information (pass/fail means directionally inverted!), so
   `MARGIN_THRESHOLD` moved to its semantic zero (0.0 = embedding agrees with the LLM's
   queue choice) and 0.45 similarity was re-grounded (~36th percentile held-out).
   Leakage audit: the one human-fail reply clearing both thresholds is a denial the
   adverse-action rule blocks structurally. Full record:
   `week-2-evals/reports/threshold-derivation.md`.
4. **Judge-v2 re-backfill, append-only** ($0.35): the 41 labeled replies were COPIED to
   a fresh batch (`69b3fa3d`) and re-judged with the tool-evidence judge — v1 rows
   untouched (evidence preserved). **Preview vs the v1-era labels: raw agreement
   0.512 → 0.634, kappa 0.279 → 0.418, weighted 0.551 (CI 0.21–0.61).** Official number
   waits for the fresh blind pass (`judge_labels_v2.csv`).
5. **Baseline re-derived from live run `d429d547`** (PR #49, `31b7f25`): floors now
   include `adversarial_catch_rate_strict ≥ 0.60` and `adversarial_escalate_rate ≥ 1.00`;
   validated by the push-triggered gate run.
6. **Surprise + lesson:** merging PRs #46/#47/#48 each auto-triggered the eval gate
   (eval paths — by design, but unbudgeted): 3 unplanned runs ≈ $2.7. The paths trigger
   re-verifying eval-layer changes is the system working; the lesson (ledger) is to
   BATCH eval-path merges when several land in one session.

### Spend
**≈ $3.94 this session** (4 gate runs ≈ $0.89–0.91 each incl. judge; backfill $0.35).
Total **≈ $7.7 of $20**.

### Open
- **Cai: blind-label `judge_labels_v2.csv`** (41 rows, instructions in
  `results/LABELING-INSTRUCTIONS.md`) → `label-import --eval-run 69b3fa3d…` →
  `calibrate --eval-run 69b3fa3d…` → official v2 kappa → close #45.
- Then Week 3 (issues #13–#16) per the standing plan.

---

## Session — 2026-07-14 · Calibration lands (kappa 0.279, the tool-blind judge) + the CI eval gate goes GREEN — WEEK 2 COMPLETE

**Where it started:** blocked on Cai's blind labeling pass (41 rows).
**Where it ended:** #11 AND #12 closed. **Week 2 complete; the kill criterion is MET**
(eval gate green on `main`, first live run, $0.72). STOPPED for Cai's end-of-week
llm-council checkpoint — agenda in `week-2-evals/HANDOFF.md`. **No Week 3 work before it.**

### What happened
1. Cai labeled all 41 blind rows (26 pass / 13 fail / 2 needs_review) → `label-import` +
   `calibrate` ($0 — pure DB + math). Artifact: `results/judge-calibration.md`.
2. **Kappa 0.279, raw agreement 0.512.** Low — and then root-caused rather than shrugged at.
3. **The finding of the week: the judge is tool-blind.** Its context is ticket + KB + reply;
   the agent also grounds facts in `lookup_account_status`/`check_entitlement`. Every
   plan/status claim the judge called "invented" was replayed against the simulated CRM:
   **7/7 were true tool-derived facts.** Evidence table in
   `week-2-evals/reports/task-6-calibration-kappa.md`.
4. Direction of error is safe: judge stricter than human in 18/20 disagreements (fails
   closed). The 2 lenient misses (results 34, 70) are recorded as the real risk.
5. **Deliberately NOT fixed mid-week** — showing the judge tool outputs would invalidate the
   calibration just paid for. Goes to the council checkpoint as top agenda item. Consequence
   for Task 7 (already in the plan): judge metrics get a tolerance band; deterministic
   metrics carry the gate.

6. **Task 7 shipped via the full SDD choreography** (implementer → reviewer → haiku fixer →
   re-review APPROVE → merge, PR #42): `.github/workflows/eval.yml` with the council-amended
   trigger (`workflow_dispatch` + eval-relevant paths only — NOT every merge),
   `results/eval-baseline.json` derived from recorded numbers and labeled a *regression
   floor, not a quality target*, `tolerance: {}` for the judge (kappa 0.279 ⇒ advises, never
   vetoes). Reviewer caught a real hole pre-merge: `alembic/**` missing from the paths
   filter — a schema migration could have dodged the gate. Fixed (+ `requirements.txt`).
7. **The live gate run went GREEN** (run 29359540499, $0.72 under the $1 cap): catch 1.00,
   recall 1.00, precision 0.88, 2.9¢/run. Secrets `EVAL_DATABASE_URL`/`ANTHROPIC_API_KEY`/
   `VOYAGE_API_KEY` set from credentials.env. Deviations recorded in the ledger + HANDOFF:
   eval DB = dev branch (no Neon API key for a dedicated branch); tightened-baseline live
   failure proof replaced by the unit-layer breach tests (~$1 saved).

### Spend
**$0.72 this session** (the counted CI gate run). Total **~$3.77 of $20**.

### Open
- Cai's llm-council checkpoint (agenda in `week-2-evals/HANDOFF.md`) — then Week 3.

---

## Session — 2026-07-12 → 07-14 · Week 2 evals (Tasks 1–6) + a full docs overhaul

**Where it started:** Week 1 was merged and QA'd; Week 2 (the evaluation layer — the
project's actual differentiator) had a plan but no code.
**Where it ended:** Week 2 is **6 of 7 tasks done**, blocked on one human action.

### ⏸ The one thing waiting on Cai
**Label `judge_labels.csv` — 41 blind rows.** (Read `results/LABELING-INSTRUCTIONS.md`
first.) The judge's verdicts are deliberately withheld from the file; that blindness is what
makes the calibration honest. When done → `label-import` → `calibrate` → Cohen's kappa +
the disagreement analysis → issue #11 closes.

### What got built (12 PRs merged, #29–#40)

| Task | Issue | Outcome |
|---|---|---|
| **QA hardening** (carried over from Wk1) | #28 | The "show your receipt" gate rule: auto-resolve now *structurally* requires `check_entitlement` evidence. Plus fail-closed cost typing, gitleaks in CI. |
| **1 · SDK spike** | — | 4 live calls (2¢) → committed fixture. Caught the trap: an unconstrained verdict field lets the model answer `"poor"`. |
| **2 · Prompt caching** | — | Stable prompt prefixes cached → **~2.9¢/run** (was 3–7¢). Had to land before any suite run. |
| **3 · Golden set** | #8 | 25 cases (20 stratified + 5 adversarial, incl. the soft-denial trap). |
| **4 · Eval harness** | #9 | Deterministic metrics + calibration table + `eval_results` persistence. **The project's first real numbers.** |
| **5 · LLM judge** | #10 | Pinned, temp-0, enum verdict, abstain option. Grades reply-vs-KB grounding only. |
| **6 · Calibration tooling** | #11 | Blind CSV export, hand-rolled Cohen's kappa, disagreement report, + a 25-ticket held-out calibration pool. ⏸ *awaiting labels* |
| **7 · CI eval gate** | #12 | ⬜ **Not started** — the Week 2 kill criterion. Does not depend on the labels. |

### The numbers that now exist (first live evidence)
- **Adversarial catch rate 5/5 = 100%** — every trap caught by its intended defense layer.
- **Escalation recall 1.0** (precision 0.88) — nothing needing a human slipped through.
- **~2.9¢ per run**, p50 31–34s. Judge on 19 golden replies: 9 pass / 5 fail / 5 needs_review.
- Routing accuracy 29% — *against noisy dataset labels* (the 10 queues overlap heavily in
  embedding space). Reported honestly as a finding, not hidden.
- **API spend: ~$3.05 of the hard $20 budget.**

### Decisions made this session (binding — don't relitigate)
1. **Council review of the Week 2 plan** (Cai requested it before implementation). Verdict:
   the plan was about to measure a system that couldn't produce variance. A **$0 diagnostic**
   settled it: the margin formula is *correct*, but the 0.02 threshold is structurally
   near-unreachable (only 2/20 ground-truth tickets clear it). Amendments now binding in
   `week-2-evals/PLAN.md`.
2. **Hold-out rule.** The golden set MEASURES, never TRAINS. Thresholds get re-derived from
   held-out data — never tuned on the 25. The judge's calibration pool is likewise *different*
   tickets (Cai chose this over the cheaper same-tickets option).
3. **Expected outcomes encode IDEAL behavior**, not what today's config does. Three golden
   cases are labeled "should auto-resolve" even though current thresholds fail them — an
   honest red beats green-by-construction.
4. **CI eval gate trigger = manual + eval-paths filter, NOT every merge** — at $1+/run across
   Weeks 3–4's merges, an every-merge trigger would eat the whole remaining budget.
5. **Docs reorganized** (Cai: "I don't know where to look"): grouped **by week**, same four
   names in every week (`PLAN` / `STORY` / `HANDOFF` / `reports/`), **no dates in filenames**,
   task reports **committed to the repo**, and a **one-fact-one-home** anti-duplication rule.
   Map: `docs/README.md`.
6. **`docs/00-spec/DATA-SCHEMA.md` created** — every table/column, the enum vocabularies, the
   gotchas. Written because guessed column names crashed two queries in one session.

### Things that went wrong (and what each taught us)
Every one of these was invisible to green mocked tests and only surfaced against reality —
this is the case study's spine (full list in `.superpowers/sdd/progress.md`):
- **The first live eval suite crashed** on a naive-vs-aware timestamp mismatch.
- **The judge was dead code.** It was gated on runs finishing `completed` — which this system,
  by design, essentially never does. It would never have fired once, and calibration would
  have opened to an empty file. Fixed semantically: reply *quality* is independent of the
  gate's *send* decision.
- **The soft-denial trap didn't trap.** Its auto-assigned ticket ID mapped (via `id % 12`) to
  an *enterprise* customer who was legitimately entitled to what the ticket asked for. IDs are
  now pinned; the trap is anchored to Dana's basic plan.
- **A reseed destroyed a paid-for eval run's history** (25 rows, $0.73 of evidence) via an
  FK-convenience `delete()`. Destructive deletes are now gated behind `--reset-history`.
- **Our own answer key was wrong.** Dana's ticket was labeled "should auto-resolve," but it
  contains a denial — so it *can't* be. Caught by the first live run.
- **The plan's kappa formula would have claimed "perfect agreement"** on a degenerate sample
  where kappa is mathematically undefined (0/0). The implementer overrode the plan; the
  reviewer independently re-derived the math and confirmed. *The eval layer caught an error in
  its own specification.*
- **Five Week-1 task reports were destroyed** by a filename collision (Week 2's `task-N-report.md`
  overwrote Week 1's). Reconstructed from the ledger, issue closeouts, and git — clearly
  labeled as reconstructions, with unrecoverable facts marked `(not recovered)` rather than
  guessed.

### Housekeeping done
- Issue **#11 reopened** — it had auto-closed when the *tooling* PR merged, but its acceptance
  criteria (human labels + kappa) aren't met yet. A closed issue would have lied.
- `PITCH.md` refreshed with the live numbers; `STORY.md` gained chapters for tasks 4–6;
  `HANDOFF.md` rewritten as a blocker-first operating manual with the full tooling/plugin
  environment.

### Next session picks up here
1. **Cai's labels land** → `label-import` + `calibrate` → kappa + disagreement appendix →
   closeout #11.
2. **Task 7 — the CI eval gate (#12).** Can start immediately; independent of the labels.
   ⚠️ The baseline is committed only *after* threshold re-derivation — the first run's numbers
   are diagnostic, not a target.
3. **Week 2 kill criterion:** if the gate isn't green by week's end, the Week-3 console is cut
   to one read-only page. Not negotiable mid-project.
4. **Then STOP** for Cai's end-of-Week-2 council checkpoint before any Week 3 work.

---

## Session — 2026-07-10 → 07-12 · Week 1 (the pipeline) + QA

Built the 5-stage agent end to end (pre-check → classify → retrieve → act loop → confidence
gate), the tracing layer, cost caps, and the CLI. Week 1's kill criterion was met: two live
runs through all five stages, both correctly escalating Dana's entitlement denial to a human.
A post-merge council review then found the adverse-action guarantee was enforced by *model
cooperation* rather than *gate structure* — fixed in #28.

**Full story:** `docs/week-1-pipeline/STORY.md` · **evidence:** `docs/week-1-pipeline/reports/`
