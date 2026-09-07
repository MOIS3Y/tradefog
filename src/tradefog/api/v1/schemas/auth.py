"""Transport models for account registration and token exchange."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError


class RegisterRequest(BaseModel):
    """Public request to create a regular self-hosted journal account."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, username: object) -> str:
        """Store a stable, whitespace-free login identifier."""
        if not isinstance(username, str):
            raise PydanticCustomError(
                "string_type", "Username must be a string"
            )
        normalized = username.strip()
        if not normalized or any(
            character.isspace() for character in normalized
        ):
            raise ValueError("Username cannot be empty or contain whitespace")
        return normalized


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
