"""Request-scoped persistence dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tradefog.api.errors import api_error
from tradefog.api.security import decode_token
from tradefog.config.authentication import AuthenticationSettings
from tradefog.db.models import User
from tradefog.db.session import Database

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide a transaction committed before the response is sent."""
    database = cast(Database, request.app.state.database)
    async with database.session() as session:
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and session.bind.dialect.name == "sqlite"
        ):
            await session.execute(text("BEGIN IMMEDIATE"))
        yield session


SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session, scope="function"),
]


def get_authentication_settings(request: Request) -> AuthenticationSettings:
    """Return authentication settings selected for this application instance."""
    return request.app.state.settings.authentication


async def get_current_user(
    request: Request,
    session: SessionDependency,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Resolve an active account from a valid access bearer token."""
    subject = decode_token(
        token,
        "access",
        get_authentication_settings(request),
    )
    if subject is None:
        api_error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "Could not validate credentials",
        )
    statement = select(User).where(User.id == subject[0])
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        statement = statement.with_for_update()
    user = await session.scalar(statement)
    if user is None or not user.is_active or user.auth_version != subject[1]:
        api_error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "Could not validate credentials",
        )
    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]


async def get_staff_user(user: CurrentUserDependency) -> User:
    """Require the administrative role without granting journal ownership."""
    if not user.is_staff:
        api_error(
            status.HTTP_403_FORBIDDEN,
            "staff_required",
            "Staff access is required",
        )
    return user


StaffUserDependency = Annotated[User, Depends(get_staff_user)]
