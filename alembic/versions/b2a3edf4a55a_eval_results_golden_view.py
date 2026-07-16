"""eval_results_golden view

Revision ID: b2a3edf4a55a
Revises: 868d4d9166da
Create Date: 2026-07-16 00:00:00.000000

Hardening Task 2 (issue #45): a read-only Postgres view joining eval_results
to eval_cases, filtered to the golden set (kind <> 'calibration'), exposing
the columns Week 3's console needs (result fields + kind, expected_outcome,
adversarial_kind). This is the ONLY sanctioned read path for golden metrics
from non-Python consumers -- see docs/00-spec/DATA-SCHEMA.md.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2a3edf4a55a'
down_revision: str | Sequence[str] | None = '868d4d9166da'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_VIEW = """
CREATE VIEW eval_results_golden AS
SELECT
    er.id,
    er.eval_run_id,
    er.case_id,
    er.run_id,
    er.predicted_queue,
    er.predicted_outcome,
    er.escalation_reason,
    er.cost_usd,
    er.latency_ms,
    er.retrieval_similarity,
    er.classification_margin,
    er.routing_correct,
    er.outcome_correct,
    er.judge_verdict,
    er.judge_reason,
    er.judge_rule_triggered,
    er.human_label,
    er.created_at,
    ec.kind,
    ec.expected_outcome,
    ec.adversarial_kind
FROM eval_results er
JOIN eval_cases ec ON ec.id = er.case_id
WHERE ec.kind <> 'calibration'
"""

_DROP_VIEW = "DROP VIEW eval_results_golden"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(_CREATE_VIEW)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(_DROP_VIEW)
