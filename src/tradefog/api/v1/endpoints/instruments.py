"""Profile-scoped manual specifications and public Bybit imports."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement

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
    StrategyCapital,
    Trade,
    TradeReservation,
    TradeSnapshot,
    TradingAsset,
    TradingInstrument,
    TradingProfile,
    WalletOperation,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.enums import AssetType, ProductKind, VenueType
from tradefog.services.instruments import (
    apply_spec,
    ensure_asset,
    import_spec,
    validate_assets,
)
from tradefog.services.journal import (
    allocated_capital,
    get_owned,
    recompute_wallet_asset,
    wallet_balance,
    wallet_reserved,
)
from tradefog.services.pagination import paginate

router = APIRouter(
    prefix="/profiles/{profile_id}", tags=["Profile instruments"]
)


class InstrumentListQuery(ListQuery):
    """Filter selected instruments by their market product."""

    product: ProductKind | None = None


class AssetListQuery(ListQuery):
    """Filter empty account denominations before pagination."""

    hide_empty: bool = False
    asset_type: AssetType | None = None


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
    query: Annotated[AssetListQuery, Query()],
) -> Page[AssetResponse]:
    """List profile assets with current derived balances.

    Search q matches symbol; the supported sort key is symbol. hide_empty
    excludes assets without account history or references, rather than
    simply excluding every zero balance. visibility filters archive state,
    independently of the advisory financial status.
    """
    await get_owned(session, TradingProfile, profile_id, user.id)
    statement = owned_select(TradingAsset, user.id).where(
        TradingAsset.profile_id == profile_id
    )
    if query.hide_empty:
        statement = statement.where(asset_has_history())
    if query.asset_type is not None:
        statement = statement.where(
            TradingAsset.asset_type == query.asset_type
        )
    if query.q.strip():
        statement = statement.where(
            TradingAsset.symbol.icontains(query.q.strip(), autoescape=True)
        )
    if query.visibility != "all":
        statement = statement.where(
            TradingAsset.is_archived.is_(query.visibility == "archived")
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
        items=[await asset_response(session, i) for i in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def get_asset_record(
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
) -> AssetResponse:
    """Create an account denomination without funding it."""
    profile = await profile_record(profile_id, session, user)
    if profile.venue_type != VenueType.MANUAL:
        conflict("Bybit assets are created by importing instruments")
    item = TradingAsset(profile_id=profile_id, **request.model_dump())
    session.add(item)
    await flush_unique(session)
    return await asset_response(session, item)


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(
    profile_id: int,
    asset_id: int,
    request: AssetPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> AssetResponse:
    """Edit labels and local availability without changing historical identity."""
    await profile_record(profile_id, session, user)
    item = await get_asset_record(profile_id, asset_id, session, user)
    values = request.model_dump(exclude_unset=True)
    if values.get("is_archived"):
        used = await session.scalar(
            select(TradingInstrument.id)
            .where(
                instrument_uses(asset_id),
                TradingInstrument.is_archived.is_(False),
            )
            .limit(1)
        )
        allocated = await session.scalar(
            select(StrategyCapital.id)
            .where(
                StrategyCapital.asset_id == asset_id,
                StrategyCapital.is_archived.is_(False),
            )
            .limit(1)
        )
        if (
            await wallet_balance(session, item) != 0
            or await wallet_reserved(session, item) != 0
            or allocated is not None
            or used is not None
        ):
            conflict("Asset still has funds or active references")
    for field, value in values.items():
        setattr(item, field, value)
    await recompute_wallet_asset(session, item)
    await session.flush()
    return await asset_response(session, item)


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(
    profile_id: int,
    asset_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> None:
    """Remove only an inactive unreferenced asset."""
    item = await get_asset_record(profile_id, asset_id, session, user)
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
    history = await session.scalar(
        select(TradingAsset.id).where(
            TradingAsset.id == asset_id, asset_has_history()
        )
    )
    if not item.is_archived or used is not None or history is not None:
        conflict("Only archived unreferenced assets can be deleted")
    await session.delete(item)
    await session.flush()


@router.get("/instruments", response_model=Page[InstrumentResponse])
async def list_instruments(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[InstrumentListQuery, Query()],
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
    if query.product is not None:
        statement = statement.where(TradingInstrument.product == query.product)
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
        items=await instrument_responses(session, list(items)),
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
) -> InstrumentResponse:
    """Return an instrument with its current denomination types."""
    item = await get_instrument_record(
        profile_id, instrument_id, session, user
    )
    return (await instrument_responses(session, [item]))[0]


async def instrument_responses(
    session: SessionDependency,
    items: list[TradingInstrument],
) -> list[InstrumentResponse]:
    """Resolve denomination types in one query, without persisting copies."""
    if not items:
        return []
    ids = {id_ for i in items for id_ in (i.base_asset_id, i.quote_asset_id)}
    rows = await session.execute(
        select(TradingAsset.id, TradingAsset.asset_type).where(
            TradingAsset.id.in_(ids)
        )
    )
    types = dict(rows.tuples().all())
    fields = InstrumentResponse.model_fields.keys() - {
        "base_asset_type",
        "quote_asset_type",
    }
    return [
        InstrumentResponse(
            **{field: getattr(item, field) for field in fields},
            base_asset_type=types[item.base_asset_id],
            quote_asset_type=types[item.quote_asset_id],
        )
        for item in items
    ]


async def get_instrument_record(
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
) -> InstrumentResponse:
    """Import Bybit metadata or create a manual instrument specification.

    Request mode must match the profile venue (422, invalid_mode).
    Creation also resolves or creates the profile-local denomination
    assets. Duplicate identities return 409; browsing venue instruments
    alone does not import them into a profile.
    """
    profile = await profile_record(profile_id, session, user)
    if request.mode != profile.venue_type.value:
        api_error(422, "invalid_mode", "Request must match profile venue")
    try:
        if request.mode == "bybit":
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
                **assets,
            )
            apply_spec(item, spec)
            if not item.is_active:
                conflict("Instrument is not currently trading")
        else:
            if request.base.symbol == request.quote.symbol:
                api_error(
                    422, "invalid_denominations", "Base must differ from quote"
                )
            base = await ensure_asset(session, profile_id, request.base)
            quote = await ensure_asset(session, profile_id, request.quote)
            item = TradingInstrument(
                profile_id=profile_id,
                exec_symbol=f"{base.symbol}/{quote.symbol}",
                base_asset_id=base.id,
                quote_asset_id=quote.id,
                settlement_asset_id=quote.id,
                **request.model_dump(exclude={"mode", "base", "quote"}),
            )
        session.add(item)
        await session.flush()
    except IntegrityError:
        await session.rollback()
        conflict("Profile identity already exists; reload and retry")
    return (await instrument_responses(session, [item]))[0]


@router.patch(
    "/instruments/{instrument_id}", response_model=InstrumentResponse
)
async def update_instrument(
    profile_id: int,
    instrument_id: int,
    request: InstrumentPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> InstrumentResponse:
    """Keep exchange-owned rules read-only while allowing local archives."""
    profile = await profile_record(profile_id, session, user)
    item = await get_instrument_record(
        profile_id, instrument_id, session, user
    )
    values = request.model_dump(exclude_unset=True)
    if profile.venue_type == VenueType.BYBIT and values.keys() - {
        "is_archived",
    }:
        api_error(
            422,
            "automatic_metadata",
            "Refresh Bybit execution rules from the source",
        )
    if values.get("is_archived") is False:
        await validate_assets(
            session,
            profile_id,
            item.base_asset_id,
            item.quote_asset_id,
            item.settlement_asset_id,
        )
    for field, value in values.items():
        setattr(item, field, value)
    await session.flush()
    return (await instrument_responses(session, [item]))[0]


@router.post(
    "/instruments/{instrument_id}/refresh", response_model=InstrumentResponse
)
async def refresh_instrument(
    profile_id: int,
    instrument_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    market: MarketDependency,
) -> InstrumentResponse:
    """Update supported source metadata without repurposing the instrument."""
    profile = await profile_record(profile_id, session, user)
    item = await get_instrument_record(
        profile_id, instrument_id, session, user
    )
    spec, assets = await import_spec(
        session, profile, item.exec_symbol, item.product.value, market
    )
    if any(getattr(item, key) != value for key, value in assets.items()):
        conflict(
            "Exchange instrument identity changed; create a new instrument"
        )
    apply_spec(item, spec)
    await session.flush()
    return (await instrument_responses(session, [item]))[0]


@router.delete("/instruments/{instrument_id}", status_code=204)
async def delete_instrument(
    profile_id: int,
    instrument_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> None:
    """Delete only an archived instrument without trade history."""
    item = await get_instrument_record(
        profile_id, instrument_id, session, user
    )
    used = await session.scalar(
        select(Trade.id).where(Trade.instrument_id == item.id).limit(1)
    )
    if not item.is_archived or used is not None:
        conflict("Only archived unreferenced instruments can be deleted")
    await session.delete(item)
    await session.flush()


def instrument_uses(asset_id: int) -> ColumnElement[bool]:
    """Match any instrument denomination."""
    return or_(
        TradingInstrument.base_asset_id == asset_id,
        TradingInstrument.quote_asset_id == asset_id,
        TradingInstrument.settlement_asset_id == asset_id,
    )


def asset_has_history() -> ColumnElement[bool]:
    """Keep all ledger/history identities visible even at zero balance."""
    return or_(
        select(WalletOperation.id)
        .where(WalletOperation.asset_id == TradingAsset.id)
        .exists(),
        select(StrategyCapital.id)
        .where(StrategyCapital.asset_id == TradingAsset.id)
        .exists(),
        select(TradeReservation.id)
        .where(TradeReservation.asset_id == TradingAsset.id)
        .exists(),
        select(TradeSnapshot.id)
        .where(TradeSnapshot.settlement_asset_id == TradingAsset.id)
        .exists(),
        select(Trade.id)
        .join(TradingInstrument)
        .where(
            or_(
                TradingInstrument.base_asset_id == TradingAsset.id,
                TradingInstrument.quote_asset_id == TradingAsset.id,
                TradingInstrument.settlement_asset_id == TradingAsset.id,
            )
        )
        .exists(),
    )


async def asset_response(
    session: SessionDependency, item: TradingAsset
) -> AssetResponse:
    """Combine identity and exact, derived account values."""
    balance = await wallet_balance(session, item)
    reserved = await wallet_reserved(session, item)
    allocated = await allocated_capital(session, item)
    return AssetResponse(
        id=item.id,
        profile_id=item.profile_id,
        symbol=item.symbol,
        name=item.name,
        asset_type=item.asset_type,
        is_archived=item.is_archived,
        status=item.status,
        risk_stop_capital=item.risk_stop_capital,
        balance=balance,
        reserved=reserved,
        allocated=allocated,
        available=balance - reserved,
        uncommitted=balance - max(allocated, reserved),
    )


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(
    profile_id: int,
    asset_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> AssetResponse:
    """Resolve one profile asset with financial values."""
    return await asset_response(
        session, await get_asset_record(profile_id, asset_id, session, user)
    )
