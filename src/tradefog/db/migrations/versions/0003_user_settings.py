"""Persist account language and revocable credential versions."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep existing accounts and browser preferences unchanged."""
    op.add_column("users", sa.Column("preferred_locale", sa.String(2)))
    op.add_column(
        "users",
        sa.Column(
            "auth_version", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    """Remove settings without deleting account records."""
    with op.batch_alter_table("users") as batch:
        batch.drop_column("auth_version")
        batch.drop_column("preferred_locale")
