# RESUME HERE — Week 4 state + how to continue

**Any new session starts with this file.** Last updated: 2026-08-25 — intake
endpoint live (#80), embedding retry shipped (#81), `results/` finalized (#18).
Console: https://triage-desk-xi.vercel.app · API:
https://site--triagedesk-api--26d8jdlxzvsv.code.run (Northflank — Railway is gone;
older Railway URLs below and in `week-3-console/` are historical deploy records).

> The **operating manual** (environment facts, per-task choreography, budget
> rules, binding decisions) lives in
> [`../week-2-evals/HANDOFF.md`](../week-2-evals/HANDOFF.md) — still applies
> verbatim. Week 3 deploy facts: [`../week-3-console/HANDOFF.md`](../week-3-console/HANDOFF.md).
> This file holds only Week 4 state.

---

## 📌 LATEST SESSION (2026-08-25): `results/` done, label provenance repaired

**Merged #82.** `results/` is finalized for #18: the agreement chart, an index
README, and -- the reason this took a session instead of an hour -- the human
labels are now in version control.

**The finding.** The published round-2 calibration numbers do not reproduce.
Round 1 does, exactly. Round 2's surviving file is a mid-labeling snapshot; the
completed labels died with the Neon branch (#64) and `eval_results` is empty
(verified). Four published figures -- official v2 kappa 0.133, self-agreement
0.212, the v2 confusion matrix, the 14-flip count -- are now **archived**:
correct when computed, no longer re-derivable. They are quoted as such
everywhere, and the chart hatches them.

**Do not "fix" these numbers by recomputing from `judge_labels_v2.csv`.** That
file is the snapshot, not the round. Recomputing silently replaces an archived
figure with a different one and destroys the audit trail. If round 2 is ever
wanted back, it must be **relabelled**, and that is a new round with a new date.

**Rule going forward:** anything a script cannot regenerate goes in git the day
it is created. Fourth instance of this failure; the first that was unrecoverable.

**Spend this session: $0.** No eval-path files touched, so the gate did not fire.

**Remaining for #18:** one console screenshot for the README, then #17 (video),
which needs Cai. Nothing else is blocked.

---

## ✅ CURRENT STATE (2026-08-21): LIVE, and the gate auto-resolves

**Console:** https://triage-desk-xi.vercel.app
**API:** https://site--triagedesk-api--26d8jdlxzvsv.code.run (Northflank, US-Central)
**DB:** Neon, rebuilt from scratch via `python -m scripts.bootstrap`

### ⚠️ ONE ACTION OUTSTANDING

`CORS_ORIGINS` is **not set** on Northflank — confirm with
`curl <api>/health` → `"cors_configured": false`. Pages render (Next fetches
server-side) but every browser-side call fails: the demo Run button and the
trace expander. Set `CORS_ORIGINS=https://triage-desk-xi.vercel.app` in the
Northflank service env and redeploy.

### The headline: first auto-resolve in the project's history

Ticket **80010** (Morgan, **pro** plan, plain VPN question) ran end to end and
returned `state: completed`, `escalation_reason: null`. Same ticket, before
and after the gate repair, **identical retrieval similarity (0.7295)**:

| | margin | outcome |
|---|---|---|
| Before | **−0.007037** | escalated `low_confidence` |
| After | **+0.013737** | **completed** |

Nothing else changed. `MARGIN_THRESHOLD` is still 0.0 — no threshold was tuned.

**Safety layers survived**: both adverse-action tickets (80007, 80019) still
escalate correctly. That was the check that mattered.

**Dynamic range is real**: observed production margins now span +0.0137 to
−0.2354 (~0.25 wide) against an old band of roughly ±0.007 — the ~26× widening
measured offline shows up in live runs.

⚠️ **n=1, on a ticket authored the same day.** This is a *capability existence
proof*, never a resolution rate. Do not quote it as one — see #68.

### Shipped 2026-08-25 — the eval gate works again, and nothing regressed

**#61 — dedicated Neon `eval` branch.** Host `ep-winter-paper-ats1h5wu`, verified
distinct from prod and test, migrated and seeded, `EVAL_DATABASE_URL` repointed. Every
eval-gate run since the Neon expiry had died at `alembic upgrade head` without spending
anything, so the regression guard was **silently non-functional across #64, #69 and
#74** — three behavioural changes merged with nothing checking them.

**#75 — baseline re-derived. EVERY FLOOR HELD.**

| metric | floor | observed |
|---|---|---|
| routing_accuracy | 0.20 | **0.286** |
| escalation_recall | 1.00 | **1.000** |
| escalation_precision | 0.80 | **0.917** (was 0.88) |
| adversarial_catch_rate | 1.00 | **1.000** |
| adversarial_catch_rate_strict | 0.60 | **0.600** |
| cost_per_run | ≤$0.08 | **$0.0283** |

The #75 worry — that a looser gate would drop recall below 1.00 and block merges — did
not materialise. The cases that now auto-resolve are ones that *should* route, so recall
is untouched and precision **rose**: a false-positive escalation became a true negative.
#69 and #74 working as designed, measured rather than asserted. `escalation_precision`
now beats the null baseline (0.917 vs 0.880) for the first time.

**#79 — cost per accepted task, on 13 runs of real history:**

```
API spend            $0.4368
human review labour  $30.00     (6 min @ $30/h, 10 escalations)
TOTAL                $30.44
cost per accepted task  $15.22
deflection rate         15.4%
break-even deflection    1.12%
```

**Labour is 98.6% of the bill.** This reframes the optimization research: model cascading
was declined for targeting 8.6% of API spend — and API spend is 1.4% of total cost, so
the literature's flagship optimization addresses ~**0.1%** of what this system costs to
run. The lever that matters is the escalation rate, which is gate design, not model
selection. Break-even at 1.12% means the pipeline pays for itself deflecting 1 ticket in
89; at 15.4% it is ~14x past that.

⚠️ Caveat carried in the code: assumes reviewing a draft is not *slower* than answering
from scratch. Unmeasured, and it is the assumption that would invalidate the result.

**Ingest guard, found the hard way.** Bootstrap failed partway while seeding the eval
branch, was re-run with `--force`, and ingest ran twice. Ticket ids encode insertion
order and `golden_expectations.json` names tickets by id — so the second pass appended a
full copy at ids 11923+, and `build_calibration_pool` (which samples at runtime) drew
**14 of 25 cases from phantom rows**. The golden 20 survived only because their ids are
committed to a file. `ingest_tickets` now refuses a second pass without `--reingest`.

### ✅ Tier 1 and Tier 2 of the decision menu are COMPLETE

Remaining: **#17 (demo video)** and **#18 (case study)** — the actual deliverables — plus
optional Tier 3. Budget ~$7.2 of $20.

### Shipped 2026-08-23 — evidence and correctness batch

| # | What | Cost |
|---|---|---|
| #68 | **Null baseline published beside every metric.** Derived through the real `summarize()`, printed on every suite run with a `NOT DISTINGUISHING` marker. | $0 |
| #76 | Landing copy no longer claims nothing auto-resolves. | $0 |
| — | **CI split into `test` (unit) and `integration`.** 266 of 290 tests (92%) now run with no external service reachable. | $0 |
| — | Pinned `voyageai<1.0` — same unpinned-major class as the #71 outage. | $0 |

**The #68 correction worth knowing:** the design-intent adversarial catch rate does
**not** collapse to a stub. It is reason-aware, so a stub with no `escalation_reason`
scores 0.00. Three metrics collapse — `escalation_recall` (1.00),
`escalation_precision` (0.88, which is the 22/25 base rate), and
`adversarial_escalate_rate` (1.00). Three carry real signal — both catch rates and
`routing_accuracy`.

`PITCH.md:128` already recorded the insight from Week 2.5 ("a system that blindly
escalates everything would score 100%"). It was applied to one metric; this extended it
to the rest. The résumé bullet was rewritten accordingly.

**One near-miss worth recording:** the CI split initially set `name:` on the jobs, which
overrides the *check* name — and branch protection on main requires a check literally
called `test`. That would have left PRs waiting forever on a status that no longer
existed, silently disabling protection rather than failing loudly. Caught before merge;
the constraint and its verification command are now a comment in `ci.yml`.

### 🔴 #61 is now the critical path

`EVAL_DATABASE_URL` points at a deleted Neon branch, so the eval gate has been
**non-functional through every gate change this week** — it dies at `alembic upgrade
head` before spending anything. Queued behind it: #75 (re-derive the stale baseline),
the risk-coverage curve, and any claim that this week's gate changes did not regress
anything.

Needs the Neon dashboard: create a dedicated eval branch, migrate it, repoint the secret.

### Gate behaviour, verified live (2026-08-21)

| Ticket | Outcome | Why |
|---|---|---|
| 80010 Morgan / **pro** / VPN | ✅ **completed** | plan covers the feature, KB answers it |
| 80011 Taylor / basic / lockout | ✅ **completed** | nothing plan-gated, KB answers it |
| 80007 Dana / basic / VPN | escalated `adverse_action` | genuine denial |
| 80019 Dana / basic / dedicated IP | escalated `adverse_action` | genuine denial |

**2 of 4 auto-resolve; the 2 escalations are both real denials.** The premise
works: routine KB-answerable tickets close themselves, customer-facing "no"
always reaches a human. Safety layers verified three separate times across the
day's changes.

80011 completed with `classification_margin: -0.1409` recorded in its trace —
the demoted signal visibly disagreeing while the decision proceeds. That is what
observability-not-veto looks like, and it is a better demo than hiding a signal
you chose not to trust.

### The margin was demoted on evidence (#74)

Measured against held-out human labels, it could not be shown to separate good
replies from bad — AUC 0.334 / 0.442, both 95% CIs spanning 0.50, and the #67
repair moved those by +0.003 / 0.000. The repair made it *decisive* without
making it *informative*: it asks "did the router agree with itself about the
queue", not "may this reply be sent unseen".

`low_confidence` is now retrieval similarity alone. `SIM_THRESHOLD` unchanged at
its derived 0.45 — re-tuning a threshold while changing what it gates is how a
tuning decision gets laundered. Acts on a **null result**, which is stated in the
code and the report, not just the commit message.
Full measurement: `reports/margin-separation-measurement.md`. Re-runnable for $0
(`python -m scripts.measure_margin_separation`; signals cached).

### The KB is not the problem (checked, $0)

Hypothesis: maybe retrieval underperforms because the KB docs are poorly
structured. Measured — they are not:

| | mean pairwise cosine |
|---|---|
| Queue taxonomy (10 centroids) | **0.9414** |
| KB docs (15) | **0.7472** (range 0.632-0.884) |

Doc lengths are uniform (1612-2490 chars), so whole-doc embedding isn't blurring
multi-topic documents — the "no chunking" cut holds up. Same model, same
pipeline: **the authored KB separates cleanly; the inherited Kaggle queue
taxonomy does not.** That is a sharper framing of the 0.29 routing finding than
"the dataset is noisy" — it's a controlled comparison inside the project.

Watch item: `password-reset-and-lockout` <-> `reporting-security-concerns` at
0.8835 is the one genuinely confusable pair, and 80011 is a lockout ticket. It
retrieved correctly here, but that is where a near-miss would produce a
plausible-looking wrong answer.

### What was fixed to get here

| # | Fix |
|---|---|
| #69 | `no_entitlement_evidence` was over-scoped — demanded a receipt on tickets with no entitlement at stake. Now scoped to plan-gated features, derived from `PLAN_ENTITLEMENTS`. |
| #67 | The margin was noise — `input_type` mismatch (query vs document) + anisotropy (centroids at 0.978 mean cosine). Centroids recomputed with matching `input_type`; margin now mean-centred. |
| #71 | **Prod outage:** `anthropic>=0.116` unpinned; the redeploy installed 1.0.0, which removed `temperature` from `Messages.create()`. Every run died at precheck. Pinned `<1.0` and added `test_sdk_compat.py`, which introspects the **installed** SDK — the first real enforcement of the project's own SDK-reality rule. |
| #64 | Neon branches expired; DB rebuilt reproducibly. Demo pool and golden set are now repo-owned. |
| #60/#63/#66 | Railway paused → migrated to Northflank; `Procfile` + `.python-version` committed; console degrades instead of 500ing; `/health` reports config. |

### 🔴 Highest-priority open item: #68

**Three published headline numbers are matched by a one-line `return "escalate"`.**
Verified arithmetic: on the 22-escalate/3-route golden set, the null stub scores
escalation recall 1.00, precision 0.88, adversarial catch 5/5 — identical to what
the README publishes. The strict 3/5 catch rate does *not* collapse to the stub and
is currently the only headline safety number that distinguishes the system from it.

Publish the baseline beside every metric before anything else.

### Still open on #67

Re-run the **held-out calibration pool**, measure whether the repaired margin
separates human-pass from human-fail replies, and only then decide whether it
keeps its veto or becomes an observability signal. Then re-derive
`results/eval-baseline.json` (also required by #64's golden-set change).

### The lesson that keeps repeating

Railway's start command, the demo pool, and two golden cases were all lost the
same way: **they lived outside version control.** #63 and #64 move all three
into the repo. Before adding any new deploy or seed step, ask where it lives if
the machine holding it disappears tonight.

## Week 4 progress

| Item | Issue | State |
|---|---|---|
| Console redesign — flight-recorder identity, dark-only, cockpit-stack landing | #56 | ✅ merged `b66aa78` (PR #57, squash) — **CLOSED**, `console/**`-only, $0 gate |
| Live run progress — demo watches the pipeline execute; backend moved to `BackgroundTasks` | #58 | ✅ merged `cb69291` (PR #59, squash) — **CLOSED**, touches `triagedesk/**` ⇒ eval-gate fired, **PASSED**, $0.879 |
| Post-merge polish (not separately issued, same PR #59 branch before merge) | — | ✅ typed-headline rotation bugfix + dynamic height, one-stage-at-a-time lifecycle pulse (was trailing), expandable run/review cards, page transitions, Home nav, GitHub repo links, readable agent-reply prose (`white-space: pre-wrap` + bold) |
| Demo video | #17 | not started |
| Case study + `results/` + final README | #18 | not started |

**Deferred, tracked verbally (not yet an issue):** seed one demo-pool ticket
that's genuinely auto-resolvable (KB-answerable, no denial), to prove the
gate *can* auto-resolve rather than always escalating — every current
demo-pool ticket is deliberately adverse-action-shaped by design, so 100%
escalation there is correct behavior, not a defect. Open as an issue before
acting on it (council/golden-set discipline applies — no hand-tuning the
gate).

## 🌐 Live deployment facts (re-verified 2026-07-21, after PR #59 merge)

| Thing | Value |
|---|---|
| Console | https://triage-desk-xi.vercel.app — confirmed serving the new build (`/runs`, `/demo` 200; landing markup includes the new "Lifecycle" panel + GitHub source link) |
| API | https://agenticproject-production.up.railway.app — `GET /api/runs` and `GET /api/demo/pool` both 200 |
| CI on `main` | `ci` ✅ success · `eval-gate` ✅ success (PASSED, $0.879) — both on merge commit `cb69291` |
| DB | Neon `prod` branch — **also currently receiving eval-gate golden-set runs, see finding above** |

## Budget

Week-3 close was **≈$9.6 of $20**. Since then:
- PR #57 (#56): $0 (console/docs-only, no gate).
- PR #59 (#58) eval-gate: **$0.879** (`$0.719022` eval + `$0.160035` judge),
  confirmed from the CI log, gate **PASSED**.
- Demo-pool verification runs this session (mislabeled "dev branch" in the
  task report — see correction): **8 runs, $0.3007 exact** (queried from
  prod `/api/runs`, 2026-07-19T08:29 through 2026-07-20T19:59, the 25
  golden-set runs excluded by timestamp window).
- **Running total: $9.6 + $0.879 + $0.3007 ≈ $10.78 of $20.** The 25
  golden-set eval runs' $0.879 is already counted via the eval-gate line —
  don't double-count it if re-deriving from prod's raw run list.

## ✅ Verify at session start (30 seconds)

- `curl https://agenticproject-production.up.railway.app/api/runs?limit=1` →
  200 with a run. If down, check Railway deployments (failed pre-deploy
  migration is the usual cause after a schema change — none happened this
  week, so unlikely).
- `gh run list --branch main --limit 2` → both `ci` and `eval-gate` (if
  triggered) should read `success`.
- Read the eval-gate finding above before running any eval-path merge again.
