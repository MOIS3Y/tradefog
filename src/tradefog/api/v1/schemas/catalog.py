"""Transport models for the staff-maintained shared reference catalog."""

from decimal import Decimal
from typing import ClassVar, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from tradefog.domain.enums import AssetType, MarketDataProvider, ProductKind


class CatalogInput(BaseModel):
    """Reject unknown catalog fields instead of silently dropping edits."""

    model_config = ConfigDict(extra="forbid")


class CatalogPatch(CatalogInput):
    """Distinguish omitted attributes from explicit, invalid null values."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_required_nulls(self) -> Self:
        """Allow null only for fields whose database columns are nullable."""
        for name, value in self.model_dump(exclude_unset=True).items():
            if value is None and name not in self.nullable_fields:
                raise ValueError(f"{name} cannot be null")
        return self


class CatalogModel(BaseModel):
    """Enable direct serialization from SQLAlchemy catalog entities."""

    model_config = ConfigDict(from_attributes=True)


class AssetResponse(CatalogModel):
    """Shared asset identity returned by catalog endpoints."""

    id: int
    symbol: str
    name: str | None
    asset_type: AssetType


class AssetWrite(CatalogInput):
    """Staff-managed attributes for a shared asset."""

    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    asset_type: AssetType

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, symbol: object) -> str:
        """Produce the canonical symbol accepted by the database check."""
        if not isinstance(symbol, str):
            raise PydanticCustomError(
                "string_type", "Asset symbol must be a string"
            )
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Asset symbol cannot be blank")
        return normalized


class AssetPatch(CatalogPatch):
    """Optional staff edits to an existing asset."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset({"name"})

    symbol: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    asset_type: AssetType | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, symbol: str | None) -> str | None:
        """Normalize a supplied symbol while preserving an omitted field."""
        return (
            AssetWrite.normalize_symbol(symbol) if symbol is not None else None
        )


class PairResponse(CatalogModel):
    """Logical base/quote market including both shared asset identities."""

    id: int
    base: AssetResponse
    quote: AssetResponse
    canonical_symbol: str


class PairWrite(CatalogInput):
    """Staff input identifying the two sides of a logical market."""

    base_id: int = Field(gt=0)
    quote_id: int = Field(gt=0)


class PairPatch(CatalogPatch):
    """Optional staff correction to either asset of a logical market."""

    base_id: int | None = Field(default=None, gt=0)
    quote_id: int | None = Field(default=None, gt=0)


class VenueResponse(CatalogModel):
    """Exchange or broker destination in the shared catalog."""

    id: int
    name: str
    market_data_provider: MarketDataProvider
    description: str | None
    website: str | None
    is_active: bool


class VenueWrite(CatalogInput):
    """Staff-managed venue attributes."""

    name: str = Field(min_length=1, max_length=128)
    market_data_provider: MarketDataProvider = MarketDataProvider.NONE
    description: str | None = None
    website: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, name: object) -> str:
        """Prevent whitespace-only venue identities."""
        if not isinstance(name, str):
            raise PydanticCustomError(
                "string_type", "Venue name must be a string"
            )
        normalized = name.strip()
        if not normalized:
            raise ValueError("Venue name cannot be blank")
        return normalized


class VenuePatch(CatalogPatch):
    """Optional staff edits to a venue."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"description", "website"},
    )

    name: str | None = Field(default=None, min_length=1, max_length=128)
    market_data_provider: MarketDataProvider | None = None
    description: str | None = None
    website: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, name: str | None) -> str | None:
        """Normalize a supplied venue name."""
        return VenueWrite.normalize_name(name) if name is not None else None


class InstrumentResponse(CatalogModel):
    """Executable venue market and its order-size rules."""

    id: int
    venue_id: int
    pair: PairResponse
    product: ProductKind
    exec_symbol: str
    price_step: Decimal
    qty_step: Decimal
    min_qty: Decimal | None
    min_notional: Decimal | None
    settlement_asset: AssetResponse | None
    is_active: bool


class InstrumentWrite(CatalogInput):
    """Staff input for a venue-specific executable market."""

    pair_id: int = Field(gt=0)
    product: ProductKind
    exec_symbol: str = Field(min_length=1, max_length=64)
    price_step: Decimal = Field(gt=0, max_digits=30, decimal_places=18)
    qty_step: Decimal = Field(gt=0, max_digits=30, decimal_places=18)
    min_qty: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    min_notional: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    settlement_asset_id: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @field_validator("exec_symbol", mode="before")
    @classmethod
    def normalize_exec_symbol(cls, symbol: object) -> str:
        """Store the exchange identifier in its normalized uppercase form."""
        if not isinstance(symbol, str):
            raise PydanticCustomError(
                "string_type", "Execution symbol must be a string"
            )
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Execution symbol cannot be blank")
        return normalized


class InstrumentPatch(CatalogPatch):
    """Optional staff edits to an executable venue market."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"min_qty", "min_notional", "settlement_asset_id"},
    )

    product: ProductKind | None = None
    exec_symbol: str | None = Field(default=None, min_length=1, max_length=64)
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
    settlement_asset_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @field_validator("exec_symbol", mode="before")
    @classmethod
    def normalize_exec_symbol(cls, symbol: str | None) -> str | None:
        """Normalize a supplied exchange identifier."""
        return (
            InstrumentWrite.normalize_exec_symbol(symbol)
            if symbol is not None
            else None
        )


class VenueWalletAssetResponse(CatalogModel):
    """An asset allowed as a balance or settlement asset at a venue."""

    id: int
    venue_id: int
    asset: AssetResponse
    is_active: bool


class VenueWalletAssetWrite(CatalogInput):
    """Staff input connecting an asset to a venue's wallet capability."""

    asset_id: int = Field(gt=0)
    is_active: bool = True


class VenueWalletAssetPatch(CatalogPatch):
    """Optional staff edit to a venue wallet capability."""

    is_active: bool | None = None
