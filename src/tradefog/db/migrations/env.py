"""Run migrations with the same settings and engine as the application."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from tradefog.config import get_settings
from tradefog.db import models  # noqa: F401
from tradefog.db.base import Base
from tradefog.db.session import create_engine, database_url


def run_migrations_offline() -> None:
    """Render SQL without opening a database connection."""
    context.configure(
        url=database_url(get_settings().database),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate(connection: Connection) -> None:
    """Apply revisions on the async engine's synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Own a temporary engine for a migration invocation."""
    engine = create_engine(get_settings().database)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
