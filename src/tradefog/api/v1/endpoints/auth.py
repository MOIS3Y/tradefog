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
    hash_password,
    verify_password,
)
from tradefog.api.v1.schemas.auth import (
    PasswordChange,
    RefreshRequest,
    TokenResponse,
    UserPatch,
    UserResponse,
)
from tradefog.config.authentication import AuthenticationSettings
from tradefog.db.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


def token_pair(user: User, settings: AuthenticationSettings) -> TokenResponse:
    """Create a complete renewable token pair for an authenticated account."""
    return TokenResponse(
        access_token=create_token(
            user.id, "access", settings, user.auth_version
        ),
        refresh_token=create_token(
            user.id, "refresh", settings, user.auth_version
        ),
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
    user = await session.get(User, subject[0]) if subject is not None else None
    if (
        user is None
        or not user.is_active
        or subject is None
        or user.auth_version != subject[1]
    ):
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


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: PasswordChange,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> None:
    """Replace verified credentials and invalidate every previous session."""
    if not await run_in_threadpool(
        verify_password, request.current_password, user.password
    ):
        api_error(
            400, "current_password_invalid", "Current password is incorrect"
        )
    if request.new_password == request.current_password:
        api_error(400, "password_unchanged", "Choose a different password")
    user.password = await run_in_threadpool(
        hash_password, request.new_password
    )
    user.auth_version += 1
    await session.flush()


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    request: UserPatch, session: SessionDependency, user: CurrentUserDependency
) -> User:
    """Edit the authenticated user's contact fields and language preference."""
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.flush()
    await session.refresh(user)
    return user
