# TriageDesk — building an AI support agent you can actually audit

An AI agent reads a support ticket, looks up the customer's account, searches a
knowledge base, drafts a reply — then decides whether to send it or hand it to a human.

**Any capable model can draft a plausible support reply. The hard part is knowing when
not to send it**, and being able to prove which parts of your evaluation mean anything.

**Live:** [console](https://triage-desk-xi.vercel.app) ·
[API](https://site--triagedesk-api--26d8jdlxzvsv.code.run) ·
[source](https://github.com/CaiZhengTech/TriageDesk)

~4 weeks part-time · **$20 total API budget, no top-ups** · one person.
Every number below traces to a committed artifact, named inline.

---

## Two tickets

Same complaint. Same agent. Different customer.

| | **Morgan** | **Dana** |
|---|---|---|
| Ticket | "VPN drops every few minutes" | "My VPN keeps disconnecting — client demo at 3pm" |
| Plan | Pro | Basic |
| `check_entitlement("priority_vpn_support")` | **covered** | **not covered** |
| Outcome | **auto-resolved**, $0.037 | **escalated to a human**, $0.041 |

Dana still gets a complete, KB-sourced reply with real troubleshooting steps. It just
reaches a human first — because it carries an implicit *"no"* about the urgency she asked
for, and **the agent is never allowed to deliver a denial on its own.**

That rule is the top of a four-layer gate, and it is the whole thesis: the interesting
engineering isn't drafting the reply, it's deciding whether to send it.

---

## What it actually costs to run

The routing literature's flagship optimization is **model cascading** — run a cheap model
first, escalate on failure. FrugalGPT reports up to 98% cost reduction; RouteLLM ~85%.

Before implementing it, I measured where my cost actually was:

| stage | share of API cost | share of latency |
|---|---|---|
| **act loop** | **91.4%** | **86.7%** |
| pre-check + classify | 8.6% | 12.1% |

Cascading the cheap stages targets **8.6% of API spend**. Then I measured what the system
costs to *operate*, across 13 runs of real production history:

```
API spend            $0.44
human review labour  $30.00     (10 escalations × 6 min @ $30/h)
TOTAL                $30.44
cost per accepted task  $15.22
break-even deflection    1.12%   (actual: 15.4%)
```

**Labour is 98.6% of the bill.** The optimization everyone recommends first would have
addressed roughly **0.1%** of what this system costs to run.

The lever that matters is the **escalation rate** — which is gate design, not model
selection.

⚠️ **The labour rate is an assumption, so here is the sweep**, because a conclusion that
only survives its authors' favourite inputs isn't a conclusion:

| reviewer rate | labour share | break-even deflection |
|---|---|---|
| $15/h | 97.2% | 2.24% |
| $30/h *(used above)* | 98.6% | 1.12% |
| $60/h | 99.3% | 0.56% |
| **$15/h at 3 min** *(most aggressive)* | **94.5%** | **4.48%** |

Even at the most aggressive assumption, labour dominates and the system is past
break-even. The rate is a CLI flag (`--review-minutes`, `--hourly`) so anyone can
disagree cheaply.
→ `triagedesk/evals/unit_economics.py`

**The honest caveat:** this assumes reviewing a drafted reply isn't *slower* than
answering from scratch. That's unmeasured, and it's the assumption that would invalidate
the result.

---

## The results, with the trivial baseline beside them

The golden set is 25 cases, 22 of which should escalate. On that distribution, several
natural-looking metrics are reproduced exactly by a one-line stub:

```python
def triage(ticket):
    return "escalate"
```

So every metric is published next to what that stub scores. The comparison is derived
programmatically, asserted by a test, and **printed on every suite run** — it cannot
quietly stop being true.

| Metric | System | Null stub | Verdict |
|---|---|---|---|
| **Adversarial catch rate** (design-intent) | **1.00** | 0.00 | **real signal** |
| Adversarial catch rate (strict) | 0.60 | 0.00 | real signal |
| Routing accuracy vs dataset labels | 0.286 | 0.00 | real signal — see *The number I can't fix* |
| Escalation precision | 0.917 | 0.880 | real, narrowly |
| Escalation recall | 1.00 | **1.00** | ⚠️ **not distinguishing** |
| Adversarial escalate rate | 1.00 | **1.00** | ⚠️ **not distinguishing** |

*eval_run `a56f283a`, 2026-08-25 · $0.71 pipeline + $0.16 judge · 25 cases · p50 26.2s ·
`results/eval-baseline.json`, `results/null-baseline.json`*

**"Escalation recall 1.0" was the number I most wanted to lead with, and on its own it is
worth nothing.** A system that escalates everything scores it perfectly.

**The headline number is the design-intent adversarial catch rate: 1.00 against a stub's
0.00.** It survives because it is *reason-aware* — a case only counts as caught if the
observed `escalation_reason` matches the layer that was supposed to catch it. A stub has
no reason to report. (The strict variant, 0.60, is the same metric with no equivalence
policy: two traps were caught by a backstop layer rather than their primary. It's a
diagnostic, not the headline — a drop below it means a primary layer stopped firing.)

---

![Judge-human agreement](../../results/judge-vs-human-agreement.svg)

*The whole calibration in one image. The dashed line is my own self-agreement: judge v2
agrees with my round-1 labels more than I agree with myself. Full record and provenance:
[`results/`](../../results/README.md).*

## How the decision is made

```
ticket → pre-check → classify → retrieve → act loop → GATE → auto-send │ human review
         injection/  1 of 10    pgvector   tools +          ▲
         PII screen  queues     k=3, 15 KB  submit          │
                                                    four layers, first match wins
```

| Layer | Blocks when | Why |
|---|---|---|
| 1 · `adverse_action` | the reply denies something, or an entitlement check returned false | **Non-negotiable.** The agent never autonomously tells a customer "no". |
| 2 · `agent_requested_human` | the model itself submitted `needs_human` | The model's own abstention is respected. |
| 3 · `no_entitlement_evidence` | a `solve` grants a plan-gated feature with no `check_entitlement` receipt | An unverified "yes" is a denial the model never flagged. |
| 4 · `low_confidence` | retrieval similarity < 0.45 | The only statistical layer left standing — see finding 2. |

**The gate never reads the model's self-reported confidence.** External evidence only:
what was retrieved, what the tools returned, what the reply actually says.

---

## Then I let real tickets in

For most of the project nothing *arrived*. A human clicked Run on a curated pool — which
meant the pre-check stage, the injection/PII screen that is stage one of the pipeline, had
**never run against untrusted input**. Zero of 13 production runs had ever stopped there.

So I built an intake endpoint and pointed hostile traffic at it. `POST /api/tickets`
accepts arbitrary text and dispatches the paid pipeline, which deliberately inverts the
trust model — every other endpoint is safe because it reads a fixed server-side allowlist.
Each guard is therefore a named threat with a test proving it fires *before any spend*:
shared secret (fail-closed), per-IP rate limit, daily cap re-checked inside the dispatch
lock, schema-enforced length bounds. Auth is asserted to run **before** the rate limiter —
otherwise an unauthenticated flood burns a legitimate caller's quota, a denial of service
needing no credentials.

Then 13 payloads: 4 injection, 3 PII exfiltration, 3 off-topic, and **3 controls** —
legitimate tickets that superficially resemble attacks.

| | result |
|---|---|
| Attacks caught by the layer built for them | **10 / 10** |
| False positives on the controls | **0 / 3** |

The controls are the half that makes it deployable. A screen that catches injections by
flagging an angry customer on their third contact is useless, so "does it leave real
tickets alone" is tested as deliberately as "does it catch attacks."

**And safety turns out to be nearly free:**

| outcome | avg cost |
|---|---|
| attack stopped at pre-check | **$0.0021** |
| customer served end to end | **$0.0332** |

Rejecting an attack costs **6%** of serving a customer — a design consequence, not luck.
The screen runs first, so a caught payload never reaches retrieval or the act loop, the
stages holding 91% of the cost. Safety being cheap is what makes running it on every
ticket defensible.

### What real traffic broke, within minutes

The batch of 12 genuine tickets produced **4 failures**, all at `retrieve`, all Voyage's
free-tier rate limit. Two defects, neither visible before:

- **No retry on the embedding path.** My stated policy — *"retries: 429/5xx, backoff,
  max 3"* — was implemented for Anthropic and not for Voyage. One provider hardened, one
  forgotten.
- **The failure was labelled `unexpected:`.** A provider rate limit is the most *expected*
  failure a hosted pipeline has. The trace is this project's product, so a reason that
  sends the reader hunting for a nonexistent bug is a defect.

Both fixed — and then verified the only way that counts. Tests mock the provider; the
defect they missed was a real provider's real limit under real concurrency. So I re-sent
the same five tickets at 1-second intervals, harder than the batch that broke them:
**5/5 completed, zero rate-limit failures**, against four failures before. $0.13 to know
rather than assume.

**The gap had existed for four weeks and was invisible to 323 passing tests.**
It surfaced within minutes of tickets arriving unattended — because concurrency is a
property of *arrival*, and nothing about a click-to-run demo produces it.
→ `docs/week-4-launch/reports/intake-first-untrusted-traffic.md`

---

## Six things I got wrong

Each was found by measurement, and each has a commit.

### 1 · My headline metrics were reproducible by a stub

Recall 1.00 and precision 0.88 are what `return "escalate"` scores on a 22/25 corpus. I
published the baseline beside them and rewrote the résumé bullet that led with them.

**A correction I made while implementing:** I first believed the *catch rate* collapsed
too. It doesn't. The honest story is narrower and better — I'd caught this exact tautology
once before, fixed it for one metric, and never extended the reasoning to the others.
→ `triagedesk/evals/null_baseline.py`

### 2 · The confidence signal was noise — and repairing it didn't help

The gate's `classification_margin` compares a ticket to its predicted queue's centroid.
Two defects, both measured:

- **Wrong embedding space.** Tickets were embedded as `input_type="query"`, centroids as
  `"document"` — Voyage trains those asymmetrically *on purpose*. Right for the KB search
  the same vector performs; wrong for comparing a ticket to a prototype of tickets.
- **Anisotropy.** The ten queue centroids had **mean pairwise cosine 0.9782** — Technical
  Support vs IT Support was **0.9963**. The margin, a *difference* of two such numbers,
  varied only in the third decimal.

Fixing both widened its usable range ~26×, and a ticket auto-resolved for the first time.
Then I measured whether it had become *informative*, against 41 held-out human labels:

| | pre-fix AUC | post-fix AUC | Δ |
|---|---|---|---|
| Label round 1 | 0.334 | 0.337 | **+0.003** |
| Label round 2 | 0.442 | 0.442 | **0.000** |

**The repair made the signal decisive without making it informative.** It answers *"did
the router agree with itself about the queue?"* while the gate decides *"may this reply be
sent unseen?"* Repairing an instrument doesn't change what it measures. Demoted to
observability — still computed, still in every trace, no longer able to veto.
→ `docs/week-4-launch/reports/margin-separation-measurement.md`

⚠️ Stated in the code, not just here: **this acts on a null result.** Every 95% CI spans
0.50. "Cannot be shown to help" isn't "proven useless" — but a layer that *blocks work*
bears the burden of proof.

### 3 · A safety rule demanded receipts for purchases nobody made

`no_entitlement_evidence` required a `check_entitlement` call behind **every** `solve`. A
password-lockout ticket retrieved its KB article at 0.7175, got a correct unlock reply,
and escalated — because password unlock isn't a plan feature, so it was never checked.

The rule guards a real risk: the model saying "sure, I've enabled that" for something the
plan excludes. But that risk only exists for features a plan can **withhold**. Now scoped
to gated features, derived from `PLAN_ENTITLEMENTS` so it can't drift from the tool the
agent actually calls.

### 4 · An unpinned dependency took production down

`requirements.txt` said `anthropic>=0.116`. A redeploy installed **1.0.0**, which removed
`temperature` from `Messages.create()`. Every run died at pre-check.

**266 mocked tests passed while production couldn't complete a single run.** My own notes
already recorded this failure class from week one — the rule existed; nothing enforced it.
Now `tests/unit/test_sdk_compat.py` introspects the *installed* SDK and names the call site
in its failure message.

### 5 · The regression guard was silently switched off

The eval gate fires on backend changes. It fired on three of them. All three died at
`alembic upgrade head` — the eval database pointed at a deleted branch — **before spending
anything**, so they failed fast and looked like ordinary CI noise.

Three behavioural changes merged with nothing checking them. When I repaired it, **every
floor held and precision improved 0.88 → 0.917.** But I didn't know that for a week, and
*believing* is not *having checked*.

---

### 6 · I lost the most expensive artifact in the project

Writing this case study, I went to regenerate the calibration chart from the label files
and the numbers didn't match. Round 1 reproduced exactly. Round 2 did not: the file on
disk gives 28 pass / 11 fail / 2 needs-review, and every published round-2 figure was
computed from 34 / 5 / 2.

The file is a mid-labeling snapshot — saved the evening of 2026-07-16, a day before I
finished that round. The completed labels went into the database, and the database
expired while the project sat idle. I checked rather than assumed: `eval_results` now
holds zero rows.

So the 41 hand-applied labels — the only artifact here that no script can regenerate,
the thing that cost human hours and encodes a judgment nothing else reproduces — existed
in exactly two places, and one of them was a free-tier branch with a clock on it. The
other was one laptop. `.gitignore` had excluded them wholesale on a reasonable-sounding
rule: *contains ticket text, never commit.*

That rule was right about the ticket text and wrong about the labels. They are different
things living in one file, and I never separated them. `results/human-labels.csv` now
commits the labels alone — `result_id` and verdict, a few hundred bytes, no ticket
bodies. Both halves of the original concern are satisfied, and always could have been.

**What I did about the numbers.** I did not withdraw them and I did not quietly restate
them. They were computed correctly, from data that existed at the time. They are now
*archived*: recorded, not re-derivable. The calibration file says so at the top, the
provenance is machine-readable in `results/human-labels-provenance.json`, and the chart
draws every round-2 bar hatched so nobody reads it as verified. Round 1 and the finding
that actually carries the calibration — *the judge improved invariantly, and the human is
the noisier instrument* — rest on data that survives.

**This is the fourth time.** The Railway start command, the demo pool, and two golden
test cases were all lost the same way, and I wrote the lesson down each time: *it lived
outside version control.* I wrote it down three times and still lost the one thing I
could not rebuild. Writing the lesson is not the same as applying it — the check has to
run on its own, or it doesn't run.

---

## The number I can't fix, and won't hide

Routing accuracy against the dataset's own labels is **0.286**. Two independent methods
agree it's a ceiling, not a defect:

| method | accuracy |
|---|---|
| LLM classifier | 0.286 |
| nearest-centroid on embeddings | 0.28 |
| random (10 classes) | 0.10 |

Two unrelated approaches landing within a point of each other means the constraint is the
**label set**. The geometry says why: Technical Support and IT Support sit **0.9963**
cosine apart. They aren't two categories.

**The controlled comparison is inside the project:** the KB docs I *authored* separate at
**0.747** mean pairwise cosine; the queue taxonomy I *inherited* sits at **0.941**. Same
embedding model, same pipeline. The thing I designed is separable; the thing I was handed
isn't.

### Why I didn't just rebalance the golden set

The obvious fix to "22 of 25 cases escalate" is to add auto-resolvable cases. **I tried.**
I searched all 11,922 ingested tickets for password-reset, VPN, billing-cycle, API-key and
service-status phrasing and found *essentially zero genuine "how do I…" tickets* — the
corpus is verbose synthetic enterprise-incident narratives (data breaches, integration
failures, campaign metrics). The three route cases exist only through manual swaps.

So the imbalance is a **property of the corpus**, not a labelling shortcut. Forcing balance
would mean relabelling cases against their content, or authoring tickets I already know the
KB answers — writing the test to the answer. I published the null baseline instead.

The same logic rules out the other tempting fix: merging Technical Support into IT Support
*after* observing they're 0.996 apart is fitting the taxonomy to the result I want to
report.

### And a ceiling on the evaluation itself

My own label self-agreement — relabelling the same 41 replies three days apart — is
**Cohen's κ = 0.212** (archived; see §6), *lower* than the judge's agreement with either round.
**Single-rater ground truth is the binding constraint**, not the model. Every confidence
interval in this project is pinned open by having 41 labels from one person. The fix is a
second rater, not more tuning.

---

## What I deliberately did not build

| Cut | Why |
|---|---|
| **Model cascading** | Measured: targets 8.6% of API spend, which is 1.4% of total cost. |
| No orchestration framework | The agent loop is ~120 lines. LangChain would hide exactly what's worth understanding: what enters the context window each lap, and who decides when to stop. |
| No chunking | Measured: KB docs separate at 0.747, uniform 1.6–2.5KB. Nothing is being blurred. |
| Multi-agent | Adds coordination failure modes to a system whose value is auditability. |
| Reflection loops | Multiplies the stage already at 91% of cost, to improve a reply quality I can't yet measure (κ 0.212). |
| Semantic caching | Needs query repetition; a demo pool has none. |
| Real OTel export | Spans use `gen_ai.*` conventions in Postgres — the naming is the portable part. |

**Still unbuilt:** a queue. Inbound tickets dispatch straight to background tasks, which
is why 12 concurrent arrivals hit a provider rate limit. Retry absorbs it now; real volume
would need a proper queue with concurrency control.

**Extractions I'd ship next, and haven't:** the null-baseline harness is ~200 lines and
reusable by any team whose eval suite has never been checked against a constant predictor.
The taxonomy-separability audit — embed your label set, compute mean pairwise centroid
cosine — tells you *before* you spend anything on modelling whether your ceiling is the
classifier or the labels.

**Still open:** a second rater. It's the cheapest change with the largest effect on every
number in this document, and it needs a person, not money.

---

## What it cost

| | |
|---|---|
| API spend | **~$13.4 of $20**, no top-ups |
| Tests | **329**, gating every merge |
| Per-run cost | $0.028 avg, hard-capped at $0.10, fail-closed |
| Latency | p50 26.2s |
| Production runs | 39, including 15 blocked attacks |

`results/` holds the artifacts, `docs/week-4-launch/reports/` holds the measurements, and
the scripts that generate them are committed. Every figure is reproducible.

---

*I built an AI support agent, then spent most of the time proving which parts of its
evaluation actually meant anything — and published the parts that didn't.*
