"""Add an optional browser link without changing exchange transports."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve existing profiles with an empty venue link."""
    op.add_column(
        "TradingProfile",
        sa.Column("venue_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    """Remove the optional link while preserving journal records."""
    with op.batch_alter_table("TradingProfile") as batch:
        batch.drop_column("venue_url")
