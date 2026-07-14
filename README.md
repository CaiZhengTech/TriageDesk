# TriageDesk

AI support-ticket triage agent with a glass-box ops console: every run is traced,
evaluated, cost-capped, and — where stakes require it — routed to a human review queue.

**📖 Start with the [documentation map](docs/README.md)** — it says where everything is.

Quick links: [design record](docs/00-spec/DESIGN-SPEC.md) ·
[the pitch](docs/00-spec/PITCH.md) ·
[what Week 1 built, in plain language](docs/week-1-pipeline/STORY.md) ·
[what Week 2 built](docs/week-2-evals/STORY.md)

Issues #1–#18 are the build sequence; plan docs in `docs/week-N-*/PLAN.md` are canonical
for implementation detail.

## Architecture

    ticket → [pre-check] → [classify] → [retrieve] → [act loop] → [confidence gate]
                 ↓ fail        ↓ low margin              ↓ exhausted      ↓ low / adverse
              escalate       escalate               agent_incomplete   review queue

## Local setup

1. Python 3.13, `python -m venv .venv`, activate, `pip install -r requirements.txt`
2. Secrets: see `.env.example` — set `TRIAGEDESK_ENV_FILE` to the absolute path of a
   credentials env file (e.g., `setx TRIAGEDESK_ENV_FILE "<path>"` on Windows);
   secrets never live in the repo
3. `alembic upgrade head` (dev DB), `pytest` (integration tests need `TEST_DATABASE_URL`)

## CI / evals

**Eval gate (`.github/workflows/eval.yml`)** re-runs the 25-case golden set on
every merge to `main` ($1 cap): deterministic metrics gated exactly, judge
metrics with a tolerance band. **KILL CHECKPOINT (issue #12): if this gate is
not green by end of Wk2, the console (Wk3) is cut to a single read-only page and
remaining hours go to pipeline + evals. This rule is not negotiable mid-project.**

Trigger is `workflow_dispatch` (manual) plus `push` to `main` filtered to
eval-relevant paths (`triagedesk/**`, `kb/**`, `results/eval-baseline.json`,
the workflow file itself) — a council amendment so console/docs merges in
Weeks 3–4 don't burn $1–1.5 each. `results/eval-baseline.json` is a regression
floor on currently observed behavior, not a quality target — see the `_note`
field in that file.
