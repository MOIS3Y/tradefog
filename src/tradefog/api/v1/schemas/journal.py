"""Transport models for profiles, wallets, strategies and ledger facts."""

from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from tradefog.domain.enums import (
    StrategyStatus,
    WalletAssetStatus,
    WalletOperationKind,
)


class JournalInput(BaseModel):
    """Reject accidental fields on owner-scoped mutation requests."""

    model_config = ConfigDict(extra="forbid")


class ProfileCreate(JournalInput):
    """Create a venue-bound trading workspace."""

    venue_id: int = Field(gt=0)
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


class ProfilePatch(JournalInput):
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
    venue_id: int
    name: str
    description: str | None
    is_archived: bool


class WalletAssetCreate(JournalInput):
    """Add one active venue capability to a profile wallet."""

    venue_wallet_asset_id: int = Field(gt=0)
    risk_stop_capital: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=30,
        decimal_places=18,
    )


class WalletAssetPatch(JournalInput):
    """Edit the advisory deposit floor or archive a zero balance."""

    risk_stop_capital: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=30,
        decimal_places=18,
    )
    is_archived: bool | None = None

    @model_validator(mode="after")
    def reject_null_archive_flag(self) -> "WalletAssetPatch":
        """Prevent explicit null for the archive flag."""
        fields = self.model_dump(exclude_unset=True)
        if fields.get("is_archived", False) is None:
            raise ValueError("is_archived cannot be null")
        return self


class WalletAssetResponse(BaseModel):
    """Wallet asset with exact derived balance and reservations."""

    id: int
    venue_wallet_asset_id: int
    asset_id: int
    symbol: str
    balance: Decimal
    allocated: Decimal
    reserved: Decimal
    available: Decimal
    uncommitted: Decimal
    risk_stop_capital: Decimal | None
    status: WalletAssetStatus
    is_archived: bool


class WalletResponse(BaseModel):
    """The one wallet belonging to a profile."""

    id: int
    profile_id: int
    assets: list[WalletAssetResponse]


class WalletOperationCreate(JournalInput):
    """Append a positive deposit or withdrawal request."""

    kind: WalletOperationKind
    amount: Decimal = Field(gt=0, max_digits=30, decimal_places=18)
    note: str | None = Field(default=None, max_length=255)


class WalletOperationPatch(JournalInput):
    """Correct only the note attached to an immutable ledger fact."""

    note: str | None = Field(default=None, max_length=255)


class WalletOperationResponse(BaseModel):
    """Immutable signed wallet ledger fact."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_asset_id: int
    kind: WalletOperationKind
    amount: Decimal
    note: str | None
    created_at: datetime


class StrategyCreate(JournalInput):
    """Create reusable edge rules within a trading profile."""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    risk_percent: Decimal = Field(
        gt=0, le=100, max_digits=10, decimal_places=6
    )
    reward_multiple: Decimal = Field(
        default=Decimal(3),
        gt=0,
        max_digits=10,
        decimal_places=6,
    )

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

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    risk_percent: Decimal | None = Field(
        default=None,
        gt=0,
        le=100,
        max_digits=10,
        decimal_places=6,
    )
    reward_multiple: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=6,
    )
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

    wallet_asset_id: int = Field(gt=0)
    capital: Decimal = Field(gt=0, max_digits=30, decimal_places=18)


class StrategyCapitalPatch(JournalInput):
    """Edit unlocked allocation capital or its archive state."""

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

    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_id: int
    wallet_asset_id: int
    capital: Decimal
    is_archived: bool


class StrategyResponse(BaseModel):
    """Strategy edge rules and their per-asset allocations."""

    id: int
    profile_id: int
    name: str
    description: str | None
    risk_percent: Decimal
    reward_multiple: Decimal
    status: StrategyStatus
    is_archived: bool
    allocations: list[StrategyCapitalResponse]
