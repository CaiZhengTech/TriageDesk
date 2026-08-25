# The pre-check fires for the first time (#80, #81)

**What changed:** `POST /api/tickets` shipped, and tickets began arriving from outside
the system instead of being launched by a human clicking Run in the console.

**Why it mattered immediately:** the pre-check stage — the injection/PII screen that is
stage one of the pipeline — had **never run against untrusted input**. Verified before
the change: 0 of 13 production runs stopped at pre-check, because there was no path by
which untrusted text could enter.

---

## The adversarial batch

13 payloads: 4 injection, 3 PII/exfiltration, 3 off-topic, and **3 controls** — legitimate
tickets that superficially resemble attacks. The controls matter as much as the attacks:
a screen that catches injections by flagging angry customers is not deployable.

| Expected | Observed reason | Cost | Verdict |
|---|---|---|---|
| injection ×4 | `precheck_injection` | $0.0021 | **caught, right layer** |
| pii ×3 | `precheck_pii` | $0.0021 | **caught, right layer** |
| off_topic ×3 | `precheck_off_topic` | $0.0021 | **caught, right layer** |
| **SAFE** — "Frustrated, third time asking" | `agent_requested_human` | $0.0429 | passed the screen |
| **SAFE** — "Need my own account details" | *(auto-resolved)* | $0.0310 | passed the screen |
| **SAFE** — "Password reset not arriving" | `agent_requested_human` | $0.0335 | passed the screen |

**10/10 true positives, each stopped by the layer built for it. 0/3 false positives.**

Not "escalated for some reason" — matched to the intended defence layer, which is the
distinction the reason-aware catch-rate metric exists to enforce.

The `SAFE` control that **auto-resolved** is worth noting on its own: a genuine ticket,
arriving unattended from outside the system, answered end to end with no human. That is
the premise working on input nobody curated.

---

## The cost asymmetry

| Outcome | n | avg cost |
|---|---|---|
| Stopped at pre-check | 15 | **$0.0021** |
| Auto-resolved | 3 | **$0.0332** |

**Rejecting an attack costs ~6% of serving a customer.** That is a design consequence,
not luck: `execute_run` calls `run_precheck` first and returns immediately on an unsafe
verdict, so a caught payload pays for one 256-token structured call and never reaches
retrieval or the act loop — the stages that hold 91% of the cost.

Safety being nearly free is what makes running it on every ticket defensible.

---

## What real traffic broke, within minutes

The clean batch of 12 real Kaggle tickets produced **4 failures**, all at `retrieve`:

```
RateLimitError: ... reduced rate limits of 3 RPM and 10K TPM
```

Two defects, neither visible before tickets arrived:

1. **No retry on the embedding path.** The stated policy — *"retries: 429/5xx, backoff,
   max 3"* — was implemented for Anthropic (`Anthropic(max_retries=3)`) and not for
   Voyage, whose client was constructed bare. One provider hardened, one forgotten.
2. **The failure was labelled `unexpected:RateLimitError`.** The runner caught
   `anthropic.APIError`; Voyage raises its own hierarchy. A provider rate limit is the
   most *expected* failure a hosted pipeline has, and the trace is this project's
   product — a reason that sends the reader hunting for a nonexistent bug is a defect.

Both fixed in #81 (retry with 5s/20s/45s backoff tuned to the 3 RPM ceiling; both
providers' error hierarchies caught together).

**This is the argument for the intake path in one incident.** The gap existed for four
weeks. It was invisible to 323 passing tests. It surfaced within minutes of tickets
arriving unattended, because concurrency is a property of arrival, and nothing about a
click-to-run demo produces it.

---

## An unplanned finding: the screen acts as a domain filter

5 of the 12 real Kaggle tickets were caught as `precheck_off_topic` — "Boost Digital
Marketing Content Production", "Enhancing Firm's Investment Portfolio Management",
"Inquiry About Data Analytics Solutions", "Strategies for Enhancing Smart-Smoke-Alarm
Sales".

Read against this system's actual scope — an IT support desk whose 15 KB articles cover
VPN, passwords, billing, API keys and outages — those genuinely are out of domain. The
screen is doing something its prompt describes ("clearly not a customer support request")
but that was designed with prompt injection in mind, not corpus mismatch.

It is the same finding as the 0.286 routing accuracy seen from a different angle: **the
Kaggle corpus is not the support desk this KB was written for.** Whether treating them as
`off_topic` is right depends on a product decision — reject, or route to a sales queue —
that this project has not made and should not pretend to have made.

---

## Production state after

| | before | after |
|---|---|---|
| Runs | 13 | **39** |
| Pre-check trips | **0** | **15** |
| Terminal states seen | 3 | 4 outcome types, 10 distinct reasons |
| Total spend | $0.44 | $0.76 |

The console now shows genuinely inbound traffic — attacks stopped at the door, real
tickets resolved or escalated, and failures visible rather than hidden.
