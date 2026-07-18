# TriageDesk — The Pitch File

*One file to read before any interview or recruiter conversation. Updated at every
milestone. Everything here is true and defensible — every claim traces to a commit,
a test, or a logged run.*

**Last updated:** 2026-07-18 (**Week 3 COMPLETE — the system is LIVE**:
**https://triage-desk-xi.vercel.app** — the glass-box console on the public internet,
behind real abuse protection, smoke-verified end-to-end at 3.6¢/run. Nothing descoped.)

---

## How to use this file (30-second map)

| If they ask about… | Jump to |
|---|---|
| "Tell me about a project" | **The 30-second pitch** → **the one-minute version** |
| Safety / trust / guardrails | *Safety & trust* one-liners |
| The agent / LangChain / SDK | *The agent* one-liners |
| Evals / testing / metrics / honesty | *Evals & honest numbers* one-liners |
| The UI / observability / demo | *The glass box you can see* one-liners |
| CI / process / scope | *Process & limitations* one-liners + *"What I'd add in production"* |
| Hard numbers | **The numbers** table at the bottom |

*The spine of every answer: this project's value isn't the AI, it's the **trust
machinery** around it — evidence trails, fail-closed cost caps, a structurally-enforced
safety rule, and evals I calibrated against my own labels and then caught lying to me.*

---

## The 30-second pitch (lead with this)

> "I built TriageDesk — an AI agent that triages customer support tickets, but the
> point isn't the AI. It's the trust machinery around it: every decision leaves an
> evidence trail with per-run dollar costs, hard spending caps that fail closed, and a
> safety rule — the AI never delivers bad news to a customer on its own — that's
> enforced by code structure, not by hoping the model behaves. I proved that last part
> the hard way: an adversarial review of my own finished work found the rule could be
> bypassed, so I wrote the exploit as a failing test, then closed the hole
> structurally."

## The one-minute version (if they lean in)

> "It's a five-stage pipeline: a safety screen, a classifier, retrieval over a
> knowledge base, a hand-written agent loop with tools — no LangChain, I wanted to own
> every line of the loop — and a confidence gate that decides auto-resolve versus
> human review. The gate only trusts external, measurable signals: retrieval
> similarity and classification margin. Never the model's self-reported confidence —
> models flatter themselves. Week 1 ended with a live end-to-end run: a real ticket
> asking for a feature the customer's plan didn't include went through all five
> stages, and the system correctly refused to auto-deliver the denial and routed it to
> a human, for about four cents, with every step logged. Week 2 is the evaluation
> layer: a golden set with adversarial cases, an LLM judge calibrated against human
> labels with Cohen's kappa, and a CI gate that blocks any change that regresses
> quality."

---

## Per-feature one-liners (drop these when a topic comes up)

*Grouped so you can find the right one fast. Every quote traces to a commit, a test, or
a logged run — nothing here is aspirational.*

### 🛡️ Safety & trust — the differentiator

**On the safety rule (adverse action):**
> "My safety invariant turned out to depend on model cooperation, so I made it
> structural — the gate now requires tool-call evidence before any auto-resolve, and I
> wrote the exploit as a failing test before writing the fix."

**On the gate's design:**
> "The gate never asks the model how confident it is — self-reported confidence is
> miscalibrated flattery. It uses two external signals, retrieval similarity and
> classification margin, and Week 2 calibrates the thresholds against human labels
> instead of me guessing them."

**On cost controls:**
> "Every run has a ten-cent cap that fails closed — if cost can't be computed, that
> IS a breach. And the boundary is pinned by tests, including the exactly-at-cap
> case, so the policy lives in the test suite, not in tribal knowledge."

**On observability (the glass box):**
> "Every stage writes structured spans following OTel GenAI conventions — model,
> tokens, cost, decision reasons. When someone asks 'why did the AI escalate this
> ticket?', I print the trace. The rationale the LLM gives is logged as context, but
> the trace is the evidence — I never treat the model's explanation as ground truth."

### 🤖 The agent — owning every line

**On the hand-written agent loop (why no LangChain):**
> "I wrote the agent loop by hand on the raw SDK because I wanted to answer for every
> line of it — and it paid off: a live probe showed the model issuing parallel tool
> calls, which my review then caught as an ordering bug in exactly that case. A
> framework would have hidden both the behavior and the bug."

**On the SDK-reality rule (the week's best story):**
> "Three separate times, code that passed green mocked tests was wrong against the
> real API. So I made a standing rule: no code against an API surface I haven't
> observed live — run a real probe first, commit the actual response as a test
> fixture, build mocks only from that. Reality is the spec."

### 🔬 Evals & honest numbers — the #1 hiring signal

**On judge calibration (the tool-blind judge — the flagship honest-number story):**
> "I calibrated my LLM judge against 41 of my own blind labels and got a kappa of
> 0.28 — a number most people would hide. But the disagreement report explained it:
> the judge was flagging 'you're on the Pro plan' as hallucination, and when I
> replayed those claims against the simulated CRM, seven out of seven were true —
> facts the agent got from its tools, which the judge was never shown. The grader
> wasn't wrong, it was under-informed. That finding changed my CI design: a
> kappa-0.28 judge advises, it doesn't veto. Then I fixed it — the judge now receives
> the verified account facts — and re-calibrated with a fresh labeling pass, because
> you don't grade your own fix with stale labels. The result taught me something
> better than a good number: my fresh labels disagreed with my original labels on the
> same 41 replies (self-agreement kappa 0.21) — lower than the judge's agreement with
> either of my rounds. The fixed judge beat the old judge against BOTH label rounds,
> so the improvement is real and invariant; the absolute kappa is capped by
> single-rater noise. My eval layer ended up measuring the instability of my own
> ground truth — which is why the next step is a second rater, not more judge tuning."

**On auditing my own evals (the Week-2.5 story):**
> "After my eval gate went green I ran an adversarial review of the eval layer itself,
> and it found my headline number was flattering me: 'adversarial catch rate 5/5'
> counted ANY escalation as a catch — a system that blindly escalates everything would
> score 100%. So I made the metric reason-aware: a trap only counts if the defense
> layer it was built to test actually fired. The honest split is 5/5 by design intent
> but 3/5 strict — two traps were caught by backstop layers, not their primaries. Both
> numbers are in my CI baseline now, so the strict one can only improve visibly."

**On threshold derivation (why the gate's statistics are honest):**
> "When I finally derived the gate thresholds from held-out data, the data said
> something uncomfortable: my two confidence signals carried zero reply-quality
> information — the good and bad replies' means were even slightly inverted. So I
> didn't pretend precision I didn't have: the margin threshold sits at its semantic
> zero — the embedding evidence must agree with the model's queue choice — and quality
> assurance is carried by the structural rules. The audit even caught one bad reply
> that cleared both thresholds — and it was a denial the adverse-action rule blocks
> before thresholds are consulted. Defense in depth, demonstrated on held-out data."

**On why a low kappa was still safe to ship:**
> "Eighteen of the twenty disagreements were the judge being stricter than me —
> for a triage gate that's the failure direction you want. The two lenient misses
> are the real risk, and they're why deterministic metrics carry my CI gate."

**On the CI eval gate (the Week-2 finale):**
> "My golden set re-runs automatically in CI whenever behavior-relevant code changes —
> agent code, knowledge base, schema migrations, dependencies — under a $1 hard cap
> that fails the job if exceeded. Deterministic metrics gate exactly; my LLM judge
> only advises, because I measured its agreement with me first and a kappa-0.28 judge
> hasn't earned a veto. And the trigger is path-filtered, because at a dollar per run,
> an every-merge trigger would have eaten my entire remaining budget."

### 🖥️ The glass box you can see — Week 3 (LIVE: https://triage-desk-xi.vercel.app)

**On the ops console (the glass box, now visible):**
> "Week 1 built the flight recorder — every stage writes a span. Week 3 built the
> window to look through it: a thin Next.js console where a run is a row you click into
> a per-stage table — duration, tokens, cost, the gate's signals, the draft reply, and
> the agent's rationale, captioned 'post-hoc — not evidence.' I deliberately made it a
> flat table, not a waterfall visualization — the honesty is in the data, not the
> chrome, so I cut the fancy visual and kept the build a tenth of the size. And failed
> runs are structurally impossible to hide: the list query has no state filter at all,
> so 'no hidden failures' is a property of the code, not a dashboard toggle a reviewer
> has to trust me about."

**On the review queue (where the safety rule pays off):**
> "The adverse-action rule says the agent never delivers a denial on its own — it
> routes to a human. Week 3 built the desk that promise points at: a queue of every
> escalated run, each showing the draft reply and the agent's reasoning, where an
> operator approves or rejects with a note. The verdict is persisted with a
> database-level one-verdict-per-run constraint — a second review gets a clean 409, not
> a race. And the write fails closed: if no operator token is configured, the endpoint
> returns 503, because an empty lock must never mean an open door — the same principle
> as the cost cap, one level up."

**On the live demo (drop the URL early — it changes the conversation):**
> "It's deployed and public — you can watch it triage a ticket live right now. The demo
> is guarded the way the whole system is built: visitors pick from a seeded ticket pool
> — no free-text path to the model exists, which also closes the prompt-injection front
> door — there's a per-IP rate limit, and a hard daily budget that's checked *before*
> any money is spent. When the budget runs out, the demo says so honestly and points to
> the video; I refused to silently replay cached runs, because a visitor believing they
> triggered a live run while watching a recording is deception in miniature — inside a
> project whose entire pitch is transparency."

**On the demo's best bug (concurrency on the money path):**
> "Review of the demo endpoint asked the right adversarial question: what if several
> requests arrive at once? They could all pass the budget check before any of them had
> spent anything — a classic check-then-act race, on a public endpoint that spends real
> money. I fixed it by serializing demo dispatch — one run at a time is a feature at a
> dollar a day — and the reviewer validated the regression test by removing the lock
> and watching the double-spend appear five times out of five."

### ⚙️ Process & limitations

**On process (CI/branch protection):**
> "CI gates every merge: tests, linting, and gitleaks secret-scanning. I learned the
> hard way after CI was silently red for two days — now GitHub physically refuses
> merges without green checks."

**On honest limitations (say this proactively — it builds trust):**
> "Right now nothing auto-resolves — and my metrics can finally say precisely why: not
> the thresholds (those are now derived from held-out data and reachable), but the
> model's own conservatism and my entitlement-receipt rule. My 'escalation recall 1.0'
> is real but partly a consequence of total conservatism — which is why my baseline
> also tracks the strict per-layer catch rate, the number that can't be gamed by
> escalating everything."

---

## "What I'd add in production" (deliberately cut — knowing what NOT to build)

Scope discipline was a design goal: a 4-week part-time budget and a hard $20 API
budget. Each cut is a talking point, not a gap:

- **Contract tests & nightly eval runs** — CI evals run on merge; nightly cadence
  matters at team scale, not solo scale.
- **Docker** — Windows/WSL2 friction wasn't worth it for one developer; Railway's
  Nixpacks builds from source. In production: containerize for parity.
- **Real OTel export** (Jaeger/Honeycomb) — spans already follow OTel conventions in
  Postgres; production would export to a real collector. The conventions make that a
  config change, not a rewrite.
- **CodeQL / Dependabot / pip-audit** — enterprise supply-chain scanning is
  maintenance noise on a solo portfolio repo; gitleaks covers the realistic risk
  (leaked secrets).
- **Dead-letter queue for failed runs** — failed runs are visible in the console;
  at production volume they'd need retry workflows.

---

## The numbers (live, as of Week 3 — in progress)

| Metric | Value |
|---|---|
| **Adversarial catch rate (design-intent)** | **5 / 5 = 100%** — every trap stopped by a layer designed to stop it (documented equivalence policy) |
| **Adversarial catch rate (strict, per-primary-layer)** | **3 / 5 = 0.60** — the honest diagnostic: two traps were caught by backstops, not their primary layer; regression-guarded in CI so it can only improve visibly |
| **Escalation recall** | **1.0** — nothing needing a human slipped through (precision 0.88) — real, but partly a product of total conservatism; that's exactly why the strict catch rate exists |
| Real tickets in the database | 11,922 (public Kaggle dataset, English) |
| Golden evaluation set | 25 cases (20 stratified real + 5 authored adversarial) |
| Judge calibration (v1, tool-blind) | 41 blind human labels · raw agreement 0.512 · **kappa 0.279** (stricter than human in 18/20 disagreements — fails safe) |
| Judge "hallucination" flags replayed against the CRM | 7/7 were TRUE tool-derived facts — the judge was tool-blind, so it was fixed (v2 sees the tool evidence) |
| Judge v2 (tool-evidence) vs fresh labels (round 2) | raw agreement 0.488 · **kappa 0.133** — low because the label standard moved, not the judge (see next rows) |
| Judge v2 improvement — invariant across label rounds | v2 beats v1 against BOTH labeling rounds: 0.279 → **0.418** (round-1 labels) and 0.038 → **0.133** (round-2 labels) |
| **Human self-agreement (same 41 replies, 3 days apart)** | **kappa 0.212** — lower than the judge's agreement with either round; single-rater ground truth is the measured bottleneck (next step: second rater, not judge tuning) |
| Gate thresholds | Derived from **held-out** data (never the golden set), with a leakage audit showing the layered gate fails closed |
| Knowledge-base articles authored + embedded | 15 |
| Pipeline stages, all live-verified end-to-end | 5 |
| Cost per full pipeline run | **~3.0¢** with prompt caching (hard-capped at 10¢) |
| Latency | p50 ~35s · p95 ~46s |
| CI eval gate | **GREEN on main across 6 consecutive live runs** — 25 golden cases re-run on behavior-relevant pushes, $1 in-workflow cap (~$0.90 actual/run) |
| **LIVE demo (Week 3)** | **https://triage-desk-xi.vercel.app** — Vercel console + Railway API + Neon Postgres; smoke-verified end-to-end in production (Dana's ticket: escalated, 3.6¢, exit 0); **nothing on the descope ladder was cut** |
| Ops console (Week 3) | Next.js 15 + TypeScript, **zero UI libraries** — run list + run-detail flight recorder + review queue + demo page; reads through the API only, never the DB; failed runs structurally unhideable |
| Human review queue (Week 3) | `review_decisions` table, one verdict/run **enforced by a DB constraint**; operator-token write that **fails closed** (503 when no token is configured) |
| Demo abuse protection (Week 3) | Seeded pool only (no free text = no prompt-injection front door) · 5 runs/hr/IP · **$1/day hard cap, pre-checked before spending, fail closed** · concurrency race on the cap closed by serialized dispatch, regression-proven both ways |
| Test suite | **206 unit tests** (+ integration) + lint + secret-scan, gating every merge |
| **Total API spend, entire project to date** | **~$9.6** against a hard $20 budget |

*(Week 2.5 hardening — DONE: the eval layer was adversarially reviewed and fixed;
official v2 kappa + the single-rater-noise reliability finding. Week 3 — DONE and LIVE:
runs API → console pages → review queue API+page → CORS/JSON-log deploy prep → demo
guards → Railway+Neon+Vercel deploy, smoke-verified. Next: Week 4 — demo video (#17),
case study (#18); console polish (#56) as stretch.)*

---

## Deep-dive companions (for interview prep, not for recruiters)

- [The Week 1 story, issue by issue](STORY.md) — analogies
  + Dana's journey through every stage
- [The QA hardening explainer](QA-HARDENING.md) — the
  "show your receipt" fix in full
- Design record: `docs/00-spec/DESIGN-SPEC.md`
