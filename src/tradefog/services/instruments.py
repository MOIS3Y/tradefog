"""Import or validate profile-owned specifications without funding wallets."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradefog.api.errors import api_error, conflict
from tradefog.db.models import TradingAsset, TradingInstrument, TradingProfile
from tradefog.domain.enums import AssetType, VenueType
from tradefog.market.contracts import InstrumentSpec
from tradefog.market.public_service import PublicMarketService


async def import_spec(
    session: AsyncSession,
    profile: TradingProfile,
    symbol: str,
    product: str,
    market: PublicMarketService,
) -> tuple[InstrumentSpec, dict[str, int]]:
    """Fetch one supported market and create only its required assets."""
    if profile.venue_type != VenueType.BYBIT or product not in (
        "spot",
        "perpetual_future",
    ):
        api_error(
            422,
            "unsupported_product",
            "No automatic specification for this market",
        )
    spec = await market.instrument("bybit", symbol, product)
    assets: dict[str, int] = {}
    for role, code in (
        ("base", spec.base),
        ("quote", spec.quote),
        ("settlement", spec.settlement),
    ):
        asset = await session.scalar(
            select(TradingAsset).where(
                TradingAsset.profile_id == profile.id,
                TradingAsset.symbol == code,
            )
        )
        if asset is None:
            asset = TradingAsset(
                profile_id=profile.id, symbol=code, asset_type=AssetType.CRYPTO
            )
            session.add(asset)
            await session.flush()
        if not asset.is_active:
            conflict("Required profile asset is inactive")
        assets[f"{role}_asset_id"] = asset.id
    return spec, assets


def apply_spec(item: TradingInstrument, spec: InstrumentSpec) -> None:
    """Refresh rules and source availability without overwriting archives."""
    for field in (
        "price_step",
        "qty_step",
        "min_qty",
        "min_notional",
        "is_active",
    ):
        setattr(item, field, getattr(spec, field))
    item.metadata_updated_at = datetime.now(UTC).replace(tzinfo=None)


async def validate_assets(
    session: AsyncSession,
    profile_id: int,
    base: int,
    quote: int,
    settlement: int,
) -> None:
    """Require supported same-profile denominations for every product."""
    if base == quote or settlement != quote:
        api_error(
            422,
            "invalid_denominations",
            "Base must differ from quote; settlement must equal quote",
        )
    for asset_id in {base, quote, settlement}:
        item = await session.get(TradingAsset, asset_id)
        if item is None or item.profile_id != profile_id or not item.is_active:
            api_error(
                422,
                "invalid_asset",
                "An active asset in this profile is required",
            )
