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

---

*Next chapters as they land: Task 4 (deterministic harness + calibration table),
Task 5 (LLM judge), Task 6 (human labels + Cohen's kappa), Task 7 (CI eval gate —
the Week 2 kill criterion).*
