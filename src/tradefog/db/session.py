"""Async engines and explicit transactional session boundaries."""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy import event
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tradefog.config.database import DatabaseSettings


class SQLiteCursor(Protocol):
    """SQLite cursor operations required for connection setup."""

    def execute(self, statement: str) -> object:
        """Execute a connection-local SQLite pragma."""
        ...

    def close(self) -> None:
        """Release the cursor after setting pragmas."""
        ...


class SQLiteConnection(Protocol):
    """SQLite adapter operations required during connection setup."""

    def cursor(self) -> SQLiteCursor:
        """Open a cursor on the adapted connection."""
        ...

    def create_function(
        self,
        name: str,
        nargs: int,
        function: Callable[[str | None], str | None],
        *,
        deterministic: bool,
    ) -> None:
        """Register a deterministic scalar function on this connection."""
        ...


def lowercase_text(value: str | None) -> str | None:
    """Give SQLite Unicode lowercasing for journal and catalog searches."""
    return value.lower() if value is not None else None


def enable_sqlite_foreign_keys(
    connection: SQLiteConnection,
    _record: object,
) -> None:
    """Enable referential integrity on every pooled SQLite connection."""
    connection.create_function("lower", 1, lowercase_text, deterministic=True)
    cursor = connection.cursor()
    try:
        _ = cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def database_url(settings: DatabaseSettings) -> URL:
    """Build an async URL without interpreting credentials as URL syntax."""
    if settings.active == "sqlite":
        return URL.create(
            "sqlite+aiosqlite",
            database=str(settings.sqlite.path),
        )
    postgres = settings.psql
    return URL.create(
        "postgresql+asyncpg",
        username=postgres.user,
        password=postgres.password.get_secret_value(),
        host=postgres.host,
        port=postgres.port,
        database=postgres.name,
    )


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create a lazy async engine and prepare the SQLite data directory."""
    if settings.active == "sqlite":
        settings.sqlite.path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(database_url(settings), pool_pre_ping=True)
    if settings.active == "sqlite":
        event.listen(engine.sync_engine, "connect", enable_sqlite_foreign_keys)
    return engine


class Database:
    """Own an engine and provide one transaction per session context."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Create the engine and non-expiring session factory."""
        self.engine: AsyncEngine = create_engine(settings)
        self.sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        """Commit successful work and roll back failures before closing."""
        async with self.sessions.begin() as session:
            yield session

    async def dispose(self) -> None:
        """Release the connection pool on application shutdown."""
        await self.engine.dispose()
