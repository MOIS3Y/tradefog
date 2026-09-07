"""JWT bearer-token endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from tradefog.api.dependencies import (
    CurrentUserDependency,
    SessionDependency,
    get_authentication_settings,
)
from tradefog.api.errors import api_error
from tradefog.api.security import (
    DUMMY_PASSWORD_HASH,
    create_token,
    decode_token,
    verify_password,
)
from tradefog.api.v1.schemas.auth import (
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from tradefog.config.authentication import AuthenticationSettings
from tradefog.db.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


def token_pair(user: User, settings: AuthenticationSettings) -> TokenResponse:
    """Create a complete renewable token pair for an authenticated account."""
    return TokenResponse(
        access_token=create_token(user.id, "access", settings),
        refresh_token=create_token(user.id, "refresh", settings),
    )


@router.post("/token", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDependency,
    settings: Annotated[
        AuthenticationSettings,
        Depends(get_authentication_settings),
    ],
) -> TokenResponse:
    """Exchange valid form credentials for access and refresh JWTs."""
    user = await session.scalar(
        select(User).where(User.username == form.username)
    )
    verified = await run_in_threadpool(
        verify_password,
        form.password,
        user.password if user is not None else DUMMY_PASSWORD_HASH,
    )
    if user is None or not user.is_active or not verified:
        api_error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "Incorrect username or password",
        )
    return token_pair(user, settings)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    session: SessionDependency,
    settings: Annotated[
        AuthenticationSettings,
        Depends(get_authentication_settings),
    ],
) -> TokenResponse:
    """Exchange a valid refresh JWT for a fresh token pair."""
    subject = decode_token(request.refresh_token, "refresh", settings)
    user = await session.get(User, subject) if subject is not None else None
    if user is None or not user.is_active:
        api_error(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "Could not validate credentials",
        )
    return token_pair(user, settings)


@router.get("/me", response_model=UserResponse)
async def current_user(user: CurrentUserDependency) -> User:
    """Return the active account represented by the access token."""
    return user
