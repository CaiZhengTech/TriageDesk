# TriageDesk — Documentation Map

**Start here.** Everything written about this project lives under `docs/`, grouped by
the week that produced it. This page tells you where to look for what.

---

## 🧭 Where things are

| I want… | Go to |
|---|---|
| **The interview pitch** (one-liners, the 30-second story, the numbers) | [`00-spec/PITCH.md`](00-spec/PITCH.md) |
| **The design record** — what this system is and why, the non-negotiable rules | [`00-spec/DESIGN-SPEC.md`](00-spec/DESIGN-SPEC.md) |
| **The database schema** — table/column names, gotchas, useful queries | [`00-spec/DATA-SCHEMA.md`](00-spec/DATA-SCHEMA.md) ⭐ *read before writing any query* |
| **To understand what was built, in plain language** (analogies, no jargon) | Any week's `STORY.md` |
| **To resume work / hand off to a new session** | The current week's `HANDOFF.md` |
| **The task-by-task plan being executed** | The current week's `PLAN.md` |
| **Engineering evidence** — what each task built, TDD proof, findings | Any week's `reports/` |
| **What was decided and why** (narrative, per issue) | [GitHub issue closeouts](https://github.com/CaiZhengTech/Agentic_Project/issues?q=is%3Aissue+is%3Aclosed) |

## 📁 The layout

```
docs/
  README.md              ← you are here
  00-spec/               cross-week: the design record, the schema, the pitch
    DESIGN-SPEC.md         what TriageDesk is, the locked stack, the rules
    DATA-SCHEMA.md         ★ every table + column, the gotchas, example queries
    PITCH.md               ★ read before any interview — one-liners + numbers
  week-1-pipeline/       the agent itself (issues #1–#7, #28)
    PLAN.md                the 9-task plan that was executed
    STORY.md               ★ plain-language walkthrough, issue by issue
    QA-HARDENING.md        the post-merge audit ("show your receipt" fix)
    HANDOFF.md             end-of-week state
    HANDOFF-mid-week.md    (superseded, kept for the record)
    reports/               per-task engineering evidence
  week-2-evals/          the evaluation layer (issues #8–#12)
    PLAN.md                the 7-task plan + binding council amendments
    STORY.md               ★ plain-language walkthrough, task by task
    HANDOFF.md             the controller operating manual (how to run this project)
    reports/               per-task engineering evidence
  week-3-console/        (not started — console + deploy, issues #13–#16)
  week-4-story/          (not started — demo video + case study, issues #17–#18)
```

**Naming convention:** the folder says *when*, the filename says *what*. No dates in
filenames — git already has those. `PLAN` / `STORY` / `HANDOFF` / `QA-*` are always the
same names in every week, so you always know what you're opening.

- `PLAN.md` — the canonical, code-level task list for that week (what gets built)
- `STORY.md` — the explainer: analogy → the recurring "Dana's ticket" walkthrough →
  "under the hood" (semi-technical). Written to be retold to a non-technical listener.
- `HANDOFF.md` — the state doc: where things stand, what's next, how to resume
- `reports/task-N-<topic>.md` — what a task actually built, with test evidence and findings

## 📊 Status

**Week 2 (evals) — 6 of 7 tasks done.** Golden set, deterministic harness, LLM judge, and
calibration tooling are merged (issues #8, #9, #10 closed).

**⏸ Blocked on one human action:** Cai labels 41 blind rows in `judge_labels.csv` (see
[`results/LABELING-INSTRUCTIONS.md`](../results/LABELING-INSTRUCTIONS.md)) → then Cohen's
kappa + the disagreement analysis close issue #11. Task 7 (the CI eval gate, issue #12 —
Week 2's kill criterion) can proceed in parallel.

**To resume work:** read [`week-2-evals/HANDOFF.md`](week-2-evals/HANDOFF.md) — the
controller operating manual (environment, tooling, the per-task choreography, budget rules,
binding decisions).

Live numbers so far: **100% adversarial catch rate**, escalation recall **1.0**,
~**2.9¢** per pipeline run, **41** judged replies awaiting human calibration.
API spend: **~$3.05 of a hard $20 budget.**

## 🔍 Other places records live

- **GitHub issues** — every closed issue carries a narrative closeout comment (what was
  built, how it went, decisions, what's next) plus a plain-language explainer comment.
  This is the best chronological read of the project.
- **`results/`** — outputs meant to be read as deliverables (labeling instructions;
  calibration report and eval baselines land here).
- **`.superpowers/sdd/progress.md`** — the raw working ledger (git-ignored, local only):
  every commit, fix loop, incident, and running budget line. The reports in each week's
  `reports/` folder are the readable version of the same evidence.
