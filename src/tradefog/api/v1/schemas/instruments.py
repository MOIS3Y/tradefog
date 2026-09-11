"""Typed profile-local asset and instrument requests."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from tradefog.domain.enums import AssetType, ProductKind, WalletAssetStatus


class Input(BaseModel):
    """Reject fields not belonging to the requested operation."""

    model_config = ConfigDict(extra="forbid")


class Patch(Input):
    """Allow null only for explicitly optional persistent fields."""

    nullable: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def reject_null(self) -> Self:
        """Distinguish a missing patch value from explicit null."""
        for key, value in self.model_dump(exclude_unset=True).items():
            if value is None and key not in self.nullable:
                raise ValueError(f"{key} cannot be null")
        return self


class AssetWrite(Input):
    """Create a manual asset in one profile."""

    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    asset_type: AssetType

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        """Store one normalized identity within the profile."""
        normalized = value.strip().upper()
        if not normalized or "/" in normalized:
            raise ValueError(
                "Asset symbols must be nonblank and cannot contain /"
            )
        return normalized


class AssetPatch(Patch):
    """Edit presentation or availability without repurposing identity."""

    nullable = {"name", "risk_stop_capital"}
    risk_stop_capital: Decimal | None = Field(
        default=None, ge=0, max_digits=30, decimal_places=18
    )
    name: str | None = Field(default=None, max_length=255)
    is_archived: bool | None = None


class AssetResponse(BaseModel):
    """One asset owned by the profile."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    profile_id: int
    symbol: str
    name: str | None
    asset_type: AssetType
    is_archived: bool
    risk_stop_capital: Decimal | None
    status: WalletAssetStatus
    balance: Decimal
    allocated: Decimal
    reserved: Decimal
    available: Decimal
    uncommitted: Decimal


class AssetInput(Input):
    """Identify an existing asset or supply the type for a new symbol."""

    symbol: str = Field(min_length=1, max_length=32)
    asset_type: AssetType | None = None
    name: str | None = Field(default=None, max_length=255)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        """Use the same identity normalization for all creation paths."""
        return AssetWrite.normalize_symbol(value)


class ManualInstrumentWrite(Input):
    """Create a manual instrument and any missing profile assets."""

    mode: Literal["manual"]
    product: ProductKind
    base: AssetInput
    quote: AssetInput
    price_step: Decimal = Field(gt=0, max_digits=30, decimal_places=18)
    qty_step: Decimal = Field(gt=0, max_digits=30, decimal_places=18)
    min_qty: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    min_notional: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )


class BybitInstrumentWrite(Input):
    """Import an explicitly selected exchange instrument."""

    mode: Literal["bybit"]
    product: ProductKind
    exec_symbol: str = Field(min_length=1, max_length=64)

    @field_validator("exec_symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        """Normalize the provider identity, without splitting it."""
        return AssetWrite.normalize_symbol(value)


InstrumentWrite = Annotated[
    ManualInstrumentWrite | BybitInstrumentWrite,
    Field(discriminator="mode"),
]


class InstrumentPatch(Patch):
    """Update editable metadata; identity remains immutable."""

    nullable = {"min_qty", "min_notional"}
    price_step: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    qty_step: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    min_qty: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    min_notional: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    is_active: bool | None = None
    is_archived: bool | None = None


class InstrumentResponse(BaseModel):
    """Normalized profile instrument with exact execution rules."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    profile_id: int
    exec_symbol: str
    product: ProductKind
    base_asset_id: int
    quote_asset_id: int
    settlement_asset_id: int
    base_asset_type: AssetType
    quote_asset_type: AssetType
    price_step: Decimal
    qty_step: Decimal
    min_qty: Decimal | None
    min_notional: Decimal | None
    metadata_updated_at: datetime | None
    is_active: bool
    is_archived: bool
