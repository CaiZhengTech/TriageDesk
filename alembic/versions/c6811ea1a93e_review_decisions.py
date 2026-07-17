"""review_decisions table

Revision ID: c6811ea1a93e
Revises: b2a3edf4a55a
Create Date: 2026-07-17 00:00:00.000000

Week 3 Task 3 (issue #14): the review_decisions table backing the human-in-the-loop
review queue -- one row per escalated run once a human approves or rejects it.
`run_id` is unique: a run can be decided exactly once (the queue query excludes runs
that already have a decision).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c6811ea1a93e'
down_revision: str | Sequence[str] | None = 'b2a3edf4a55a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('review_decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('decision', sa.String(length=8), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('review_decisions')
