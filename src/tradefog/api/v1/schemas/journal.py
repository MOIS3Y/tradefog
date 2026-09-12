"""Transport models for profiles, wallets, strategies and ledger facts."""

from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from tradefog.api.documentation import (
    ALLOCATION_CREATE_EXAMPLE,
    ALLOCATION_EXAMPLE,
    ALLOCATION_PATCH_EXAMPLE,
    STRATEGY_CREATE_EXAMPLE,
    STRATEGY_EXAMPLE,
    STRATEGY_PATCH_EXAMPLE,
    WALLET_OPERATION_EXAMPLE,
    WALLET_OPERATION_RESPONSE_EXAMPLE,
)
from tradefog.domain.enums import (
    StrategyStatus,
    VenueType,
    WalletOperationKind,
)


class JournalInput(BaseModel):
    """Reject accidental fields on owner-scoped mutation requests."""

    model_config = ConfigDict(extra="forbid")


class ProfilePresentation(JournalInput):
    """Optional browser navigation, never an exchange transport address."""

    venue_url: str | None = Field(default=None, max_length=2048)

    @field_validator("venue_url")
    @classmethod
    def validate_venue_url(cls, value: str | None) -> str | None:
        """Accept only credential-free absolute HTTP(S) links."""
        if value is None or not value.strip():
            return None
        parts = urlsplit(value.strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("Venue URL must be an absolute HTTP(S) address")
        if parts.username is not None or parts.password is not None:
            raise ValueError("Venue URL must not contain credentials")
        normalized = str(HttpUrl(value.strip()))
        if len(normalized) > 2048:
            raise ValueError("Venue URL must not exceed 2048 characters")
        return normalized


class ProfileCreate(ProfilePresentation):
    """Create a venue-bound trading workspace."""

    venue_type: VenueType
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str) -> str:
        """Trim and reject a whitespace-only profile name."""
        normalized = name.strip()
        if not normalized:
            raise ValueError("Profile name cannot be blank")
        return normalized


class ProfilePatch(ProfilePresentation):
    """Edit profile presentation or its archive state."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    is_archived: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str | None) -> str | None:
        """Normalize a supplied profile name."""
        return ProfileCreate.normalize_name(name) if name is not None else None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "ProfilePatch":
        """Prevent explicit null for non-null profile columns."""
        fields = self.model_dump(exclude_unset=True)
        if (
            fields.get("name", False) is None
            or fields.get(
                "is_archived",
                False,
            )
            is None
        ):
            raise ValueError("name and is_archived cannot be null")
        return self


class ProfileResponse(BaseModel):
    """Owner-scoped profile summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_type: VenueType
    venue_url: str | None = None
    name: str
    description: str | None
    is_archived: bool


class WalletOperationCreate(JournalInput):
    """Append a positive deposit or withdrawal request."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [WALLET_OPERATION_EXAMPLE]}
    )

    kind: WalletOperationKind
    amount: Decimal = Field(
        gt=0,
        max_digits=30,
        decimal_places=18,
        description="Positive asset units for either kind of operation.",
    )
    note: str | None = Field(default=None, max_length=255)


class WalletOperationPatch(JournalInput):
    """Correct only the note attached to an immutable ledger fact."""

    note: str | None = Field(default=None, max_length=255)


class WalletOperationResponse(BaseModel):
    """Immutable signed wallet ledger fact."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [WALLET_OPERATION_RESPONSE_EXAMPLE]},
    )

    id: int
    asset_id: int
    kind: WalletOperationKind
    amount: Decimal = Field(
        description=(
            "Signed asset units: deposits positive, withdrawals negative."
        )
    )
    note: str | None
    created_at: datetime


class StrategyCreate(JournalInput):
    """Create reusable edge rules within a trading profile."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [STRATEGY_CREATE_EXAMPLE]},
    )

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    risk_percent: Decimal = Field(
        ge=Decimal("0.01"),
        le=100,
        max_digits=10,
        decimal_places=6,
        description="Risk per trade as a percentage of allocated capital.",
    )
    reward_multiple: int = Field(default=3, ge=3, le=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str) -> str:
        """Trim and reject a whitespace-only strategy name."""
        normalized = name.strip()
        if not normalized:
            raise ValueError("Strategy name cannot be blank")
        return normalized


class StrategyPatch(JournalInput):
    """Edit unlocked strategy rules or archive the strategy."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [STRATEGY_PATCH_EXAMPLE]},
    )

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    risk_percent: Decimal | None = Field(
        default=None,
        ge=Decimal("0.01"),
        le=100,
        max_digits=10,
        decimal_places=6,
    )
    reward_multiple: int | None = Field(default=None, ge=3, le=100)
    is_archived: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str | None) -> str | None:
        """Normalize a supplied strategy name."""
        return (
            StrategyCreate.normalize_name(name) if name is not None else None
        )

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "StrategyPatch":
        """Prevent explicit null for non-null strategy columns."""
        values = self.model_dump(exclude_unset=True)
        for field in (
            "name",
            "risk_percent",
            "reward_multiple",
            "is_archived",
        ):
            if field in values and values[field] is None:
                raise ValueError(f"{field} cannot be null")
        return self


class StrategyCapitalCreate(JournalInput):
    """Commit fixed strategy capital from a wallet asset."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [ALLOCATION_CREATE_EXAMPLE]},
    )

    asset_id: int = Field(gt=0)
    capital: Decimal = Field(gt=0, max_digits=30, decimal_places=18)


class StrategyCapitalPatch(JournalInput):
    """Edit unlocked allocation capital or its archive state."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [ALLOCATION_PATCH_EXAMPLE]},
    )

    capital: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=30,
        decimal_places=18,
    )
    is_archived: bool | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "StrategyCapitalPatch":
        """Prevent explicit null for allocation columns."""
        values = self.model_dump(exclude_unset=True)
        if any(value is None for value in values.values()):
            raise ValueError("Allocation fields cannot be null")
        return self


class StrategyCapitalResponse(BaseModel):
    """Fixed allocation for one wallet settlement asset."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [ALLOCATION_EXAMPLE]},
    )

    id: int
    strategy_id: int
    asset_id: int
    capital: Decimal
    is_archived: bool


class StrategyResponse(BaseModel):
    """Strategy edge rules and their per-asset allocations."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [STRATEGY_EXAMPLE]},
    )

    id: int
    profile_id: int
    name: str
    description: str | None
    risk_percent: Decimal
    reward_multiple: int
    status: StrategyStatus
    is_archived: bool
    allocations: list[StrategyCapitalResponse]
