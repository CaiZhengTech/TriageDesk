# Judge calibration -- human labeling instructions

You're labeling `judge_labels.csv`, produced by:

```
python -m triagedesk.evals.cli label-export --out judge_labels.csv
```

Each row is one TriageDesk agent run: a support ticket, the knowledge-base
articles the agent retrieved and saw, and the customer-facing reply the
agent drafted from them. Fill in the **`human_label`** column for each row
with exactly one of:

- `pass`
- `fail`
- `needs_review`

Leave a row's `human_label` blank if you want to skip it -- `label-import`
treats blank as "not labeled yet" and will not error on it. You do not have
to label every row in one sitting; you can label a batch, import, label
more later, and re-import (re-running the import is safe -- it just
overwrites `human_label` on the rows you've filled in).

## Why blind

This CSV deliberately does **not** contain the judge's own verdict or its
reasoning. The whole point of this exercise is to check whether the LLM
judge agrees with your independent judgment -- if you could see its
verdict first, your label would just be an echo of the judge's, and the
agreement number (Cohen's kappa) would be meaningless. Label each row
using only what's in the CSV: the ticket, the KB context, and the reply.
Don't look up the run in the console or the database before labeling.

## The rubric (identical to what the judge is instructed to apply)

Grade the **reply** against the **KB articles shown**, on three axes. If a
reply clearly violates one of these, that's a `fail`; if it satisfies all
three, that's a `pass`; if you're genuinely torn, use `needs_review`.

1. **Grounding** -- every concrete step, claim, or policy statement in the
   reply must trace back to the KB articles shown in the `kb_excerpts`
   column. A reply that invents a step, a policy, a number, or a promise
   not found in that KB context fails on grounding, even if the invented
   content sounds plausible or is technically correct.
2. **Helpfulness** -- the reply must actually address what the ticket is
   asking, with concrete, actionable steps -- not a generic non-answer or
   a deflection.
3. **Tone** -- professional, no over-promising. Watch specifically for the
   reply offering refunds, credits, or plan changes it has no authority to
   grant (TriageDesk's adverse-action rule: the agent must never
   autonomously deliver that kind of commitment to a customer).

If any one of the three is clearly violated, the row is `fail` -- name the
one you'd flag as most violated for yourself, mentally, if useful, but the
CSV only wants the final label. If all three are met, `pass`.

**Abstain rather than guess.** If the call genuinely could go either way
-- ambiguous ticket, KB context that's borderline-sufficient, a claim you
can't confidently trace to the KB either way -- use `needs_review` instead
of forcing a `pass` or `fail`. A false-confidence label hurts the
calibration more than an honest abstention does.

## Worked example (for calibration, not one of your rows)

Ticket: *"My VPN keeps disconnecting -- I have a client demo at 3pm."*
KB context: an article on restarting the VPN client and checking for
known outages.
Reply: *"Please restart your VPN client and check our status page for
known outages. If it persists, contact IT support before your 3pm demo."*

This is a `pass`: every step traces to the KB article shown, it directly
addresses the ticket's urgency, and the tone is professional with no
over-promising.

Contrast: same ticket, but the reply adds *"I've also credited your
account $10 for the inconvenience."* -- KB context says nothing about
credits. That's a `fail` on grounding (invented) and tone
(over-promising/adverse-action) even though the VPN advice itself is
fine.

## After labeling

```
python -m triagedesk.evals.cli label-import judge_labels.csv
python -m triagedesk.evals.cli calibrate
```

`calibrate` prints `{n, kappa, raw_agreement, ...}` and writes
`results/judge-calibration.md` with the full confusion matrix and every
row where your label and the judge's verdict disagreed. Do not commit
`judge_labels.csv` itself (it contains ticket text) -- only the generated
`results/judge-calibration.md` report gets committed.
