"""Transport models for account and token endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from tradefog.domain.accounts import validate_password


class UserResponse(BaseModel):
    """Safe public account representation without authentication material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_staff: bool
    is_active: bool
    first_name: str | None
    last_name: str | None
    email: str | None
    preferred_locale: Literal["en", "ru"] | None
    created_at: datetime
    updated_at: datetime


class UserPatch(BaseModel):
    """Self-service metadata and language; never privileges or credentials."""

    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = Field(default=None, max_length=254)
    preferred_locale: Literal["en", "ru"] | None = None

    @field_validator("first_name", "last_name", "email", mode="before")
    @classmethod
    def trim_optional(cls, value: object) -> object:
        """Normalize blank optional fields to absence."""
        return value.strip() or None if isinstance(value, str) else value


class PasswordChange(BaseModel):
    """Verify existing credentials before replacing the password."""

    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128, repr=False)
    new_password: str = Field(repr=False)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        """Apply the same password policy as account provisioning."""
        return validate_password(value)


class TokenResponse(BaseModel):
    """Access and refresh token pair returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request a fresh token pair from a valid refresh token."""

    refresh_token: str = Field(min_length=1)
