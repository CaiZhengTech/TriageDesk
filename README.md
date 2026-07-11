# TriageDesk

AI support-ticket triage agent with a glass-box ops console: every run is traced,
evaluated, cost-capped, and — where stakes require it — routed to a human review queue.

**Read this first:** the design record lives in
[`docs/superpowers/specs/2026-07-10-triagedesk-design.md`](docs/superpowers/specs/2026-07-10-triagedesk-design.md).
Issues #1–#18 are the build sequence; plan docs in `docs/superpowers/plans/` are canonical
for implementation detail.

## Architecture

    ticket → [pre-check] → [classify] → [retrieve] → [act loop] → [confidence gate]
                 ↓ fail        ↓ low margin              ↓ exhausted      ↓ low / adverse
              escalate       escalate               agent_incomplete   review queue

## Local setup

1. Python 3.13, `python -m venv .venv`, activate, `pip install -r requirements.txt`
2. Secrets: see `.env.example` — locally they live in a machine-level env file
   (path in `triagedesk/config.py`), never in the repo
3. `alembic upgrade head` (dev DB), `pytest` (integration tests need `TEST_DATABASE_URL`)
