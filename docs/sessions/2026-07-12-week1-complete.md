# Session Handoff — 2026-07-12 (WEEK 1 COMPLETE — stopped at the Week 2 gate)

**Read this first when resuming.** Supersedes `2026-07-11-week1-handoff.md`.
Per-task detail: `.superpowers/sdd/progress.md` (local ledger).

## Where things stand

**Week 1 is done and merged.** All 9 tasks complete, issues #1–#7 closed (each with a
narrative closeout comment). `main` = `a230052` (PR #27: gate + runner + CLI + E2E
evidence), CI green, no open PRs, no feature branches.

**The Week 1 kill criterion is met**: two live E2E runs through all 5 stages —
Dana's VPN ticket (12027, $0.0362) and the adverse-action variant (12039, $0.0313) —
both correctly `escalated/adverse_action`. The MUST-condition (denial held for human
review) held on both.

**Budget:** ~$0.11 of the $20 hard cap spent. Week 1 came in far under its ~$2 envelope.

## ⛔ THE GATE (why work is stopped)

Standing instruction from Cai: **no Week 2 work until he reviews the checkpoint.**
The llm-council checkpoint he requested has been run (verdict below, full detail in the
session conversation + ledger). He decides: accept the council's mandate and start
Week 2, or adjust first.

## Council checkpoint verdict (2026-07-12, 5 advisors + peer review + chairman)

- **Merge: yes** (done — merged after the known-gap note was added to PR #27's description).
- **The one real finding:** the adverse-action guarantee is enforced by **model
  cooperation, not gate structure**. A soft denial written into `customer_reply` with
  `resolution_type=="solve"` and no `check_entitlement` call would auto-resolve. The two
  live passes happened because the model *did* call the tool — n=2 is evidence, not an
  invariant. This is the third instance this week of "tested sample beat structural
  verification" (after the two SDK incidents).
- **MANDATE — first commit of Week 2, before ANY golden-set/calibration work:** make the
  gate structurally require positive `check_entitlement` tool evidence before a `solve`
  may auto-resolve. TDD (failing soft-denial test first). $0 API cost — pure gate logic.
  Otherwise Week 2's calibration table launders the blind spot into "validated" thresholds.
  Also add a soft-denial case to the 5 adversarial golden cases.
- **CI:** add gitleaks + concurrency-cancel in the next CI-touching PR (~25 min); ruff is
  already gated; keep holding the line against CodeQL/Dependabot (case-study paragraph).
- **Process fix:** review rubric — violation of a written non-negotiable design rule is
  Critical by definition (the whole-branch reviewer scored this gap as a non-issue).

## Final whole-branch review (opus, pre-merge)

Ready to merge; zero Critical/Important. **SDK-assumption sweep clean** — llm.py,
tracing.py, act.py, embeddings.py verified against the installed SDK + committed fixture.
Deferred-minors triage: 9 ACCEPT (case-study material), 8 → **grooming issue #28**.

## Task 9 record (what merged in a230052)

- `scripts/compute_centroids.py` + committed `triagedesk/data/queue_centroids.json`
  (10 queues × 1024 dims; script is sub-batched/paced/resumable for Voyage 3 RPM)
- `triagedesk/pipeline/gate.py` — adverse-action first, then SIM≥0.45 + MARGIN≥0.02
- `triagedesk/pipeline/runner.py` — 5-stage orchestration; every failure → terminal state
  (incl. review-driven catch-all: unexpected exception → `failed/unexpected:<type>`)
- `triagedesk/cli.py` — `run` / `trace` glass-box dump (UTF-8 stdout fix for Windows)
- Live-API finding now regression-tested: strict structured outputs need
  `additionalProperties:false` in the schema (`_strict_schema()` in llm.py). The Week 2
  judge uses this same path — its live smoke + fixture is still required first (SDK-reality
  rule) since the spike never covered structured outputs end-to-end.
- 49 tests + ruff green. Both live runs had **negative classification margin (−0.008)** vs
  MARGIN_THRESHOLD=0.02 — as configured nothing can auto-resolve; that's the honest
  placeholder state Week 2 calibration exists to fix. Do NOT hand-tune before calibration.

## Next steps, in order (after Cai's go)

1. **Week 2 kickoff, commit 1:** structural gate fix (council mandate above) — TDD, $0.
2. **Judge structured-output live smoke + committed fixture** (SDK-reality rule) before
   any judge code.
3. Prompt caching (mandatory early Week 2 — cuts run cost 30–50%).
4. Then the planned Week 2 sequence: golden set (25 cases, 5 adversarial incl. the
   soft-denial case) → deterministic harness + calibration table → judge → kappa
   calibration → CI eval gate. Budget envelope ~$10–12.
5. Grooming issue #28 items ride along where they fit; gitleaks in the next CI PR.

## Standing working preferences (keep honoring)

- Closeout comment on every issue at close; handoff doc at every milestone; ledger current.
- `export TRIAGEDESK_ENV_FILE="C:\Users\Wonton Soup\.secrets\credentials.env"` in every
  shell that touches settings/DB/API. Never print secrets.
- $20 hard budget: intentional usage — cheapest path that fully serves the goal; never
  skip a quality-relevant step to save cents. Track spend in the ledger.
- 14 "(filler)" tickets sit in the dev DB — do NOT bare-delete (E2E evidence runs
  reference seeded rows); handle deliberately in Week 2 (issue #28).

## How to resume

1. Read this doc; `git log --oneline -3`; `cat .superpowers/sdd/progress.md`.
2. Confirm Cai has reviewed the checkpoint and given the Week 2 go.
3. Start at "Next steps" item 1.
