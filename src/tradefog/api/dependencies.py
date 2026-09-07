"""Request-scoped persistence dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tradefog.db.session import Database


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide a transaction committed before the response is sent."""
    database = cast(Database, request.app.state.database)
    async with database.session() as session:
        yield session


SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session, scope="function"),
]
