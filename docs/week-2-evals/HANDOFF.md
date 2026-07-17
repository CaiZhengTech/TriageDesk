# RESUME HERE — Controller Operating Manual

**Any new session starts with this file.** Written so a fresh controller (any model) can
finish this project end-to-end without guessing. Last updated: 2026-07-17.

---

## ✅ WEEK 2.5 COMPLETE (2026-07-17) — Week 3 is GO

**Issue #45 is fully done** (all three hardening tasks + Cai's fresh labeling round 2 +
the official judge-v2 calibration). **Next session starts Week 3: issues #13–#16**
(console run list/detail → review queue → deploy → demo protection), per the standing
plan at the bottom of this file. Read `results/judge-calibration.md`'s reliability
analysis before quoting ANY kappa — the recalibration's headline finding:

- **Judge v2 improved invariantly** (beats v1 against both labeling rounds:
  0.279 → 0.418 on round-1 labels, 0.038 → 0.133 on round-2 labels).
- **The human label standard is the measured bottleneck**: Cai's self-agreement across
  rounds on the same 41 replies is kappa **0.212** — lower than the judge's agreement
  with either round. Official v2 kappa (0.133 vs round-2 labels) is capped by
  single-rater noise, not judge quality. **Next calibration step = a second rater
  (chore #19) and/or adjudicated gold labels — NOT more judge tuning.**
- **One real residual judge blind spot**: negative entitlement claims ("X is not in
  your plan" — true per `PLAN_ENTITLEMENTS`) get failed as "invented policy"; a future
  judge v3 should declare the entitlement list exhaustive in the account-facts block.
  Judge still advises, never vetoes (`tolerance: {}` unchanged).

**Week 2.5 outcome (2026-07-16/17):** metrics are reason-aware (headline catch 5/5
design-intent, strict diagnostic 3/5 = 0.60 — both baseline-guarded); calibration is
run-scoped with weighted kappa + bootstrap CI; the judge sees tool evidence
(`JUDGE_PROMPT_VERSION = 2`, preview: agreement 0.512 → 0.634, kappa 0.279 → 0.418);
precheck/classify pinned to temp 0; `eval_results_golden` view for Week 3's console;
thresholds derived from held-out data (`reports/threshold-derivation.md` — margin 0.02 → 0.0,
its semantic zero); baseline re-derived from live run `d429d547` and validated green.
Spend ≈ **$7.7 of $20**.

**Still-open council item (cheap, anytime):** dedicated Neon eval branch —
`EVAL_DATABASE_URL` points at DEV; create a branch in the Neon dashboard, update the secret.

**⚠️ Cost lesson (binding-ish):** merging anything touching `triagedesk/**`, `kb/**`,
`alembic/**`, `requirements.txt`, the workflow file, or `results/eval-baseline.json`
push-triggers the eval gate (~$0.90/run incl. judge — by design, it re-verifies eval-layer
changes). **Batch eval-path merges**; docs/tests merges never trigger it.

---

## 🛠 Environment, tools, and plugins (verify before doing anything)

| Thing | Fact |
|---|---|
| **Repo** | `C:\Users\Wonton Soup\Downloads\Tech Projects\Agentic_Project` (Windows) |
| **Python** | 3.13 in `.venv` — always `.venv/Scripts/python -m pytest -q` and `-m ruff check .` |
| **Secrets** | `export TRIAGEDESK_ENV_FILE="C:\Users\Wonton Soup\.secrets\credentials.env"` in EVERY shell touching settings/DB/API. **Never print secret values.** |
| **DB** | Neon Postgres + pgvector (dev branch + a test branch for integration tests). **Never guess table/column names — read [`docs/00-spec/DATA-SCHEMA.md`](../00-spec/DATA-SCHEMA.md) first.** It exists because guessed column names crashed two queries in one session. |
| **Embeddings** | Voyage `voyage-3.5-lite`, 1024-dim. **Free tier: 3 req/min, 10K tokens/min** — always BATCH into one `embed([list])` call. Voyage is NOT the Anthropic budget. |
| **Model** | `claude-sonnet-4-6` everywhere. Judge = same model at `temperature=0`. |
| **CI** | GitHub Actions, one job named `test` (pytest + ruff + gitleaks). Branch protection needs it green + branch up to date. **Always `gh pr checks N --watch` before merging.** |
| **GitHub CLI** | `gh` is authenticated; issues and PRs are managed through it. |

**Superpowers plugin** — this project runs on **`superpowers:subagent-driven-development`**.
The two scripts you'll use constantly:

```bash
S="/c/Users/Wonton Soup/.claude/plugins/cache/claude-plugins-official/superpowers/6.1.1/skills/subagent-driven-development/scripts"
"$S/task-brief"     docs/week-2-evals/PLAN.md 7     # extract a task's brief → prints the path
"$S/review-package" <BASE_SHA> <HEAD_SHA>           # bundle a diff for a reviewer → prints the path
```
Reviewer template: `…/subagent-driven-development/task-reviewer-prompt.md`.
Final whole-branch review template: `…/requesting-code-review/code-reviewer.md`.

**Also available:** the `llm-council` skill (Cai invokes it at week boundaries and before big
merges — expect it, feed it real numbers); MCP servers for GitHub, Firecrawl (web search), and
Context7 (library docs). Memory files carry Cai's standing preferences across sessions and load
automatically.

---

## 🔁 The per-task choreography (repeat for every task)

1. `git checkout main && git pull`; record `BASE=$(git rev-parse --short HEAD)`.
2. Extract the brief with `task-brief`. **Never archive briefs** — regenerate each time so
   they always reflect the current (possibly amended) plan.
3. Dispatch **ONE** implementer subagent (sonnet). **Never two implementers at once** — they
   share one working tree and collide on branch switches (this has bitten twice). The dispatch
   carries: one line on where the task fits; the brief path ("read this first — your complete
   requirements"); any **binding council amendments** touching the task; the environment facts
   above; the branch name (`feat/NN-slug`, off BASE); the report path
   (`docs/week-N-<topic>/reports/task-N-<topic>.md` — **reports are committed to the repo**);
   and "push + open a PR, do NOT merge."
4. On DONE → `review-package BASE HEAD` → dispatch **ONE reviewer** (sonnet) with the brief
   path, report path, diff path, and the task's binding constraints **copied verbatim**.
5. Critical/Important findings → **ONE** fix subagent (haiku for 1–2-file mechanical fixes,
   else sonnet) → re-review by messaging the same reviewer. Minor findings → the ledger.
6. Merge ritual: `gh pr checks N --watch` (must be green — **never merge without**) →
   `gh pr merge N --squash --delete-branch` → `git checkout main && git pull`.
7. Bookkeeping in the same breath: ledger entry, TaskUpdate, and the three standing
   deliverables below.

**If an agent dies mid-task:** check `git status`, its branch, and its report file BEFORE
re-dispatching. Twice now an agent has died *after* completing its work but before reporting.
Verify, then resume — never blindly restart.

---

## 📣 The three standing deliverables (Cai's explicit, non-negotiable ask)

After **every** completed task:
1. **A plain-language explanation in chat** — what was done and why, no jargon walls.
2. **A short analogy-driven comment on the GitHub issue** (~1 min read): why it matters, how it
   builds on the previous issue, what's next. Written for a non-technical reader.
3. **A chapter in that week's `STORY.md`** — three layers: **analogy** → **Dana's journey** →
   **"Under the hood"** (semi-technical, real component names, no code). Roll interview
   one-liners into `docs/00-spec/PITCH.md`.

Dana Fuentes (customer-3; VPN ticket 12027, dedicated-IP variant 12039) is the **recurring
worked example** everywhere. Continuity is the point.

---

## 💰 Budget — HARD CAP $20, no top-ups (~$7.7 spent)

- Unit tests are **$0** — fixtures and fakes only, always.
- Live steps are deliberate, counted events. A full eval suite run ≈ **$0.75–1.30**;
  **≤4 during Week 2** (2 used). The judge-backfill command (15¢) exists so you never re-run
  the pipeline just to re-judge.
- Update the budget table in `.superpowers/sdd/progress.md` after every API-touching step.
- **Task 7's CI gate trigger = `workflow_dispatch` + a paths filter (eval-relevant code only),
  NOT every merge.** At $1+/run across ~10–15 merges in Weeks 3–4, an every-merge trigger would
  eat the entire remaining budget. Council amendment; the $1 in-workflow cap stays.

---

## 🚫 Binding decisions — do not relitigate

- **Hold-out rule:** the golden set MEASURES, never TRAINS. Thresholds are re-derived from
  held-out tickets + the calibration table — *never* tuned on the 25. The judge's calibration
  pool is likewise non-golden tickets.
- **Expected outcomes encode IDEAL behavior**, not current-config behavior. Three golden cases
  are labeled ideal-auto-resolve even though today's thresholds fail them — an honest red beats
  green-by-construction.
- **SDK-reality rule:** never code against an API surface you haven't observed live. Commit the
  observed response as a fixture; build mocks only from it. (It has paid for itself ~6 times —
  see the incident list in the ledger.)
- **Gate invariants:** adverse-action check first; positive `check_entitlement` evidence
  required before any auto-resolve; signals never include LLM self-reported confidence.
- **Reviewer rubric:** violating a written non-negotiable design rule = **Critical by definition**.
- **Docs:** grouped by week; no dates in filenames; reports committed. One fact, one home —
  never restate, link. See `docs/README.md`.

---

## ✅ Week 2 status

| Task | Issue | State |
|---|---|---|
| 1 SDK spike → committed fixture | — | ✅ PR #30 |
| 2 Prompt caching | — | ✅ PR #31 |
| 3 Golden set (25 cases) | #8 | ✅ closed, PR #32 |
| 4 Eval harness + calibration table | #9 | ✅ closed, PR #33 (+#34, #35) |
| 5 LLM judge | #10 | ✅ closed, PR #36 (+#37) |
| 6 Kappa tooling + calibration pool | #11 | ✅ closed — PRs #38/#39 + calibration run (kappa 0.279) |
| 7 CI eval gate — **KILL CRITERION** | #12 | ✅ closed — PR #42, gate GREEN on main ($0.72) |
| 2.5-1 Metric integrity (reason-aware catch, cap pre-check, judge cost) | #45 | ✅ merged — PR #46 (`4932aea`), review clean |
| 2.5-2 Calibration scoping · weighted kappa+CI · judge tool-evidence · pinned temp · golden view | #45 | ✅ merged — PR #47 (`3f2cebd`), review clean |
| 2.5-3 Thresholds (held-out) + judge-v2 backfill + baseline re-derivation (controller, live) | #45 | ✅ done — PRs #48/#49, gate validated green |
| 2.5 finale: Cai's labeling round 2 → official v2 calibration + reliability analysis | #45 | ✅ done 2026-07-17 — kappa table in `results/judge-calibration.md`; #45 CLOSED |

**Live numbers:** adversarial catch **5/5 (100%)** · escalation recall **1.0** · precision 0.88
· ~**2.9¢/run** · p50 31–34s. Judge on the golden 19: 9 pass / 5 fail / 5 needs_review.
**Judge calibration (41 blind labels):** raw agreement 0.512 · **kappa 0.279** · judge stricter
in 18/20 disagreements · 7/7 flagged "hallucinations" were true tool-derived facts (the judge
is tool-blind — see `reports/task-6-calibration-kappa.md`).

**Gate diagnostic (important):** the margin formula is hand-verified correct, but the 0.02
threshold is structurally near-unreachable (only 2/20 ground-truth tickets clear it). **Zero**
ideal-route cases were blocked by thresholds — the binding gates are the entitlement-receipt
rule and model conservatism (`agent_requested_human` = 14/25). **Do not hand-tune thresholds;**
re-derive from held-out data + the calibration table.

---

## ➡️ Next steps, in order

1. **Week 3 begins** (issues #13–#16, plan below). Choreography and budget rules in this
   file apply unchanged. Two cheap standing items to fold in when convenient: the
   dedicated Neon eval branch (update `EVAL_DATABASE_URL`), and the second rater for
   judge calibration (chore #19).

## 🔭 Weeks 3–4 (so the whole path is visible)

- **Wk3 (issues #13–#16):** console run list/detail → review queue → deploy (Railway + Neon +
  Vercel, **no Docker**) → demo protection (seeded ticket pool only, per-IP rate limit, a
  *visible* spend-cap pause). Descope ladder if overrunning: cut the smoke test → cut JSON logs
  → cut the rate limit. **The daily spend cap is never cut.**
- **Wk4 (issues #17–#18):** demo video → case study + `results/` + final README. The
  **adversarial catch rate is the standalone headline number**. Every deliberate cut gets a
  "what I'd add in production" paragraph. The fail-closed / all-escalate finding is the approved
  opening narrative.
