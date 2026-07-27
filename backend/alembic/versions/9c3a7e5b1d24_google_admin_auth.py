"""Rename admin_users GitHub columns to provider-neutral Google identity.

Admin login moved from GitHub OAuth to Google OAuth. The allowlist is by
verified email; the immutable Google `sub` is stored as `subject`.

Revision ID: 9c3a7e5b1d24
Revises: 25704d8e1b75
Create Date: 2026-07-27
"""

from __future__ import annotations

from alembic import op

revision = "9c3a7e5b1d24"
down_revision = "25704d8e1b75"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("admin_users", "github_user_id", new_column_name="subject")
    op.alter_column("admin_users", "github_login", new_column_name="email")
    # Keep the constraint name aligned with the naming convention (uq_<table>_<col>)
    # so `alembic check` stays clean after the column rename.
    op.execute(
        "ALTER TABLE admin_users RENAME CONSTRAINT "
        "uq_admin_users_github_user_id TO uq_admin_users_subject"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE admin_users RENAME CONSTRAINT "
        "uq_admin_users_subject TO uq_admin_users_github_user_id"
    )
    op.alter_column("admin_users", "subject", new_column_name="github_user_id")
    op.alter_column("admin_users", "email", new_column_name="github_login")
