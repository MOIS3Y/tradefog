"""Transport models for account registration and token exchange."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from tradefog.domain.accounts import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    normalize_username,
)


class RegisterRequest(BaseModel):
    """Public request to create a regular self-hosted journal account."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
    )
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
    )

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, username: object) -> str:
        """Store a stable, whitespace-free login identifier."""
        if not isinstance(username, str):
            raise PydanticCustomError(
                "string_type", "Username must be a string"
            )
        return normalize_username(username)


class UserResponse(BaseModel):
    """Safe public account representation without authentication material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_staff: bool
    is_active: bool


class TokenResponse(BaseModel):
    """Access and refresh token pair returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request a fresh token pair from a valid refresh token."""

    refresh_token: str = Field(min_length=1)
