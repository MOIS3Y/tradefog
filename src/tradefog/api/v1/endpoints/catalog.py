"""Public reference-catalog reads and staff-only catalog maintenance."""

from collections.abc import Sequence

from fastapi import APIRouter, status
from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from tradefog.api.dependencies import SessionDependency, StaffUserDependency
from tradefog.api.errors import api_error, conflict, not_found
from tradefog.api.v1.schemas.catalog import (
    AssetPatch,
    AssetResponse,
    AssetWrite,
    InstrumentPatch,
    InstrumentResponse,
    InstrumentWrite,
    PairPatch,
    PairResponse,
    PairWrite,
    VenuePatch,
    VenueResponse,
    VenueWalletAssetPatch,
    VenueWalletAssetResponse,
    VenueWalletAssetWrite,
    VenueWrite,
)
from tradefog.db.models import (
    Asset,
    Trade,
    TradingPair,
    Venue,
    VenueInstrument,
    VenueWalletAsset,
)
from tradefog.domain.enums import AssetType

router = APIRouter(prefix="/catalog", tags=["Catalog"])


def pair_options() -> tuple[ExecutableOption, ...]:
    """Eager-load both sides needed by every pair response."""
    return (selectinload(TradingPair.base), selectinload(TradingPair.quote))


def instrument_options() -> tuple[ExecutableOption, ...]:
    """Eager-load all nested values represented by an instrument response."""
    return (
        selectinload(VenueInstrument.pair).selectinload(TradingPair.base),
        selectinload(VenueInstrument.pair).selectinload(TradingPair.quote),
        selectinload(VenueInstrument.settlement_asset),
    )


async def get_or_404[
    CatalogEntity: Asset
    | TradingPair
    | Venue
    | VenueInstrument
    | VenueWalletAsset,
](
    session: AsyncSession,
    model: type[CatalogEntity],
    identifier: int,
    options: Sequence[ExecutableOption] = (),
) -> CatalogEntity:
    """Load a shared record or return the uniform missing-resource error."""
    statement: Select[tuple[CatalogEntity]] = select(model).where(
        model.id == identifier,
    )
    for option in options:
        statement = statement.options(option)
    item = await session.scalar(statement)
    if item is None:
        not_found(model.__name__)
    return item


async def flush_or_conflict(
    session: AsyncSession,
    message: str,
    code: str = "conflict",
) -> None:
    """Flush a mutation early and expose database uniqueness as HTTP 409."""
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        api_error(status.HTTP_409_CONFLICT, code, message)


async def resolve_pair_assets(
    session: AsyncSession,
    base_id: int,
    quote_id: int,
) -> tuple[Asset, Asset]:
    """Resolve a valid, non-self-referencing pair and its canonical symbol."""
    if base_id == quote_id:
        conflict("A trading pair requires two different assets")
    base = await get_or_404(session, Asset, base_id)
    quote = await get_or_404(session, Asset, quote_id)
    if len(f"{base.symbol}/{quote.symbol}") > 32:
        api_error(
            422, "invalid_pair", "Canonical symbol exceeds 32 characters"
        )
    return base, quote


@router.get("/assets", response_model=list[AssetResponse])
async def list_assets(
    session: SessionDependency,
    asset_type: AssetType | None = None,
) -> Sequence[Asset]:
    """List globally reusable assets, optionally filtered by their type."""
    statement = select(Asset).order_by(Asset.symbol)
    if asset_type is not None:
        statement = statement.where(Asset.asset_type == asset_type)
    return (await session.scalars(statement)).all()


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: int, session: SessionDependency) -> Asset:
    """Return one shared asset by its installation-wide identifier."""
    return await get_or_404(session, Asset, asset_id)


@router.post(
    "/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset(
    request: AssetWrite,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> Asset:
    """Create a new staff-managed shared asset identity."""
    asset = Asset(**request.model_dump())
    session.add(asset)
    await flush_or_conflict(session, "Asset symbol is already in use")
    return asset


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: int,
    request: AssetPatch,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> Asset:
    """Apply selected staff corrections to a shared asset."""
    asset = await get_or_404(session, Asset, asset_id)
    values = request.model_dump(exclude_unset=True)
    identity_changed = any(
        field in values and values[field] != getattr(asset, field)
        for field in ("symbol", "asset_type")
    )
    if identity_changed:
        references = (
            select(TradingPair.id).where(
                or_(
                    TradingPair.base_id == asset_id,
                    TradingPair.quote_id == asset_id,
                )
            ),
            select(VenueInstrument.id).where(
                VenueInstrument.settlement_asset_id == asset_id,
            ),
            select(VenueWalletAsset.id).where(
                VenueWalletAsset.asset_id == asset_id,
            ),
        )
        for statement in references:
            if await session.scalar(statement.limit(1)) is not None:
                conflict("Referenced asset identity cannot be changed")
    for field, value in values.items():
        setattr(asset, field, value)
    await flush_or_conflict(session, "Asset symbol is already in use")
    return asset


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_asset(
    asset_id: int,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> None:
    """Delete an unused asset without cascading into catalog history."""
    asset = await get_or_404(session, Asset, asset_id)
    references = (
        select(TradingPair.id).where(
            or_(
                TradingPair.base_id == asset_id,
                TradingPair.quote_id == asset_id,
            )
        ),
        select(VenueInstrument.id).where(
            VenueInstrument.settlement_asset_id == asset_id,
        ),
        select(VenueWalletAsset.id).where(
            VenueWalletAsset.asset_id == asset_id,
        ),
    )
    for statement in references:
        if await session.scalar(statement.limit(1)) is not None:
            api_error(
                status.HTTP_409_CONFLICT,
                "asset_in_use",
                "Asset is in use and cannot be deleted",
            )
    await session.delete(asset)
    await flush_or_conflict(
        session,
        "Asset is in use and cannot be deleted",
        "asset_in_use",
    )


@router.get("/pairs", response_model=list[PairResponse])
async def list_pairs(session: SessionDependency) -> Sequence[TradingPair]:
    """List logical markets with their base and quote assets."""
    statement = (
        select(TradingPair)
        .options(*pair_options())
        .order_by(
            TradingPair.canonical_symbol,
        )
    )
    return (await session.scalars(statement)).all()


@router.get("/pairs/{pair_id}", response_model=PairResponse)
async def get_pair(pair_id: int, session: SessionDependency) -> TradingPair:
    """Return one logical market with both constituent assets."""
    return await get_or_404(session, TradingPair, pair_id, pair_options())


@router.post(
    "/pairs",
    response_model=PairResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pair(
    request: PairWrite,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> TradingPair:
    """Create a logical market and derive its canonical BASE/QUOTE symbol."""
    base, quote = await resolve_pair_assets(
        session, request.base_id, request.quote_id
    )
    pair = TradingPair(
        base=base,
        quote=quote,
        canonical_symbol=f"{base.symbol}/{quote.symbol}",
    )
    session.add(pair)
    await flush_or_conflict(session, "Trading pair is already in use")
    return await get_or_404(session, TradingPair, pair.id, pair_options())


@router.patch("/pairs/{pair_id}", response_model=PairResponse)
async def update_pair(
    pair_id: int,
    request: PairPatch,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> TradingPair:
    """Correct pair assets and regenerate their canonical symbol."""
    pair = await get_or_404(session, TradingPair, pair_id, pair_options())
    values = request.model_dump(exclude_unset=True)
    identity_changed = any(
        value != getattr(pair, field) for field, value in values.items()
    )
    references = (
        select(VenueInstrument.id)
        .where(
            VenueInstrument.pair_id == pair_id,
        )
        .limit(1)
    )
    if identity_changed and await session.scalar(references) is not None:
        conflict("Referenced pair identity cannot be changed")
    if values:
        base_id = values.get("base_id", pair.base_id)
        quote_id = values.get("quote_id", pair.quote_id)
        base, quote = await resolve_pair_assets(session, base_id, quote_id)
        pair.base = base
        pair.quote = quote
        pair.canonical_symbol = f"{base.symbol}/{quote.symbol}"
        await flush_or_conflict(session, "Trading pair is already in use")
    return await get_or_404(session, TradingPair, pair.id, pair_options())


@router.delete(
    "/pairs/{pair_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pair(
    pair_id: int,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> None:
    """Delete an unused pair without cascading into venue instruments."""
    pair = await get_or_404(session, TradingPair, pair_id)
    reference = (
        select(VenueInstrument.id)
        .where(VenueInstrument.pair_id == pair_id)
        .limit(1)
    )
    if await session.scalar(reference) is not None:
        api_error(
            status.HTTP_409_CONFLICT,
            "pair_in_use",
            "Trading pair is in use and cannot be deleted",
        )
    await session.delete(pair)
    await flush_or_conflict(
        session,
        "Trading pair is in use and cannot be deleted",
        "pair_in_use",
    )


@router.get("/venues", response_model=list[VenueResponse])
async def list_venues(
    session: SessionDependency,
    active_only: bool = True,
) -> Sequence[Venue]:
    """List active venues by default, including archives when requested."""
    statement = select(Venue).order_by(Venue.name)
    if active_only:
        statement = statement.where(Venue.is_active)
    return (await session.scalars(statement)).all()


@router.get("/venues/{venue_id}", response_model=VenueResponse)
async def get_venue(venue_id: int, session: SessionDependency) -> Venue:
    """Return one exchange or broker destination."""
    return await get_or_404(session, Venue, venue_id)


@router.post(
    "/venues",
    response_model=VenueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_venue(
    request: VenueWrite,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> Venue:
    """Create a staff-managed execution venue."""
    venue = Venue(**request.model_dump())
    session.add(venue)
    await flush_or_conflict(session, "Venue name is already in use")
    return venue


@router.patch("/venues/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: int,
    request: VenuePatch,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> Venue:
    """Apply selected staff updates, including soft deactivation, to a venue."""
    venue = await get_or_404(session, Venue, venue_id)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)
    await flush_or_conflict(session, "Venue name is already in use")
    return venue


@router.get(
    "/venues/{venue_id}/instruments",
    response_model=list[InstrumentResponse],
)
async def list_instruments(
    venue_id: int,
    session: SessionDependency,
    active_only: bool = True,
) -> Sequence[VenueInstrument]:
    """List executable products at a venue with their market identities."""
    await get_or_404(session, Venue, venue_id)
    statement = (
        select(VenueInstrument)
        .where(VenueInstrument.venue_id == venue_id)
        .options(*instrument_options())
        .order_by(VenueInstrument.exec_symbol, VenueInstrument.product)
    )
    if active_only:
        statement = statement.where(VenueInstrument.is_active)
    return (await session.scalars(statement)).all()


@router.post(
    "/venues/{venue_id}/instruments",
    response_model=InstrumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_instrument(
    venue_id: int,
    request: InstrumentWrite,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> VenueInstrument:
    """Add executable order rules for an existing venue and logical pair."""
    venue = await get_or_404(session, Venue, venue_id)
    pair = await get_or_404(session, TradingPair, request.pair_id)
    settlement = (
        await get_or_404(session, Asset, request.settlement_asset_id)
        if request.settlement_asset_id is not None
        else None
    )
    instrument = VenueInstrument(
        venue=venue,
        pair=pair,
        settlement_asset=settlement,
        **request.model_dump(exclude={"pair_id", "settlement_asset_id"}),
    )
    session.add(instrument)
    await flush_or_conflict(session, "Venue instrument is already in use")
    return await get_or_404(
        session,
        VenueInstrument,
        instrument.id,
        instrument_options(),
    )


@router.patch(
    "/instruments/{instrument_id}", response_model=InstrumentResponse
)
async def update_instrument(
    instrument_id: int,
    request: InstrumentPatch,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> VenueInstrument:
    """Update venue execution parameters without deleting historical identity."""
    instrument = await get_or_404(
        session,
        VenueInstrument,
        instrument_id,
        instrument_options(),
    )
    values = request.model_dump(exclude_unset=True)
    identity_changed = any(
        field in values and values[field] != getattr(instrument, field)
        for field in ("product", "settlement_asset_id", "exec_symbol")
    )
    references = (
        select(Trade.id)
        .where(
            Trade.venue_instrument_id == instrument_id,
        )
        .limit(1)
    )
    if identity_changed and await session.scalar(references) is not None:
        conflict("Traded instrument identity cannot be changed")
    if "settlement_asset_id" in values:
        identifier = values.pop("settlement_asset_id")
        instrument.settlement_asset = (
            await get_or_404(session, Asset, identifier)
            if identifier is not None
            else None
        )
    for field, value in values.items():
        setattr(instrument, field, value)
    await flush_or_conflict(session, "Venue instrument is already in use")
    return await get_or_404(
        session,
        VenueInstrument,
        instrument.id,
        instrument_options(),
    )


@router.get(
    "/venues/{venue_id}/wallet-assets",
    response_model=list[VenueWalletAssetResponse],
)
async def list_venue_wallet_assets(
    venue_id: int,
    session: SessionDependency,
    active_only: bool = True,
) -> Sequence[VenueWalletAsset]:
    """List assets that can be held in a wallet on the selected venue."""
    await get_or_404(session, Venue, venue_id)
    statement = (
        select(VenueWalletAsset)
        .where(VenueWalletAsset.venue_id == venue_id)
        .options(selectinload(VenueWalletAsset.asset))
        .order_by(VenueWalletAsset.asset_id)
    )
    if active_only:
        statement = statement.where(VenueWalletAsset.is_active)
    return (await session.scalars(statement)).all()


@router.post(
    "/venues/{venue_id}/wallet-assets",
    response_model=VenueWalletAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_venue_wallet_asset(
    venue_id: int,
    request: VenueWalletAssetWrite,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> VenueWalletAsset:
    """Mark an existing asset as wallet-capable for a venue."""
    venue = await get_or_404(session, Venue, venue_id)
    asset = await get_or_404(session, Asset, request.asset_id)
    capability = VenueWalletAsset(
        venue=venue,
        asset=asset,
        is_active=request.is_active,
    )
    session.add(capability)
    await flush_or_conflict(session, "Venue wallet asset is already in use")
    return await get_or_404(
        session,
        VenueWalletAsset,
        capability.id,
        (selectinload(VenueWalletAsset.asset),),
    )


@router.patch(
    "/wallet-assets/{venue_wallet_asset_id}",
    response_model=VenueWalletAssetResponse,
)
async def update_venue_wallet_asset(
    venue_wallet_asset_id: int,
    request: VenueWalletAssetPatch,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> VenueWalletAsset:
    """Enable or archive a venue settlement capability without deleting it."""
    capability = await get_or_404(
        session,
        VenueWalletAsset,
        venue_wallet_asset_id,
        (selectinload(VenueWalletAsset.asset),),
    )
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(capability, field, value)
    await session.flush()
    return capability
