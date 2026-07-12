# Week 1 QA Hardening, Explained (PR #29 / issue #28)

*Written for Cai — plain language first, so you can retell any part of this to a
non-technical recruiter. Each section has: the story, the analogy, and the one-liner
you can say in an interview.*

---

## The 30-second version (memorize this one)

> "After finishing week one of my AI ticket-triage system, I ran an adversarial review
> against my own work before moving on. It found that my most important safety rule —
> 'the AI never delivers bad news to a customer on its own' — was being obeyed, but not
> actually *enforced*. The AI happened to behave; nothing forced it to. So I changed the
> system so the rule physically can't be broken: no answer goes out automatically unless
> the AI can show a receipt proving it did the required check. I test-drove the loophole
> first, watched it get caught, then closed it."

That's the whole story. Everything below is detail.

---

## 1. The big fix: from "trust" to "structure"

### What TriageDesk does (context for a recruiter)
TriageDesk is an AI agent that reads customer support tickets and either resolves them
automatically or hands them to a human. The whole point of the project is the **trust
machinery** around the AI — proving when it should and shouldn't be allowed to act alone.

The running example is **Dana**: she files a ticket saying her VPN keeps disconnecting
before a 3pm client demo, and asks to have "priority VPN support" turned on. Her plan
doesn't include that feature — so the right answer contains a **denial**, and the
project's #1 rule says: *the AI never delivers a denial by itself; a human always
reviews it first.*

### The hole
The system's "gate" (the final checkpoint before an answer auto-sends) recognized a
denial in exactly two ways: the AI labels its own answer "deny," or the AI runs the
plan-coverage check and gets "not covered." Spot the problem? **Both signals come from
the AI cooperating.** An answer that says *"unfortunately your plan doesn't include
this"* — but is labeled "solved," with the coverage check never run — looked like a
success and would have auto-sent.

**Analogy:** a bouncer who only cards people who volunteer that they're underage.
Our two live tests passed because the guests happened to volunteer. That's good
behavior, not security.

### The fix
The gate now requires **positive evidence**: unless the AI actually executed the
`check_entitlement` tool (the "did this customer pay for this?" lookup) during its
work, nothing auto-sends — the ticket escalates to a human, stamped
`no_entitlement_evidence`. The receipt requirement lives in code the AI cannot argue
with.

**How we proved it works (this is the part interviewers care about):**
1. First we wrote a test that *plays the attacker*: a fake "solved" answer hiding a
   soft denial, with no coverage check run, and confidence scores good enough to sail
   through.
2. Ran it against the old gate → the test **failed** (the bad answer got through).
   That failure is the evidence the hole was real.
3. Wrote the fix, ran it again → the bad answer now gets caught and escalated.
This is called **test-driven development**: prove the disease exists before claiming
the cure works.

**Honest trade-off (say this too — it shows judgment):** the gate is now *stricter* —
even a ticket with no money-question involved escalates if the check wasn't run. That
means fewer automatic resolutions for now. That's deliberate: this system fails
**closed** (when unsure, ask a human), and Week 2's measurement work will tell us
exactly how much automation this costs and whether to refine it. Safety first, tune
with data second.

### Interview one-liner
> "I found that my safety invariant depended on model cooperation, so I made it
> structural — the gate now requires tool-call evidence before any auto-resolve, and I
> wrote the exploit as a failing test before writing the fix."

---

## 2. The money safety net

Every AI call costs real money, and the project has a hard rule: **if we can't compute
what a call cost, treat it as overspending and stop.** (Fail closed, again.)

There was a crack: a malformed API response would crash with a generic error instead
of triggering the budget rule — like a cash register that, when handed a smudged price
tag, throws its hands up instead of calling the manager. Now it calls the manager: the
proper `CostUnknownError` fires and the run escalates as a budget breach.

We also added tests for the odd edges: a call that used zero tokens, a call served
entirely from cache, and a bill that lands *exactly* on the spending cap (deliberately
allowed — the rule is "over the cap," not "at the cap," and now there's a test pinning
that decision so nobody "fixes" it by accident).

### Interview one-liner
> "My cost controls fail closed — and I test the boundaries, including the
> exactly-at-cap case, so the policy is pinned by tests, not tribal knowledge."

---

## 3. The metal detector in CI

Every time code is pushed to GitHub, an automated pipeline ("CI") runs the test suite.
This batch added **gitleaks** — a scanner that checks every commit for accidentally
pasted passwords or API keys — inside that same pipeline, so no code can merge without
passing it. Think of it as a metal detector at the door of the repository. The first
scan of the project's entire history came back clean.

Also added: if you push twice quickly, the pipeline now cancels the outdated run
instead of wasting compute on both.

**What we deliberately did NOT add** (and why that's a flex, not a gap): heavyweight
enterprise scanners (CodeQL, Dependabot). For a solo four-week project they're
maintenance noise with no payoff — knowing what *not* to build is part of the
engineering story, and they're listed in the case study as "what I'd add in
production."

### Interview one-liner
> "CI gates every merge: tests, linting, and secret-scanning. I scoped it deliberately
> — the checks that pay for themselves on a solo project, nothing performative."

---

## 4. Filling the empty guard posts (test gaps)

Several behaviors worked but had **no test standing guard** over them — like fire
exits that exist but were never inspected. Each got an inspection:

- The AI pausing mid-task (`pause_turn`) → the loop correctly continues.
- The AI itself saying "a human should handle this" → correctly escalates end-to-end.
- The unknown-cost error → correctly maps to a budget escalation (not a generic crash).
- The safety-screening stage's *reason* for flagging a ticket is now written into the
  trace — so when a human reviews a flagged ticket, the "why" is right there in the
  evidence, not lost.

Plus small polish: a Windows text-encoding call moved to the proper place, a CSV
opened the way Python's own docs say to, and one knowledge-base doc's arrows made
consistent with the other fourteen.

---

## 5. How this connects to everything before and after

- **Issues #1–#6** built the machine: database, tracing, the AI pipeline stages.
- **Issue #7** proved the machine runs end-to-end: Dana's real ticket went through all
  five stages live, and the denial correctly went to a human — Week 1's pass/fail
  criterion.
- **This batch (#28/PR #29)** came from *attacking our own finished work* — an
  adversarial "council" review — and upgraded the headline safety rule from
  "observed to hold" to "structurally cannot be broken."
- **Week 2** builds the measurement layer (a golden set of test tickets, an AI judge
  calibrated against human labels) — and it will include a test case that *tries the
  soft-denial trick on purpose*, turning this fix into a measurable, demonstrable
  result instead of just a story.

**The meta-story for recruiters:** three times in Week 1, something that *looked*
correct under simulated tests turned out to be wrong against reality (twice with the
AI provider's API, once with this gate rule). Each time, the response was the same:
verify against reality first, capture the evidence, encode the lesson as a permanent
rule. That habit — not the AI itself — is the product.

---

*Technical record: PR #29, merged to `main` as `627f778`. Five commits: gate
entitlement-evidence rule (TDD), cost fail-closed typing + boundary tests, test-gap
minors + polish, CI gitleaks + concurrency, plan reconciliation note. 57 tests + ruff
green; $0 API spend for the whole batch.*
