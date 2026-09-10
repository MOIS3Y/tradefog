"""Profile-scoped manual specifications and public Bybit imports."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.errors import api_error, conflict, not_found
from tradefog.api.v1.endpoints.venues import MarketDependency
from tradefog.api.v1.schemas.instruments import (
    AssetPatch,
    AssetResponse,
    AssetWrite,
    InstrumentPatch,
    InstrumentResponse,
    InstrumentWrite,
)
from tradefog.api.v1.schemas.pagination import ListQuery, Page
from tradefog.db.models import (
    Trade,
    TradingAsset,
    TradingInstrument,
    TradingProfile,
    WalletAsset,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.enums import VenueType
from tradefog.services.instruments import (
    apply_spec,
    import_spec,
    validate_assets,
)
from tradefog.services.journal import get_owned
from tradefog.services.pagination import paginate

router = APIRouter(
    prefix="/profiles/{profile_id}", tags=["Profile instruments"]
)


async def profile_record(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingProfile:
    """Resolve a writable profile; archived profiles remain readable."""
    profile = await get_owned(session, TradingProfile, profile_id, user.id)
    if profile.is_archived:
        conflict("Profile is archived")
    return profile


async def flush_unique(session: SessionDependency) -> None:
    """Translate duplicate identities into a stable conflict."""
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        conflict("Profile identity already exists or is still referenced")


@router.get("/assets", response_model=Page[AssetResponse])
async def list_assets(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[AssetResponse]:
    """Search only assets belonging to the requested owned profile."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    statement = owned_select(TradingAsset, user.id).where(
        TradingAsset.profile_id == profile_id
    )
    if query.q.strip():
        statement = statement.where(
            TradingAsset.symbol.icontains(query.q.strip(), autoescape=True)
        )
    if query.visibility != "all":
        statement = statement.where(
            TradingAsset.is_active.is_(query.visibility != "archived")
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {"symbol": TradingAsset.symbol},
        "symbol",
        TradingAsset.id,
    )
    return Page(
        items=[AssetResponse.model_validate(i) for i in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(
    profile_id: int,
    asset_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingAsset:
    """Resolve an asset without exposing other profiles."""
    item = await get_owned(session, TradingAsset, asset_id, user.id)
    if item.profile_id != profile_id:
        not_found("TradingAsset")
    return item


@router.post("/assets", response_model=AssetResponse, status_code=201)
async def create_asset(
    profile_id: int,
    request: AssetWrite,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingAsset:
    """Create manual metadata, never a virtual balance."""
    profile = await profile_record(profile_id, session, user)
    if profile.venue_type != VenueType.MANUAL:
        api_error(
            422,
            "automatic_metadata",
            "Bybit assets are imported with instruments",
        )
    item = TradingAsset(profile_id=profile_id, **request.model_dump())
    session.add(item)
    await flush_unique(session)
    return item


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(
    profile_id: int,
    asset_id: int,
    request: AssetPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingAsset:
    """Edit labels and local availability without changing historical identity."""
    await profile_record(profile_id, session, user)
    item = await get_asset(profile_id, asset_id, session, user)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await session.flush()
    return item


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(
    profile_id: int,
    asset_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> None:
    """Remove only an inactive unreferenced asset."""
    item = await get_asset(profile_id, asset_id, session, user)
    used = await session.scalar(
        select(TradingInstrument.id)
        .where(
            or_(
                TradingInstrument.base_asset_id == asset_id,
                TradingInstrument.quote_asset_id == asset_id,
                TradingInstrument.settlement_asset_id == asset_id,
            )
        )
        .limit(1)
    )
    wallet = await session.scalar(
        select(WalletAsset.id).where(WalletAsset.asset_id == asset_id).limit(1)
    )
    if item.is_active or used is not None or wallet is not None:
        conflict("Only inactive unreferenced assets can be deleted")
    await session.delete(item)
    await session.flush()


@router.get("/instruments", response_model=Page[InstrumentResponse])
async def list_instruments(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[InstrumentResponse]:
    """Page selected instruments, never the whole exchange catalog."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    statement = owned_select(TradingInstrument, user.id).where(
        TradingInstrument.profile_id == profile_id
    )
    if query.visibility != "all":
        statement = statement.where(
            TradingInstrument.is_archived.is_(query.visibility == "archived")
        )
    if query.q.strip():
        statement = statement.where(
            TradingInstrument.exec_symbol.icontains(
                query.q.strip(), autoescape=True
            )
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "symbol": TradingInstrument.exec_symbol,
            "product": TradingInstrument.product,
        },
        "symbol",
        TradingInstrument.id,
    )
    return Page(
        items=[InstrumentResponse.model_validate(i) for i in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get("/instruments/{instrument_id}", response_model=InstrumentResponse)
async def get_instrument(
    profile_id: int,
    instrument_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingInstrument:
    """Resolve an instrument within its exact profile."""
    item = await get_owned(session, TradingInstrument, instrument_id, user.id)
    if item.profile_id != profile_id:
        not_found("TradingInstrument")
    return item


@router.post(
    "/instruments", response_model=InstrumentResponse, status_code=201
)
async def create_instrument(
    profile_id: int,
    request: InstrumentWrite,
    session: SessionDependency,
    user: CurrentUserDependency,
    market: MarketDependency,
) -> TradingInstrument:
    """Import Bybit metadata or validate an explicit manual specification."""
    profile = await profile_record(profile_id, session, user)
    values = request.model_dump()
    if profile.venue_type == VenueType.BYBIT:
        if request.model_fields_set - {"exec_symbol", "product", "name"}:
            api_error(
                422,
                "automatic_metadata",
                "Bybit specifications cannot be supplied manually",
            )
        spec, assets = await import_spec(
            session,
            profile,
            request.exec_symbol,
            request.product.value,
            market,
        )
        item = TradingInstrument(
            profile_id=profile_id,
            exec_symbol=spec.symbol,
            product=request.product,
            name=request.name,
            **assets,
        )
        apply_spec(item, spec)
        if not item.is_active:
            conflict("Instrument is not currently trading")
    else:
        required = (
            "base_asset_id",
            "quote_asset_id",
            "settlement_asset_id",
            "price_step",
            "qty_step",
        )
        if any(values[field] is None for field in required):
            api_error(
                422,
                "missing_specification",
                "Manual instruments require assets and execution steps",
            )
        await validate_assets(
            session,
            profile_id,
            values["base_asset_id"],
            values["quote_asset_id"],
            values["settlement_asset_id"],
        )
        item = TradingInstrument(profile_id=profile_id, **values)
    session.add(item)
    await flush_unique(session)
    return item


@router.patch(
    "/instruments/{instrument_id}", response_model=InstrumentResponse
)
async def update_instrument(
    profile_id: int,
    instrument_id: int,
    request: InstrumentPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingInstrument:
    """Keep exchange-owned rules read-only while allowing local archives."""
    profile = await profile_record(profile_id, session, user)
    item = await get_instrument(profile_id, instrument_id, session, user)
    values = request.model_dump(exclude_unset=True)
    if profile.venue_type == VenueType.BYBIT and values.keys() - {
        "name",
        "is_archived",
    }:
        api_error(
            422,
            "automatic_metadata",
            "Refresh Bybit execution rules from the source",
        )
    for field, value in values.items():
        setattr(item, field, value)
    await session.flush()
    return item


@router.post(
    "/instruments/{instrument_id}/refresh", response_model=InstrumentResponse
)
async def refresh_instrument(
    profile_id: int,
    instrument_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    market: MarketDependency,
) -> TradingInstrument:
    """Update supported source metadata without repurposing the instrument."""
    profile = await profile_record(profile_id, session, user)
    item = await get_instrument(profile_id, instrument_id, session, user)
    spec, assets = await import_spec(
        session, profile, item.exec_symbol, item.product.value, market
    )
    if any(getattr(item, key) != value for key, value in assets.items()):
        conflict(
            "Exchange instrument identity changed; create a new instrument"
        )
    apply_spec(item, spec)
    await session.flush()
    return item


@router.delete("/instruments/{instrument_id}", status_code=204)
async def delete_instrument(
    profile_id: int,
    instrument_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> None:
    """Delete only an archived instrument without trade history."""
    item = await get_instrument(profile_id, instrument_id, session, user)
    used = await session.scalar(
        select(Trade.id).where(Trade.instrument_id == item.id).limit(1)
    )
    if not item.is_archived or used is not None:
        conflict("Only archived unreferenced instruments can be deleted")
    await session.delete(item)
    await session.flush()
