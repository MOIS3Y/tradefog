"""Add private trade attachment metadata.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create owner-scoped attachment metadata storage."""
    _ = op.create_table(
        "Attachment",
        sa.Column("trade_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["trade_id"],
            ["Trade.id"],
            name=op.f("fk_Attachment_trade_id_Trade"),
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name=op.f("ck_Attachment_non_negative_size"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Attachment")),
        sa.UniqueConstraint(
            "storage_key",
            name=op.f("uq_Attachment_storage_key"),
        ),
    )


def downgrade() -> None:
    """Remove private attachment metadata storage."""
    op.drop_table("Attachment")
