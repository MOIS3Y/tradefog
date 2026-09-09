"""Index owner-scoped journal pagination and review queues.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision: str = "0002"
down_revision: str = "0001"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    """Add indexes without changing journal records."""
    op.create_index("profile_owner_idx", "TradingProfile", ["owner_id", "id"])
    op.create_index(
        "trade_profile_date_idx", "Trade", ["profile_id", "trade_date", "id"]
    )
    op.create_index(
        "trade_profile_rating_idx",
        "Trade",
        ["profile_id", "quality_rating", "id"],
    )
    op.create_index(
        "trade_profile_review_idx",
        "Trade",
        ["profile_id", "status", "review_completed_at", "id"],
    )


def downgrade() -> None:
    """Remove only this revision's indexes."""
    op.drop_index("trade_profile_review_idx", table_name="Trade")
    op.drop_index("trade_profile_rating_idx", table_name="Trade")
    op.drop_index("trade_profile_date_idx", table_name="Trade")
    op.drop_index("profile_owner_idx", table_name="TradingProfile")
