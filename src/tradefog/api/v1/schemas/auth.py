"""Transport models for account and token endpoints."""

from pydantic import BaseModel, ConfigDict, Field


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
