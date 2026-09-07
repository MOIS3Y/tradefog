"""Shared declarative metadata and primary-key mixin."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Use stable constraint names for portable Alembic migrations."""

    metadata: MetaData = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class PrimaryKeyMixin:
    """Provide the integer identity shared by DBML entities."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
