# RESUME HERE — Controller Operating Manual

**Any new session starts with this file.** Written so a fresh controller (any model) can
finish this project end-to-end without guessing. Last updated: 2026-07-14.

---

## ▶️ CURRENT FRONT ITEM — Task 7, then STOP

**The labeling blocker is CLEARED (2026-07-14).** Cai labeled all 41 rows; `label-import` +
`calibrate` ran; issue #11 is closed. Results: **kappa 0.279**, raw agreement 0.512, and the
root cause — **the judge is tool-blind** (it grades against KB-only context, so true
tool-derived facts like "you're on the Pro plan" look like hallucinations; 7/7 replayed
against the simulated CRM were correct). Artifact: `results/judge-calibration.md`; analysis:
`reports/task-6-calibration-kappa.md`.

**What remains in Week 2:**
1. **Task 7 — CI eval gate (issue #12), the kill criterion.** Dispatch per the choreography
   below. Design consequence of the calibration result (already consistent with the plan):
   **judge metrics get a tolerance band; deterministic metrics carry the gate.** A kappa-0.279
   judge advises, it does not veto.
2. **Then STOP.** Cai runs his end-of-Week-2 llm-council checkpoint — hand him a state
   summary. **No Week 3 work before that checkpoint** (Cai re-confirmed this 2026-07-14).
   Top agenda item for the council: whether to add tool-call evidence to the judge's context
   (mechanical fix, ~15¢ re-judge via backfill + a second human labeling pass) or ship the
   honest 0.279 with the analysis.

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

## 💰 Budget — HARD CAP $20, no top-ups (~$3.05 spent)

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
| 7 CI eval gate — **KILL CRITERION** | #12 | ⬜ not started |

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

1. **Task 7 — CI eval gate (issue #12).** Brief: `task-brief docs/week-2-evals/PLAN.md 7`.
   Trigger = `workflow_dispatch` + eval-paths filter. Deterministic metrics gated exactly
   against a committed baseline; judge metrics with a tolerance band. **The baseline is
   committed only AFTER threshold re-derivation** — the first run's numbers are diagnostic, not
   a target (baseline-from-first-green-run is circular reasoning).
2. **KILL CRITERION (end of Week 2):** if the eval gate is not green, the Week-3 console is cut
   to a single read-only page and the hours go to pipeline + evals. Not negotiable mid-project.
3. **STOP.** Hand Cai a state summary for his end-of-Week-2 checkpoint (he runs llm-council).
   No Week 3 work before that.

## 🔭 Weeks 3–4 (so the whole path is visible)

- **Wk3 (issues #13–#16):** console run list/detail → review queue → deploy (Railway + Neon +
  Vercel, **no Docker**) → demo protection (seeded ticket pool only, per-IP rate limit, a
  *visible* spend-cap pause). Descope ladder if overrunning: cut the smoke test → cut JSON logs
  → cut the rate limit. **The daily spend cap is never cut.**
- **Wk4 (issues #17–#18):** demo video → case study + `results/` + final README. The
  **adversarial catch rate is the standalone headline number**. Every deliberate cut gets a
  "what I'd add in production" paragraph. The fail-closed / all-escalate finding is the approved
  opening narrative.
