# `results/` — the evidence, as standalone artifacts

Every number quoted in the [README](../README.md), the
[case study](../docs/00-spec/CASE-STUDY.md) and the [pitch](../docs/00-spec/PITCH.md)
resolves to a file in here. Nothing in this folder is hand-typed: each one is written by
a script that can be re-run, and the script is named beside it.

| Artifact | What it is |
|---|---|
| [`judge-calibration.md`](judge-calibration.md) | The full calibration record — both judge versions, both label rounds, both confusion matrices, and every judge/human disagreement with the judge's stated reason. **Start with the provenance section at the top.** |
| [`judge-vs-human-agreement.svg`](judge-vs-human-agreement.svg) | The calibration in one image. `python -m scripts.render_calibration_chart` |
| [`human-labels.csv`](human-labels.csv) | The 41 hand-applied labels, ticket text stripped. `python -m scripts.export_label_record` |
| [`human-labels-provenance.json`](human-labels-provenance.json) | Which label rounds survive and which do not — machine-readable, so the claim can't quietly rot. |
| [`null-baseline.json`](null-baseline.json) | What a one-line `return "escalate"` stub scores on the same golden set. `python -m scripts.build_null_baseline` |
| [`eval-baseline.json`](eval-baseline.json) | The CI regression floor. Read the `_note` field before treating any value as a target. |
| [`margin-separation-signals.json`](margin-separation-signals.json) | Cached per-case gate signals behind the AUC measurement that demoted the classification margin. `python -m scripts.measure_margin_separation` |
| [`LABELING-INSTRUCTIONS.md`](LABELING-INSTRUCTIONS.md) | The protocol the human labeler followed, kept so a second rater can be run consistently. |

## The one chart

![Judge-human agreement](judge-vs-human-agreement.svg)

## How to read anything in here

**Two rules, both learned the hard way.**

**Never quote a kappa without naming the judge version and the label round.** There are
four judge/human pairs and they range from 0.038 to 0.418. A single number pulled out of
that grid can be made to say almost anything; the 2×2 is the only honest summary.

**Check a metric against the null baseline before believing it.** On a golden set that is
22-of-25 expected-escalate, escalation recall of 1.00 and precision of 0.88 are reproduced
exactly by a stub that escalates everything. Those numbers measure the corpus, not the
pipeline. The reason-aware adversarial catch rate is the one a stub cannot fake — it
scores 0.00 there — which is why it is the headline.
