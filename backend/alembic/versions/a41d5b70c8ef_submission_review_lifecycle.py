"""Add observable lifecycle fields for AI-reviewed community submissions.

Revision ID: a41d5b70c8ef
Revises: 9c3a7e5b1d24
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a41d5b70c8ef"
down_revision = "9c3a7e5b1d24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "community_submissions",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "community_submissions",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "community_submissions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("community_submissions", "reviewed_at")
    op.drop_column("community_submissions", "last_error")
    op.drop_column("community_submissions", "attempt_count")
