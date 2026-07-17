# Gate threshold re-derivation (Hardening Task 3, Refs #45)

**What this is:** the derivation record for `SIM_THRESHOLD` and `MARGIN_THRESHOLD` in
`triagedesk/pipeline/gate.py`, replacing the Week-1 placeholder values (0.45 / 0.02) that
the 2026-07-14 llm-council flagged: the 0.02 margin threshold was hand-verified to be
structurally near-unreachable, and neither value had ever been derived from data.

**Hold-out rule compliance (binding):** every number below comes from the **25-ticket
calibration pool** (`eval_cases.kind = 'calibration'`, suite run `3231c41d`) — tickets
deliberately disjoint from the golden 25 — plus Cai's 2026-07-14 human labels on those
replies. The golden set appears only in the "expected impact" section, as a *consequence
check*, never as an input to the derivation.

## The data (22 held-out rows with signals + human labels)

3 of the 25 pool rows were stopped at precheck (no gate signals, no reply to label);
the remaining 22 carry `retrieval_similarity`, `classification_margin`, and a blind
human label on reply quality.

| Human label | n | mean similarity | mean margin |
|---|---|---|---|
| pass | 10 | 0.472 | −0.0099 |
| fail | 10 | 0.492 | −0.0082 |
| needs_review | 2 | 0.503 | −0.0050 |

### Finding 1 — the signals do not separate good replies from bad ones

The means are not just close — they are *directionally inverted* (human-fail replies have
slightly HIGHER similarity and margin than human-pass replies). On this sample the gate
signals carry no reply-quality information. **Consequence, stated honestly: the thresholds
cannot carry quality assurance.** The binding safety layers are — and remain, by design —
the adverse-action rule, the entitlement-receipt rule, and the model's own
`needs_human` conservatism. The thresholds' actual job is narrower: refuse to auto-resolve
when the *classification/retrieval evidence* is weak, as a defense-in-depth backstop.

### Finding 2 — 0.02 margin is unreachable on held-out data too

The margin is `(centroid similarity of the LLM-predicted queue) − (best other centroid)`.
Distribution on the 22 held-out rows: 18/22 negative, range −0.0267 to +0.0290.

| Margin threshold | Held-out rows clearing it |
|---|---|
| ≥ 0.02 (old) | **1/22 (5%)** |
| ≥ 0.00 (new) | 4/22 (18%) |

The old 0.02 was a Week-1 guess that demands the embedding evidence *strongly* out-vote
every alternative queue — which the 10-queue taxonomy's embedding overlap (the documented
29%-routing-accuracy finding) almost never permits. It made `low_confidence` a dead layer
and auto-resolve structurally impossible, which in turn made "escalation recall 1.0" a
tautology (the council's core complaint).

## The derived values

### `MARGIN_THRESHOLD = 0.0` (was 0.02)

0.0 is the **semantic zero** of this signal, not a tuned number: margin ≥ 0 means "the
embedding-centroid evidence *agrees* with the LLM's queue choice"; margin < 0 means the
embedding evidence contradicts it. Requiring agreement-but-not-a-margin-of-victory is the
weakest defensible requirement that keeps the signal meaningful — and since Finding 1
shows the signal carries no quality information beyond that, any stricter value would be
pseudo-precision (0.02 vs 0.03 could not be defended with data).

### `SIM_THRESHOLD = 0.45` (unchanged — but now grounded)

0.45 sits at the ~36th percentile of held-out retrieval similarity (8/22 rows below it):
it excludes the bottom third of retrieval quality while leaving the majority eligible.
The value survives re-derivation; what changes is its provenance — it is now anchored to
the held-out distribution instead of a Week-1 guess. (No alternative value is better
supported: Finding 1 applies to similarity too.)

## Leakage check (the fail-closed audit)

Rows clearing BOTH new thresholds: **3/22 (14%)** — one human-**pass**, one
human-**needs_review**, one human-**fail**.

The layered gate disposes of all three correctly:

| Row (case) | Human label | What still blocks auto-resolve |
|---|---|---|
| 59 (149) | pass | model asked for a human (`agent_requested_human`) |
| 63 (153) | needs_review | model asked for a human (`agent_requested_human`) |
| 57 (147) | **fail** | **`adverse_action` — the reply is a denial; the rule fires BEFORE thresholds and cannot be out-voted by them** |

The one bad reply that clears the thresholds is exactly the case the adverse-action rule
exists for — held-out evidence that the layered design fails closed even when the
statistical layer is blind.

## Expected impact on the golden suite (consequence check, not an input)

- Of the 3 ideal-auto-resolve golden cases, case 129 now clears both thresholds
  (sim 0.702, margin +0.0461); its remaining blockers are the entitlement-receipt rule
  and model conservatism — i.e. auto-resolve is now *reachable* and gated by the safety
  layers, not by an unreachable statistic.
- The `ambiguous` adversarial trap (margin −0.0465) still fails the margin threshold, so
  `low_confidence` — its intended defense layer — remains reachable for it.
- No expected-escalate golden case was threshold-blocked before (they all escalate at
  earlier layers), so escalation recall is not loosened by this change *for recorded
  behavior*; the Task 3 live run re-measures it rather than assuming it.

## What was changed in code

- `triagedesk/pipeline/gate.py`: `MARGIN_THRESHOLD` 0.02 → 0.0; comment now points here
  instead of at "Week-2's calibration".
- `tests/unit/test_gate.py`: the boundary test that asserted margin 0.0 →
  `low_confidence` under the old threshold now asserts margin −0.01 → `low_confidence`
  and margin 0.0 → pass (the new boundary), updated deliberately with this derivation.
