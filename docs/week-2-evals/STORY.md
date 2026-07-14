# The Week 2 Story, Explained (evals — issues #8–#12)

*Rolling doc — a chapter is added as each Week 2 task lands. Same three layers as the
[Week 1 story](STORY.md): **analogy** → **Dana's journey**
→ **Under the hood**. Interview one-liners live in [PITCH.md](PITCH.md).*

**Week 2's mission in one sentence:** turn "the agent seems fine" into *measured*
claims — a fixed test course, exact metrics, an AI grader we first prove agrees with
a human, and a tripwire in CI so quality can't silently regress.

---

## Prologue — the council review that reordered the week

Before building anything, we ran an adversarial review of the Week 2 plan itself.
It caught something big: we were about to build a measurement layer for a system
that — with its placeholder confidence thresholds — escalates *everything*. Measuring
a machine with one output teaches you nothing.

**The $0 diagnostic that followed became the finding of the week:** the margin
formula was verified correct by hand, but even tickets with *perfect* labels clear the
0.02 confidence bar only 2 times in 20. The bar wasn't mistuned — it was structurally
near-unreachable, because the dataset's ten queues (IT Support vs Technical Support vs
Service Outages…) overlap heavily in meaning-space. Lesson encoded into the plan:
thresholds get derived from *held-out* data later, never guessed, and never tuned on
the test set itself.

**Under the hood:** the diagnostic recomputed `classification_margin` (cosine
similarity to the LLM-chosen queue's centroid minus the best rival centroid) for the
Week-1 runs and matched the stored values, then batch-embedded 20 ground-truth-labeled
tickets in one Voyage call to get the margin distribution. Total Anthropic cost: $0.

---

## Task 1 — SDK spike: *check the ground before you build* (merged, PR #30)

**Analogy:** before pouring a foundation, you drill a soil sample. Four tiny live API
calls (~2¢) tested the exact ground Week 2 builds on — and found quicksand: asked for
a verdict as plain text, the AI answered **"poor"**, a word not on our three-label
menu. Structured outputs constrain the *shape* of an answer, not its *vocabulary* —
unless you use an enum. The corrected schema was verified live.

**Dana's journey:** none yet — this is about the grader that will eventually judge
how her replies get evaluated.

**Under the hood:** captured fixture `tests/fixtures/sdk_structured_output_caching.json`
holds the judge's structured-output call shape at `temperature=0` (deterministic
grading), the failed plain-`str` shape as a documented trap, and prompt-cache usage
fields (2,343 tokens written to cache on call one, read back on call two). All Week 2
mocks build from this observed reality — the project's SDK-reality rule, now on its
fourth save.

## Task 2 — Prompt caching: *the thermos* (merged, PR #31)

**Analogy:** our AI calls keep re-sending the same instructions and tool menus every
time — like re-boiling the kettle for every cup. Caching puts the stable part in a
thermos: the API stores it once (small write fee), then every repeat call reads it
back at ~a tenth of the price. Eval suites re-run the same 25 cases over and over —
this is why caching had to land *before* the first suite run.

**Under the hood:** `cache_control: {"type": "ephemeral"}` breakpoints on the act
loop's system prompt and the last tool definition, and on `structured_call`'s system
block — stable prefixes only; per-ticket content is never cached (each ticket differs,
caching it would be a useless write). Cache-write tokens bill at $3.75/MTok,
cache-read at $0.30/MTok vs $3.00 for fresh input; cost accounting already handled
both (asserted by test, not assumed). Review verdict: zero findings.

## Task 3 — The golden set: *bolting down the driving course* (merged, PR #32, closes #8)

**Analogy:** a driving test only means something if the course never changes. This
task laid out 25 fixed scenarios: 20 real tickets picked reproducibly across all ten
queues, plus 5 trick sections designed to tempt specific failures — a graffitied stop
sign (prompt injection buried in a ticket), a request to leak personal data (PII
bait), a ticket that isn't a support ticket at all, an unresolvable mumble, and the
crown jewel: a scenario engineered to tempt the agent into slipping a denial into a
"solved" reply without checking entitlements — aimed squarely at the guardrail from
issue #28.

**Dana's journey:** Dana is all over this course. Her real VPN ticket is one of the
representative cases — and the soft-denial trap is *backed by her account*: basic
plan, priority VPN support requested, genuinely not covered. If the agent takes the
bait, the gate must catch it; that catch (or miss) becomes a headline number.

**The honest-ground-truth decision:** 4 of the 25 cases are labeled with the ideal
outcome "resolve automatically" even though today's thresholds guarantee they'll fail.
That's deliberate — expected outcomes describe what a competent human triager says
*should* happen, not what the current config does. A test you tune until it passes
measures nothing; an honestly red first run is the measurement.

**The review save:** adversarial tickets originally got random database IDs — and the
ID silently decides which fake customer backs the ticket (`id % 12`). The trap landed
on an enterprise customer who was *legitimately entitled* to the request: the trap
tested nothing, and would re-roll meaning on every reseed. Fixed by pinning reserved
IDs with the account mapping documented and regression-tested, and making seeding
idempotent (re-runs converge instead of accumulating orphans).

**Under the hood:** Alembic migration adds `eval_cases` (the 25 scenarios + expected
outcome/queue + notes) and `eval_results` (per-case outcomes per eval run — CI
history). `scripts/build_golden_set.py` selects with a seeded RNG over *sorted* ticket
ids (Postgres row order isn't deterministic — sorting first is what makes the seed
reproducible), and delete-then-reinserts the pinned adversarial ids (90000-range,
safely above the ~12k dataset). 69 tests green; $0 API spend.

## Task 4 — The harness: *the examiner with the clipboard* (merged, PR #33, closes #9)

**Analogy:** Task 3 built the driving course; this built the **examiner**. It drives all
25 scenarios, times each one, prices it, and writes down not just pass/fail but *why* at
every checkpoint. Then it scores the whole exam: how often was the ticket routed to the
right queue? Did anything that needed a human slip through? Were all five traps caught?

**The first exam happened — and these are the project's first real numbers:**

| Metric | Result |
|---|---|
| **Adversarial catch rate** | **5/5 = 100%** — every trap caught by its intended defense |
| Escalation recall | **1.0** — nothing that needed a human slipped past |
| Escalation precision | 0.88 |
| Cost per case | **2.9¢** (caching working); whole suite $0.73 |
| Latency | p50 31s · p95 41s |
| Routing accuracy | 29% — *see below; this is a finding, not a failure* |

**Dana's journey:** her VPN ticket ran as case #1. Screened, sorted, briefed, worked — the
agent checked her entitlements, found priority VPN support isn't on her basic plan, and the
gate escalated it as an adverse action. Exactly right. The examiner recorded all of it,
including the 3.6¢ it cost.

**Two findings only a real run could produce:**
1. **The confidence threshold wasn't the villain.** Of the four cases that *should* have
   auto-resolved, **zero** were blocked by the confidence bars. Two were blocked by the
   entitlement-receipt rule, one by the model asking for a human on its own — and one turned
   out to be **an error in our own answer key** (Dana's ticket was labeled "should
   auto-resolve," but it contains a denial, so it *can't* be — fixed).
2. **The 29% routing accuracy is about the dataset, not the agent.** The queue labels
   overlap so heavily in meaning ("IT Support" vs "Technical Support" vs "Service Outages")
   that even a perfect classifier scores badly against them. Honest number, reported as-is.

**Also on record:** the very first live attempt **crashed** — a timezone mismatch (the
database writes naive timestamps, Python wrote timezone-aware ones) that green mocked tests
could never have caught. Fixed with a regression test. That's the sixth "reality beats
mocks" save.

**Under the hood:** all metric math (precision/recall, percentiles, calibration buckets) is
pure functions, unit-tested with fakes — $0 to test. Only the suite *run* costs money, and
it's a deliberate, counted event with a hard $1 cap. Per-case gate reasons are persisted to
`eval_results`, which is what made the diagnostic above possible.

## Task 5 — The judge: *the second grader* (merged, PR #36 + #37, closes #10)

**Analogy:** the examiner (#9) is a **scantron machine** — it grades the questions that have
one right answer. But "is this reply to the customer actually any good?" has no answer key.
So we hired a **second grader**: an AI with a strict rubric — is every claim in the reply
*grounded* in the KB articles the agent was given, is it helpful, is the tone right? It's
allowed to say **"I'm not sure"** rather than guess, and its opinion is stamped throughout
the code as a *debugging aid, never ground truth* — it never feeds back into the agent's
decisions.

**First verdicts on 19 drafted replies:** **9 pass · 5 fail · 5 needs_review** — real
variance, and it used its abstain option instead of forcing calls.

**The bug this task is really about:** the judge was wired to grade only runs that finished
`completed` — but this system, by design, escalates almost everything. So the judge was
**dead code that would never have fired once**, and the calibration in Task 6 would have
opened to an empty file. Only a live run could reveal it. The fix is a genuine conceptual
correction: **reply quality is independent of the gate's send decision.** An escalated
ticket's drafted reply is exactly what a human reviewer reads, so it must be judged.

**Under the hood:** pinned `claude-sonnet-4-6` at `temperature=0` (deterministic grading),
verdict constrained to an **enum** (`pass|fail|needs_review`) because the SDK spike proved an
unconstrained field lets the model invent labels like "poor". The judge reconstructs *exactly*
the KB articles the agent saw by reading the retrieve span's recorded doc slugs. Two review
catches landed too: the harness was silently counting an *uncomputable* cost as $0 (a
fail-closed violation the moment the judge went live), and `judge_run` would have rendered the
literal string "None" into its prompt if handed a run with no reply. Both fixed, both tested.
A **backfill command** means re-judging costs 15¢ instead of re-running the pipeline for $0.75.

## Task 6 — Calibration: *does a human actually agree with the judge?* (✅ closed — PRs #38/#39 + calibration run, issue #11)

**Analogy:** we now have an AI grading the agent's work. But **who grades the grader?** Before
CI is ever allowed to trust this judge, it has to prove it agrees with a human. So: Cai labels
the same replies **blind** — he never sees the judge's verdicts — and we compute **Cohen's
kappa**, the standard measure of agreement between two raters that *corrects for luck* (two
raters who both say "pass" 90% of the time will agree often by pure chance; kappa strips that
out).

**The hold-out twist:** the judge is calibrated on a **separate pool of 25 non-golden
tickets**, not the tickets it's graded on. Same principle as the golden set: the thing you
measure with must not be the thing you tuned on. Total: **41 blind rows** (19 golden + 22
pool).

**The deliverable nobody expects:** not just the kappa number, but the **disagreement
analysis** — every case where the human and the judge diverged, with the judge's reasoning.
"Here's where my LLM judge disagreed with me, and why" is the artifact almost no new-grad
portfolio has.

**Under the hood:** hand-rolled kappa (no scipy — it's 15 lines of math). The exported CSV is
verified by test to contain **no** judge verdict or reasoning — blindness is what makes the
number honest. And the implementer **overrode the plan's own formula**: the plan said to return
"perfect agreement" (1.0) in the degenerate case where both raters use only one label — but
that's mathematically **0/0, undefined**, and reporting 1.0 would have shipped a false claim of
perfect calibration. It now returns "undefined" with a reason. *The eval layer caught an error
in its own specification.*

**The verdict (labels landed 2026-07-14):** Cai blind-labeled all 41 rows. Agreement:
**kappa 0.279** — the human and the judge agree only "fairly," well below what you'd need to
let the judge grade unsupervised. A weaker project would bury that number. Here it's the
week's best finding, because the disagreement report explains it.

**The analogy:** imagine grading an open-book exam — but you were only handed the *textbook*,
while the student also got to interview the customer's account manager. Every fact the student
learned from that interview looks made-up to you. That's exactly what happened: the judge
grades replies against the KB articles only, but the agent also has **tools** — it can look up
a customer's real plan and account status in the (simulated) CRM. So when the agent wrote
"your account is currently suspended," the judge ruled it a hallucination. We checked the CRM:
**that customer's account really is suspended.** Seven out of seven "invented" facts the judge
flagged were true, tool-derived facts. The agent was right; the grader lacked the evidence.

**Dana's journey:** when Dana asks for a dedicated IP and the agent replies "your Pro plan
doesn't include that," the judge — seeing only the VPN troubleshooting articles — would cry
"where did 'Pro plan' come from?!" It came from `check_entitlement`, the same tool-call receipt
the confidence gate already demands. The grader just was never shown the receipt.

**Why this is good news, carefully stated:** 18 of the 20 disagreements are the judge being
*stricter* than the human — the safe direction (a paranoid grader fails closed). Only 2 rows
went the other way. And the fix is mechanical — show the judge the tool outputs — but it's
deliberately *not* rushed in mid-week, because changing the grader invalidates the calibration
you just paid a human afternoon for. Instead the number feeds Task 7's design directly: **a
kappa-0.279 judge advises, it does not veto.** The CI gate leans on deterministic metrics
(adversarial catch, escalation recall); judge metrics get a tolerance band.

**Under the hood (results):** raw agreement 0.512; confusion matrix and all 20 disagreement
rows with the judge's verbatim reasoning live in `results/judge-calibration.md`. Root-cause
verification: for every disagreement where the judge cited a plan/status claim, the claim was
replayed against the simulated CRM (`lookup_account_status`) and matched — full table in the
task-6 report.

---

## Task 7 — The CI eval gate: *regressions can't sneak in anymore* (✅ closed — PR #42, issue #12, KILL CRITERION MET)

**Analogy:** every building has a fire alarm, but a fire alarm you never test is just a
decoration. This task wired the whole evaluation layer — golden set, metrics, cost caps —
into a **tripwire that re-runs automatically**: whenever code that could change the agent's
behavior is pushed to `main`, GitHub re-runs all 25 golden cases and compares the numbers
against a committed baseline. If any number regresses, the push goes red. The quality bar is
no longer a document — it's a machine that says no.

**Dana's journey:** suppose a future change subtly breaks the entitlement check, and Dana's
dedicated-IP denial would now slip out automatically instead of routing to a human. Before
this task, we'd find out when a real Dana complained. Now: the push re-runs the golden set,
the soft-denial trap catches it, `adversarial_catch_rate` drops below 1.00, and the merge
goes red before Dana ever sees a reply.

**The two design decisions that made it affordable and honest:**
1. **It doesn't run on every merge.** Each gate run costs real money (~$0.72). A council
   amendment scoped the trigger to *eval-relevant files only* (agent code, KB, migrations,
   dependencies, the baseline itself) plus a manual button — so Week 3's console and docs
   work won't burn a dollar per merge.
2. **The judge advises, it does not veto.** Fresh from Task 6: a kappa-0.279 judge has no
   business failing anyone's build. The gate is carried entirely by deterministic metrics
   (adversarial catch, escalation recall, cost caps); the baseline explicitly labels itself
   a *regression floor on current observed behavior, not a quality target*, to be re-derived
   after the threshold work the council will schedule.

**The proof:** one deliberate, counted live run (**$0.72, under the $1 in-workflow cap**)
went green on `main`: adversarial catch 1.00, escalation recall 1.00, precision 0.88,
2.9¢/run. The reviewer also caught a real hole before merge — schema migrations
(`alembic/**`) weren't in the trigger's path filter, meaning a database change could have
dodged the gate entirely. Fixed pre-merge. The "does it actually fail on a breach?" path is
pinned by unit tests that prove the gate exits non-zero on any floor, ceiling, or band
violation.

**Week 2 is complete.** The kill criterion — *eval gate green by end of Week 2, or the
Week-3 console gets cut* — is **met**, with the gate green on the first live run.

---

*Next: Cai's end-of-Week-2 checkpoint (llm-council), then Week 3 — the glass-box console.*
