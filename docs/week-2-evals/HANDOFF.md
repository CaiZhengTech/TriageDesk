# Week 2 Execution Handoff — CONTROLLER OPERATING MANUAL (2026-07-12)

**Audience: the next controller session (any model). This doc + project CLAUDE.md +
the Week 2 plan are sufficient to finish this project beginning-to-end.** Supersedes
`2026-07-12-week1-complete.md` as the resume point.

## Orientation — read in this order
1. Project `CLAUDE.md` (auto-loads) — locked stack, non-negotiable rules, status.
2. THIS doc — the execution choreography and current frontier.
3. `docs/week-2-evals/PLAN.md` — canonical Week 2 tasks
   (**read the COUNCIL AMENDMENTS section before Tasks 3–7 work — it is binding**).
4. `.superpowers/sdd/progress.md` — the ledger: every task's commits, findings, budget.
5. `git log --oneline -5` + `gh pr list` + `gh issue list` — trust these over memory.

## Current frontier (as of this doc's commit)
- **Week 2, Tasks 1–2 of 7 DONE and merged** (SDK spike fixture PR #30; prompt
  caching PR #31). Live-run costs now ~30–50% cheaper.
- **Task 3 (golden set, issue #8) IN FLIGHT**: implementer subagent on branch
  `feat/08-golden-set` off `4b1776b`. To check: `git fetch && gh pr list`,
  `.superpowers/sdd/task-3-report.md` (exists only when it finished), branch existence.
  If the agent died mid-task: inspect `git status` on its branch, salvage per its
  report/progress, re-dispatch the remainder — do NOT restart from scratch blindly
  (Task 9 Week 1 precedent: an agent died AFTER completing work; verify before redoing).
- Tasks 4–7 pending, strictly in order (deps: 3→4→5→6→7).
- **Budget: ~$0.13 spent of a HARD $20.** Week 2 envelope ~$10–12. Anthropic spend
  ONLY when a step explicitly says LIVE; everything else is fixtures/fakes at $0.

## The per-task choreography (repeat for Tasks 4, 5, 6, 7)
1. `git checkout main && git pull`; record BASE = `git rev-parse --short HEAD`.
2. Extract the brief:
   `"/c/Users/Wonton Soup/.claude/plugins/cache/claude-plugins-official/superpowers/6.1.1/skills/subagent-driven-development/scripts/task-brief" docs/week-2-evals/PLAN.md N`
3. Dispatch ONE implementer subagent (model: sonnet; NEVER two implementers in
   parallel). The dispatch contains: one line of where the task fits; the brief path
   ("read this first — your complete requirements"); the binding council amendments
   that touch the task; env facts (below); report contract
   (`.superpowers/sdd/task-N-report.md`; final message = status/commits/tests/PR only);
   branch name `feat/NN-slug` off BASE; "push + open PR, do NOT merge".
4. On DONE: `scripts/review-package BASE HEAD` (same scripts dir) → dispatch ONE
   reviewer subagent (sonnet) with brief path, report path, diff path, and the
   task's binding constraints copied verbatim. Reviewer instructions template:
   `.../skills/subagent-driven-development/task-reviewer-prompt.md`.
5. Critical/Important findings → ONE fix subagent (haiku if 1–2 files mechanical,
   else sonnet) → re-review (SendMessage to the same reviewer). Minor findings →
   ledger, deferred.
6. Merge ritual: `gh pr checks N --watch` (must be green — NEVER merge without) →
   `gh pr merge N --squash --delete-branch` → `git checkout main && git pull`.
7. Bookkeeping IN THE SAME BREATH: ledger entry (commits, findings, budget delta);
   TaskUpdate; if the task closes a GitHub issue → closeout comment (see Standing
   Preferences); update this doc's frontier section at milestones.

## Environment facts every subagent dispatch must carry
- `export TRIAGEDESK_ENV_FILE="C:\Users\Wonton Soup\.secrets\credentials.env"` before
  anything touching settings/DB. NEVER print secret values or connection strings.
- Venv: `.venv/Scripts/python -m pytest -q` and `-m ruff check .` (Windows).
- Voyage embeddings: free tier, 3 req/min + 10K tokens/min — BATCH into one
  `embed([list])` call; pace with sleeps; Voyage is NOT Anthropic budget.
- Unit tests: fakes/fixtures ONLY ($0). Committed fixtures:
  `tests/fixtures/sdk_tool_use_shapes.json` (tool_use),
  `tests/fixtures/sdk_structured_output_caching.json` (judge structured-output +
  caching; includes the "plain-str verdict returned 'poor'" trap — judge schema MUST
  use `Literal["pass","fail","needs_review"]`).
- Commits end: `Co-Authored-By: <model attribution per session>`; PR bodies end with
  the Claude Code footer; `Closes #N` only when the issue is fully done.

## Live-run rules (the money)
- Every live step is marked `⚠️ LIVE ($…)` in the plan. Controller runs live steps
  itself OR authorizes an implementer with an explicit call cap and a
  BLOCKED-with-evidence tripwire (Week 1 used ~8 runs max).
- Full eval-suite live runs: ~$1–1.3 each (post-caching). **≤4 during Week 2
  development.** The FIRST harness live run doubles as the entitlement-veto
  diagnostic (read per-case gate reasons before authorizing more runs).
- CI eval gate (Task 7): trigger = `workflow_dispatch` + push filtered to
  eval-relevant paths ONLY (council amendment #5 — never every-merge; Weeks 3–4
  merges would burn $1+/each). $1 in-workflow hard cap stays.
- Track cumulative spend in the ledger after EVERY API-touching step. Quality beats
  frugality within the envelope, but never spend reflexively (memory: api-budget-hard-cap).

## Binding decisions already made (do not relitigate)
- Council amendments in the plan (hold-out rule; expected outcomes = IDEAL behavior;
  Task 7 trigger; kappa disagreement mini-appendix; Haiku cross-judge = stretch only).
- Controller refinement (recorded, applies to Task 3 review): 3–5 golden cases must
  have ideal-outcome = auto-resolve even though they'll FAIL today — an honest red
  beats green-by-construction. Verify the seeded set has this split when reviewing
  Task 3.
- Diagnostic verdict: margin formula CORRECT (hand-verified); 0.02 threshold
  structurally near-unreachable (2/20 ground-truth tickets clear it; median −0.0095).
  Threshold re-derivation happens AFTER harness data exists, from held-out tickets +
  calibration table — never from the golden 25.
- Model: `claude-sonnet-4-6` everywhere; judge = same model at temperature=0.
  Reviewer rubric: violating a written non-negotiable rule = Critical by definition.
- Gate/act invariants (see CLAUDE.md): adverse-action first; entitlement evidence
  required for auto-resolve; signals never include LLM self-reported confidence.

## Task-specific notes for the remaining work
- **Task 4 (harness, #9):** metrics math = pure functions, unit-tested with fakes.
  Live checkpoint = ONE full 25-case run; capture per-case gate reasons; do NOT
  commit a CI baseline from this run (it's diagnostic).
- **Task 5 (judge, #10):** schema Literal verdict (see fixture); temperature=0
  passthrough in structured_call was pre-designed in the plan (optional param, only
  sent when set); judge explanations are NEVER ground truth.
- **Task 6 (kappa, #11):** ⚠️ HUMAN CHECKPOINT — Cai personally labels 40–50 rows
  via the CSV export; STOP and hand him the file with clear instructions; resume on
  his signal. Then kappa + the disagreement mini-appendix (3–5 divergence cases,
  written up — case-study gold).
- **Task 7 (gate, #12):** KILL CRITERION at end of Week 2: eval gate green or the
  Week-3 console is cut to one read-only page. This rule is not negotiable
  mid-project. Baseline file committed only after threshold re-derivation.
- **End of Week 2:** STOP. Hand Cai a state summary for his checkpoint before
  ANY Week 3 work. Update handoff doc + CLAUDE.md + PITCH.md numbers table.

## Standing preferences (Cai — honor ALL of these, every task)
1. **Three deliverables after EVERY completed task:** (a) plain-language explanation
   in chat; (b) analogy-driven comment on the GitHub issue (SHORT — ~1 min read —
   why it matters, builds-on-previous, link to explainer); (c) explainer md in
   that week's `STORY.md` with THREE layers: analogy → Dana's-journey
   walkthrough → "Under the hood" (semi-technical, real component names, no code).
   Include ready-made interview one-liners. (Memory: explanation-format-preference.)
2. **PITCH.md** (`docs/00-spec/PITCH.md`) updated at every milestone —
   30-second story, per-feature one-liners, numbers table.
3. **Closeout comment on every issue at close** (built / how-it-went / decisions /
   next). All of #1–#7 have them; keep the streak.
4. **Handoff doc updated at every stopping point**; CLAUDE.md Status points at the
   latest one; ledger always current.
5. **Dana Fuentes (customer-3, VPN ticket 12027 / dedicated-IP 12039)** is the
   recurring worked example in ALL explanations — continuity is the point.
6. Cai runs (or asks for) an **llm-council checkpoint** at week boundaries and
   before big merges — expect it, don't fight it; feed it real numbers.
7. Git: branch per issue, PR, checks-gated squash-merge, branch deleted. Docs may
   push to main directly (admin bypass is logged).

## Week 3–4 preview (so the end-to-end path is visible)
- Wk3 (issues #13–#16): console run list/detail → review queue → deploy
  (Railway+Neon+Vercel, NO Docker) → demo protection (seeded pool, rate limit,
  visible spend-cap pause). Descope ladder if overrunning: smoke test → JSON logs →
  per-IP rate limit (daily spend cap NEVER cut).
- Wk4 (issues #17–#18): demo video → case study + `results/` + final README
  (adversarial catch rate = headline number; deliberate cuts get "what I'd add in
  production" paragraphs; the fail-closed margin finding is the approved opening
  narrative).
