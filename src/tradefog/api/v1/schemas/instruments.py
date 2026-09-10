"""Typed profile-local asset and instrument requests."""

from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from tradefog.domain.enums import AssetType, ProductKind


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
        if not normalized:
            raise ValueError("Symbol cannot be blank")
        return normalized


class AssetPatch(Patch):
    """Edit presentation or availability without repurposing identity."""

    nullable = {"name"}
    name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class AssetResponse(BaseModel):
    """One asset owned by the profile."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    profile_id: int
    symbol: str
    name: str | None
    asset_type: AssetType
    is_active: bool


class InstrumentWrite(Input):
    """Symbol-only import for Bybit, complete specification for manual."""

    exec_symbol: str = Field(min_length=1, max_length=64)
    product: ProductKind
    name: str | None = Field(default=None, max_length=255)
    base_asset_id: int | None = Field(default=None, gt=0)
    quote_asset_id: int | None = Field(default=None, gt=0)
    settlement_asset_id: int | None = Field(default=None, gt=0)
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

    @field_validator("exec_symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        """Normalize the executable symbol without guessing provider aliases."""
        return AssetWrite.normalize_symbol(value)


class InstrumentPatch(Patch):
    """Update editable metadata; identity remains immutable."""

    nullable = {"name", "min_qty", "min_notional"}
    name: str | None = Field(default=None, max_length=255)
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
    name: str | None
    product: ProductKind
    base_asset_id: int
    quote_asset_id: int
    settlement_asset_id: int
    price_step: Decimal
    qty_step: Decimal
    min_qty: Decimal | None
    min_notional: Decimal | None
    metadata_updated_at: datetime | None
    is_active: bool
    is_archived: bool
