"""hackathon_prize_label

Revision ID: 25704d8e1b75
Revises: 48f0e210b44e
Create Date: 2026-07-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25704d8e1b75"
down_revision: Union[str, Sequence[str], None] = "48f0e210b44e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hackathons",
        sa.Column(
            "prize_label",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )


def downgrade() -> None:
    op.drop_column("hackathons", "prize_label")
