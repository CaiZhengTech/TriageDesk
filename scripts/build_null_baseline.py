"""Emit results/null-baseline.json — what a trivial stub scores (#68).

  python -m scripts.build_null_baseline          # write the artifact
  python -m scripts.build_null_baseline --print  # show it, write nothing

$0 and offline: pure arithmetic over the committed golden set. No API, no
database. Re-run after any change to the golden set or a metric definition —
`tests/unit/test_null_baseline.py` fails if the committed artifact drifts from
what the code derives.
"""

import argparse
import json
from pathlib import Path

from triagedesk.evals.null_baseline import COLLAPSING_METRICS, null_baseline

OUT = Path("results/null-baseline.json")

_NOTE = (
    "What a one-line `def triage(ticket): return \"escalate\"` stub scores on the "
    "current golden set. Published so no headline metric is quoted without the "
    "trivial baseline beside it. DERIVED by running synthetic stub results through "
    "the real triagedesk.evals.metrics.summarize() — never hand-written, so it "
    "cannot drift when the golden set or a metric definition changes. Regenerate "
    "with `python -m scripts.build_null_baseline`; the unit tests fail if this "
    "file and the code disagree."
)

_COLLAPSING_NOTE = (
    "Metrics the stub reproduces. On a corpus that is 22/25 expected-escalate, "
    "these measure the base rate rather than the pipeline, and must never be "
    "published as standalone evidence."
)

_DISTINGUISHING_NOTE = (
    "Metrics the stub scores ZERO on, and which therefore carry real signal. "
    "adversarial_catch_rate is reason-aware (triagedesk/evals/metrics.py::"
    "_caught_by_intended_layer): a case counts as caught only when the observed "
    "escalation_reason matches the layer meant to catch it. A stub has no reason "
    "to report, so it cannot score here at all — this is the Week-2.5 hardening "
    "closing the tautology-of-conservatism, working as designed."
)


def main() -> None:
    ap = argparse.ArgumentParser(prog="build_null_baseline")
    ap.add_argument("--print", dest="show", action="store_true",
                    help="print the baseline without writing the file")
    args = ap.parse_args()

    baseline = null_baseline()
    comparable = {
        k: v for k, v in baseline.items()
        if isinstance(v, int | float) and k != "n_cases"
        and not k.startswith(("cost_", "latency_", "judge_"))
    }
    distinguishing = sorted(k for k in comparable if k not in COLLAPSING_METRICS)

    payload = {
        "_note": _NOTE,
        "_collapsing_note": _COLLAPSING_NOTE,
        "_distinguishing_note": _DISTINGUISHING_NOTE,
        "n_cases": baseline["n_cases"],
        "golden_set_balance": {
            "expected_escalate": sum(
                1 for r in _outcomes() if r == "escalate"),
            "expected_route": sum(1 for r in _outcomes() if r == "route"),
        },
        "null_baseline": comparable,
        "collapsing_metrics": list(COLLAPSING_METRICS),
        "distinguishing_metrics": distinguishing,
    }

    text = json.dumps(payload, indent=2) + "\n"
    if args.show:
        print(text)
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT}")
    print(f"  collapses to the stub : {', '.join(COLLAPSING_METRICS)}")
    print(f"  carries real signal   : {', '.join(distinguishing)}")


def _outcomes() -> list[str]:
    from triagedesk.evals.null_baseline import stub_results
    return [c.expected_outcome for c in stub_results()]


if __name__ == "__main__":
    main()
