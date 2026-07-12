# TriageDesk — Project CLAUDE.md

AI support-ticket triage agent with a "glass-box" ops console. Portfolio project targeting
Northeast US (NYC/Boston) new-grad SWE roles, fall 2026 cycle. The differentiator is NOT the
agent — it's the eval/observability/trust discipline around it (market research: eval design
is the #1 hiring signal; plain RAG demos are a yellow flag).

## Status (updated 2026-07-12)

**WEEK 1 COMPLETE.** All 9 tasks merged (`main` = `a230052`); issues #1–#7 closed with
closeout comments. E2E kill criterion met: two live runs through all 5 stages, both
correctly `escalated/adverse_action`. ~$0.11 of the $20 budget spent.
**⛔ STOPPED at the Week 2 gate — Cai reviews the checkpoint before any Week 2 work.**
**→ RESUME HERE: read `docs/sessions/2026-07-12-week1-complete.md`** (council verdict,
Week 2 mandate, ordered next steps). Per-task detail: `.superpowers/sdd/progress.md`.

- **QA hardening DONE (PR #29 → `627f778`):** the council-mandated gate fix landed —
  gate now structurally requires `check_entitlement` execution evidence before any
  `solve` auto-resolves (escalates `no_entitlement_evidence` otherwise; TDD'd). Plus:
  CostUnknownError fail-closed typing, cost boundary tests, runner/act test gaps,
  gitleaks in CI (inside the `test` job) + concurrency-cancel, filler tickets cleaned.
  Issue **#28** tracks the two genuinely-Week-2 leftovers (judge live smoke; soft-denial
  golden case). Recruiter-friendly write-up: `docs/superpowers/explainers/`.
- **Week 2 sequencing:** judge structured-output live smoke + fixture (SDK-reality
  rule, FIRST) → prompt caching → golden set (incl. soft-denial adversarial case) →
  harness/calibration → judge → kappa → CI eval gate.
- **Standing explanation rule (Cai, 2026-07-12):** every completed task gets (1) a plain
  chat explanation, (2) an analogy-driven issue comment for non-technical readers,
  (3) an explainer md in `docs/superpowers/explainers/` with interview one-liners.
- **Model:** `claude-sonnet-4-6`, effort high; adaptive thinking in act loop only. Judge can
  run temp 0 on the same model.
- **Infra facts:** branch protection on main (test check + up-to-date required; verify
  `gh pr checks` before merge); `TRIAGEDESK_ENV_FILE` env var required for anything touching
  settings (no hardcoded path anymore); CI runs bare `pytest` (pythonpath fix in pyproject).
- **Key incidents on record:** (1) plan's `structured_call` broken vs real SDK despite green
  mocked tests → SDK-reality rule in plan Global Constraints; (2) strict structured outputs
  need `additionalProperties:false` — caught by a $0 live 400, now regression-tested;
  (3) both live runs' classification margin was negative (−0.008) — nothing auto-resolves
  until Week 2 calibration sets real thresholds (deliberate; do not hand-tune).

**Spec remains the design record:** `docs/superpowers/specs/2026-07-10-triagedesk-design.md`.

## Development process (issue-driven — follow this)

- **Issues = tracking layer** (lean: goal, acceptance criteria, deps). **Plan docs =
  canonical layer** (code-level detail, `docs/superpowers/plans/`, one per week).
  If they ever conflict, update the issue to match the plan.
- Work order = the number in the issue title. Per issue: branch → TDD → PR referencing
  the issue → disciplined self-review via the PR checklist → merge closes it.
- Non-code issues (KB doc authoring, the friend favor) get NO branch/PR/TDD ceremony.
- superpowers discipline throughout; fire `how-we-got-here` after backend/AI-ML/infra work.

### Issue explanation format (Cai's chosen learning style — keep using it)
Every issue has a collapsible `<details>` "🧠 Understanding this issue" section with fixed
template: In one sentence (for anyone) / Where it sits (ASCII diagram + YOU ARE HERE) /
Problem / Analogy / One ticket's journey / What breaks without it (disaster story) /
Jargon glossary / Feeds into. **The recurring worked example is "Dana's VPN ticket"**
("My VPN keeps disconnecting — client demo at 3pm"; adverse-action variant: Dana requests
a premium feature her plan excludes). Reuse Dana in all future explanations, docs, demo,
and case study — continuity is the point. Full preference saved in session memory
(`explanation-format-preference`).

## Locked stack (do not relitigate)
- Python / FastAPI / SQLAlchemy 2.0 / Alembic
- Postgres on Neon free tier, pgvector extension (NO separate vector DB)
- Hand-written agent loop on the Anthropic SDK — deliberately NO LangChain (interview story)
- Thin Next.js console on Vercel; API on Railway via Nixpacks (NO Docker anywhere —
  Windows/WSL2 friction; integration tests hit a Neon test branch, locally and in CI)
- GitHub Actions CI; Kaggle "Customer IT Support" dataset (Tobias Bueck); ~15 authored KB
  docs, whole-doc embeddings, k=3, no chunking/tuning

## Architecture (summary — spec is the full record)
Pipeline: pre-check → classify → retrieve (pgvector) → act loop (tools:
`lookup_account_status`, `check_entitlement`) → multi-signal confidence gate →
auto-resolve / escalate to human review queue. Run states: `completed | escalated |
failed` (loop exhaustion = escalated with reason `agent_incomplete`). Failed runs are
simply visible in the console — no dead-letter workflow. Traces use OTel GenAI semantic
conventions (`gen_ai.*`) stored in hand-rolled Postgres tables. 7 tables: tickets, runs,
spans, kb_docs, eval_cases, eval_results, review_decisions.

## Non-negotiable design rules
- **Adverse-action rule:** the agent never autonomously delivers a customer-facing denial;
  those always route to the review queue. Internal rationale is always logged (trace =
  evidence, LLM rationale = post-hoc context, never ground truth).
- **Fail closed on cost:** per-run cap ~$0.10; if cost can't be computed, treat as breach
  → escalate.
- **Gate never uses LLM self-reported confidence** — retrieval similarity + classification
  margin only (validated by the Wk2 calibration table before adding signals).
- **Evals-first.** Judge: pinned model, temp 0, pass/fail/`needs_review`, calibrated vs
  ~40–50 human labels (Cohen's kappa).
- Retries: 429/5xx, backoff, max 3 / 60s. Pydantic + ONE repair re-prompt. Tool errors:
  once, then escalate.

## Checkpoints and kill criteria (set while calm — not negotiable mid-project)
- **End of Wk1 (issue #7):** one ticket end-to-end through all 5 stages, however crude.
  If not green → spend Wk4 buffer hours immediately; NEVER compress Wk2.
- **End of Wk2 (issue #12):** CI eval gate green, or console is cut to one read-only page.
- **Wk3 descope ladder (cut in order):** post-deploy smoke test → JSON logs → per-IP rate
  limit. The daily spend cap is never cut.
- Everything deliberately cut (contract tests, nightly evals, Docker, cached demo
  fallback, waterfall visuals, real OTel export) gets one "what I'd add in production"
  paragraph in the case study — do not quietly add these back.

## 4-week plan (part-time, ~45–50h total — top of budget)
- **Wk1 (issues 01–07):** scaffolding+CI → DB+ingest → tracing layer → pre-check+classify
  → KB+retrieve → act loop → gate+CLI dump. Error handling built INLINE (one-touch rule).
- **Wk2 (issues 08–12):** golden set (25, 5 adversarial) → deterministic harness +
  calibration table → judge → kappa calibration → CI eval gate.
- **Wk3 (issues 13–16):** console run list/detail → review queue → deploy
  (Railway+Neon+Vercel) → demo protection (seeded pool, rate limit, visible spend-cap pause).
- **Wk4 (issues 17–18):** demo video → case study + `results/` folder + final README
  (adversarial catch rate as standalone headline number).

## Working conventions (this project)
- Secrets: `C:\Users\Wonton Soup\.secrets\credentials.env` only; `.gitignore` already
  covers `.env*`; `.env.example` documents required vars. Verify coverage before commits.
- Durable learnings → vault raw source (`raw/YYYY-MM-DD-<slug>.md`) → SCREEN → INGEST.
- Scope discipline: the design survived four council rounds that hunted over-engineering.
  Before adding anything, check it against the hour budget, the ladders, and the cuts list.
