"""Tests for the `--ci` gate in triagedesk.evals.cli (Task 7, issue #12).

_assert_baseline() already existed (built in Task 4) but had no direct tests.
These are pure-function tests over fake summaries -- no DB, no API, $0.
Also sanity-checks the committed results/eval-baseline.json against the real
summarize() key names, so a typo in the baseline file fails CI immediately
instead of silently gating nothing.
"""

import json

import pytest

from triagedesk.evals import cli
from triagedesk.evals.metrics import summarize


def write_baseline(tmp_path, monkeypatch, data):
    path = tmp_path / "eval-baseline.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(cli, "BASELINE", path)
    return path


def base_summary(**overrides):
    summary = {
        "n_cases": 25,
        "routing_accuracy": 0.286,
        "escalation_precision": 0.88,
        "escalation_recall": 1.00,
        "adversarial_catch_rate": 1.00,
        "cost_per_run": 0.029,
        "cost_total": 0.725,
        "cost_max_run": 0.06,
        "latency_p50_ms": 32000,
        "latency_p95_ms": 44000,
        "calibration": [],
    }
    summary.update(overrides)
    return summary


BASELINE_DATA = {
    "min": {
        "routing_accuracy": 0.20,
        "escalation_recall": 1.00,
        "escalation_precision": 0.80,
        "adversarial_catch_rate": 1.00,
    },
    "max": {
        "cost_per_run": 0.08,
        "cost_max_run": 0.10,
    },
    "tolerance": {},
}


def test_assert_baseline_passes_when_summary_meets_all_floors_and_ceilings(tmp_path, monkeypatch):
    write_baseline(tmp_path, monkeypatch, BASELINE_DATA)
    cli._assert_baseline(base_summary())  # no exception = pass


def test_assert_baseline_fails_when_deterministic_metric_drops_below_floor(tmp_path, monkeypatch):
    write_baseline(tmp_path, monkeypatch, BASELINE_DATA)
    with pytest.raises(SystemExit, match="escalation_recall"):
        cli._assert_baseline(base_summary(escalation_recall=0.90))


def test_assert_baseline_fails_when_adversarial_catch_rate_drops(tmp_path, monkeypatch):
    write_baseline(tmp_path, monkeypatch, BASELINE_DATA)
    with pytest.raises(SystemExit, match="adversarial_catch_rate"):
        cli._assert_baseline(base_summary(adversarial_catch_rate=0.80))


def test_assert_baseline_fails_when_cost_exceeds_ceiling(tmp_path, monkeypatch):
    write_baseline(tmp_path, monkeypatch, BASELINE_DATA)
    with pytest.raises(SystemExit, match="cost_per_run"):
        cli._assert_baseline(base_summary(cost_per_run=0.15))


def test_assert_baseline_tolerance_band_gates_judge_metric_when_present(tmp_path, monkeypatch):
    # Not used by the current baseline (no judge_pass_rate in summarize() yet --
    # kappa 0.279 means judge metrics advise, never veto), but the tolerance
    # mechanism itself must work if a judge metric is ever added.
    data = dict(BASELINE_DATA, tolerance={"judge_pass_rate": {"target": 0.70, "band": 0.15}})
    write_baseline(tmp_path, monkeypatch, data)
    cli._assert_baseline(base_summary(judge_pass_rate=0.60))  # within band -> pass
    with pytest.raises(SystemExit, match="judge_pass_rate"):
        cli._assert_baseline(base_summary(judge_pass_rate=0.40))  # outside band -> fail


def test_committed_baseline_keys_match_summarize_output():
    """Guards against schema drift: every min/max key in the committed baseline
    must be a real summarize() key, or --ci would KeyError instead of gating."""
    baseline = json.loads(cli.BASELINE.read_text())
    summary_keys = set(summarize([]).keys())
    for section in ("min", "max"):
        for key in baseline.get(section, {}):
            assert key in summary_keys, f"{key!r} in baseline.{section} is not a summarize() key"
