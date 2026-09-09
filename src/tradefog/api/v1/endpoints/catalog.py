"""Public reference-catalog reads and staff-only catalog maintenance."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
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
from tradefog.api.v1.schemas.pagination import ListQuery, Page
from tradefog.db.models import (
    Asset,
    Trade,
    TradingPair,
    TradingProfile,
    Venue,
    VenueInstrument,
    VenueWalletAsset,
    WalletAsset,
)
from tradefog.services.pagination import paginate, search_text

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


@router.get("/assets", response_model=Page[AssetResponse])
async def list_assets(
    session: SessionDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[AssetResponse]:
    """List globally reusable assets, optionally filtered by their type."""
    statement = select(Asset).order_by(Asset.symbol)
    if query.asset_type is not None:
        statement = statement.where(Asset.asset_type == query.asset_type)
    if query.exclude_venue_id is not None:
        statement = statement.where(
            ~Asset.id.in_(
                select(VenueWalletAsset.asset_id).where(
                    VenueWalletAsset.venue_id == query.exclude_venue_id,
                ),
            )
        )
    if query.q.strip():
        statement = statement.where(
            search_text(
                [
                    Asset.symbol,
                    Asset.name,
                ]
            ).icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "symbol": Asset.symbol,
            "name": Asset.name,
            "asset_type": Asset.asset_type,
        },
        "symbol",
        Asset.id,
    )
    return Page(
        items=[AssetResponse.model_validate(x) for x in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


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


@router.get("/pairs", response_model=Page[PairResponse])
async def list_pairs(
    session: SessionDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[PairResponse]:
    """List logical markets with their base and quote assets."""
    statement = (
        select(TradingPair)
        .options(*pair_options())
        .order_by(
            TradingPair.canonical_symbol,
        )
    )
    base, quote = aliased(Asset), aliased(Asset)
    statement = statement.join(base, TradingPair.base_id == base.id).join(
        quote,
        TradingPair.quote_id == quote.id,
    )
    if query.q.strip():
        statement = statement.where(
            search_text(
                [
                    TradingPair.canonical_symbol,
                    base.symbol,
                    base.name,
                    quote.symbol,
                    quote.name,
                ]
            ).icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "canonical_symbol": TradingPair.canonical_symbol,
            "base": base.symbol,
            "quote": quote.symbol,
            "type_relation": search_text([base.asset_type, quote.asset_type]),
        },
        "canonical_symbol",
        TradingPair.id,
    )
    return Page(
        items=[PairResponse.model_validate(x) for x in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


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


@router.get("/venues", response_model=Page[VenueResponse])
async def list_venues(
    session: SessionDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[VenueResponse]:
    """List venues with explicit visibility, search and ordering."""
    statement = select(Venue).order_by(Venue.name)
    if query.visibility != "all":
        statement = statement.where(
            Venue.is_active == (query.visibility == "active"),
        )
    if query.q.strip():
        statement = statement.where(
            search_text(
                [
                    Venue.name,
                    Venue.description,
                    Venue.market_data_provider,
                ]
            ).icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "name": Venue.name,
            "status": Venue.is_active,
        },
        "name",
        Venue.id,
    )
    return Page(
        items=[VenueResponse.model_validate(x) for x in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


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


@router.delete(
    "/venues/{venue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_venue(
    venue_id: int,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> None:
    """Delete an archived venue with no catalog or journal references."""
    venue = await get_or_404(session, Venue, venue_id)
    if venue.is_active:
        api_error(
            status.HTTP_409_CONFLICT,
            "venue_not_archived",
            "Venue must be archived before deletion",
        )
    references = (
        select(VenueInstrument.id).where(
            VenueInstrument.venue_id == venue_id,
        ),
        select(VenueWalletAsset.id).where(
            VenueWalletAsset.venue_id == venue_id,
        ),
        select(TradingProfile.id).where(
            TradingProfile.venue_id == venue_id,
        ),
    )
    for statement in references:
        if await session.scalar(statement.limit(1)) is not None:
            api_error(
                status.HTTP_409_CONFLICT,
                "venue_in_use",
                "Venue is in use and cannot be deleted",
            )
    await session.delete(venue)
    await flush_or_conflict(
        session,
        "Venue is in use and cannot be deleted",
        "venue_in_use",
    )


@router.get(
    "/venues/{venue_id}/instruments",
    response_model=Page[InstrumentResponse],
)
async def list_instruments(
    venue_id: int,
    session: SessionDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[InstrumentResponse]:
    """List executable products at a venue with their market identities."""
    await get_or_404(session, Venue, venue_id)
    return await instrument_page(session, query, venue_id)


@router.get("/instruments", response_model=Page[InstrumentResponse])
async def list_all_instruments(
    session: SessionDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[InstrumentResponse]:
    """Search instruments across venues without loading each venue list."""
    return await instrument_page(session, query)


async def instrument_page(
    session: SessionDependency,
    query: ListQuery,
    venue_id: int | None = None,
) -> Page[InstrumentResponse]:
    """Build a bounded instrument page for tables and option searches."""
    statement = (
        select(VenueInstrument)
        .options(*instrument_options())
        .order_by(VenueInstrument.exec_symbol, VenueInstrument.product)
    )
    statement = statement.join(TradingPair).outerjoin(
        Asset,
        VenueInstrument.settlement_asset_id == Asset.id,
    )
    if venue_id is not None:
        statement = statement.where(VenueInstrument.venue_id == venue_id)
    if query.venue_id is not None:
        statement = statement.where(VenueInstrument.venue_id == query.venue_id)
    if query.pair_id is not None:
        statement = statement.where(VenueInstrument.pair_id == query.pair_id)
    if query.product is not None:
        statement = statement.where(VenueInstrument.product == query.product)
    if query.visibility != "all":
        statement = statement.where(
            VenueInstrument.is_active == (query.visibility == "active"),
        )
    if query.q.strip():
        statement = statement.where(
            search_text(
                [
                    VenueInstrument.exec_symbol,
                    TradingPair.canonical_symbol,
                    VenueInstrument.product,
                    Asset.symbol,
                ]
            ).icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "exec_symbol": VenueInstrument.exec_symbol,
            "pair": TradingPair.canonical_symbol,
            "product": VenueInstrument.product,
            "settlement": Asset.symbol,
            "status": VenueInstrument.is_active,
        },
        "exec_symbol",
        VenueInstrument.id,
    )
    return Page(
        items=[InstrumentResponse.model_validate(x) for x in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


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


@router.get("/instruments/{instrument_id}", response_model=InstrumentResponse)
async def get_instrument(
    instrument_id: int,
    session: SessionDependency,
) -> VenueInstrument:
    """Resolve one instrument independently of catalog pagination."""
    return await get_or_404(
        session,
        VenueInstrument,
        instrument_id,
        instrument_options(),
    )


@router.delete(
    "/instruments/{instrument_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_instrument(
    instrument_id: int,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> None:
    """Delete an archived instrument that has never been used by a trade."""
    instrument = await get_or_404(session, VenueInstrument, instrument_id)
    if instrument.is_active:
        api_error(
            status.HTTP_409_CONFLICT,
            "instrument_not_archived",
            "Instrument must be archived before deletion",
        )
    reference = await session.scalar(
        select(Trade.id)
        .where(Trade.venue_instrument_id == instrument_id)
        .limit(1)
    )
    if reference is not None:
        api_error(
            status.HTTP_409_CONFLICT,
            "instrument_in_use",
            "Instrument is used by a trade and cannot be deleted",
        )
    await session.delete(instrument)
    await flush_or_conflict(
        session,
        "Instrument is used by a trade and cannot be deleted",
        "instrument_in_use",
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
    response_model=Page[VenueWalletAssetResponse],
)
async def list_venue_wallet_assets(
    venue_id: int,
    session: SessionDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[VenueWalletAssetResponse]:
    """List assets that can be held in a wallet on the selected venue."""
    await get_or_404(session, Venue, venue_id)
    statement = (
        select(VenueWalletAsset)
        .where(VenueWalletAsset.venue_id == venue_id)
        .options(selectinload(VenueWalletAsset.asset))
        .order_by(VenueWalletAsset.asset_id)
    )
    statement = statement.join(Asset)
    if query.exclude_ids:
        statement = statement.where(
            ~VenueWalletAsset.id.in_(query.exclude_ids)
        )
    if query.visibility != "all":
        statement = statement.where(
            VenueWalletAsset.is_active == (query.visibility == "active"),
        )
    if query.q.strip():
        statement = statement.where(
            search_text(
                [
                    Asset.symbol,
                    Asset.name,
                    Asset.asset_type,
                ]
            ).icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "symbol": Asset.symbol,
            "type": Asset.asset_type,
            "status": VenueWalletAsset.is_active,
        },
        "symbol",
        VenueWalletAsset.id,
    )
    return Page(
        items=[VenueWalletAssetResponse.model_validate(x) for x in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get(
    "/wallet-assets/{capability_id}", response_model=VenueWalletAssetResponse
)
async def get_wallet_capability(
    capability_id: int,
    session: SessionDependency,
) -> VenueWalletAsset:
    """Resolve a selected wallet capability independently of its page."""
    return await get_or_404(
        session,
        VenueWalletAsset,
        capability_id,
        (selectinload(VenueWalletAsset.asset),),
    )


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


@router.delete(
    "/wallet-assets/{venue_wallet_asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_venue_wallet_asset(
    venue_wallet_asset_id: int,
    session: SessionDependency,
    _staff: StaffUserDependency,
) -> None:
    """Delete an archived wallet capability absent from profile wallets."""
    capability = await get_or_404(
        session,
        VenueWalletAsset,
        venue_wallet_asset_id,
    )
    if capability.is_active:
        api_error(
            status.HTTP_409_CONFLICT,
            "wallet_asset_not_archived",
            "Wallet asset must be archived before deletion",
        )
    reference = await session.scalar(
        select(WalletAsset.id)
        .where(
            WalletAsset.venue_wallet_asset_id == venue_wallet_asset_id,
        )
        .limit(1)
    )
    if reference is not None:
        api_error(
            status.HTTP_409_CONFLICT,
            "wallet_asset_in_use",
            "Wallet asset is used by a profile and cannot be deleted",
        )
    await session.delete(capability)
    await flush_or_conflict(
        session,
        "Wallet asset is used by a profile and cannot be deleted",
        "wallet_asset_in_use",
    )
