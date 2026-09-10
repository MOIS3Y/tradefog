"""Owner-scoped profile, wallet, ledger and strategy endpoints."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.errors import api_error, conflict, not_found
from tradefog.api.v1.schemas.journal import (
    ProfileCreate,
    ProfilePatch,
    ProfileResponse,
    StrategyCapitalCreate,
    StrategyCapitalPatch,
    StrategyCapitalResponse,
    StrategyCreate,
    StrategyPatch,
    StrategyResponse,
    WalletAssetCreate,
    WalletAssetPatch,
    WalletAssetResponse,
    WalletOperationCreate,
    WalletOperationPatch,
    WalletOperationResponse,
    WalletResponse,
)
from tradefog.api.v1.schemas.pagination import ListQuery, Page
from tradefog.db.models import (
    StrategyCapital,
    Trade,
    TradeSnapshot,
    TradingAsset,
    TradingInstrument,
    TradingProfile,
    TradingStrategy,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.capital import wallet_asset_status
from tradefog.domain.enums import StrategyStatus
from tradefog.services.journal import (
    allocated_capital,
    get_owned,
    recompute_strategy,
    recompute_wallet_asset,
    record_wallet_operation,
    wallet_balance,
    wallet_reserved,
)
from tradefog.services.pagination import paginate, search_text

router = APIRouter(prefix="/profiles", tags=["Journal"])


async def flush_unique(session: SessionDependency, message: str) -> None:
    """Expose owner-scoped uniqueness conflicts without leaking internals."""
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        conflict(message)


async def wallet_asset_response(
    session: SessionDependency,
    item: WalletAsset,
) -> WalletAssetResponse:
    """Build a wallet asset response with exact derived financial values."""
    capability = await session.get(TradingAsset, item.asset_id)
    if capability is None:
        not_found("TradingAsset")
    balance = await wallet_balance(session, item)
    allocated = await allocated_capital(session, item)
    reserved = await wallet_reserved(session, item)
    return WalletAssetResponse(
        id=item.id,
        asset_id=item.asset_id,
        symbol=capability.symbol,
        balance=balance,
        allocated=allocated,
        reserved=reserved,
        available=balance - reserved,
        uncommitted=balance - max(allocated, reserved),
        risk_stop_capital=item.risk_stop_capital,
        status=item.status,
        is_archived=item.is_archived,
    )


async def strategy_response(
    session: SessionDependency,
    strategy: TradingStrategy,
    owner_id: int,
) -> StrategyResponse:
    """Build a strategy response with every persisted allocation."""
    allocations = (
        await session.scalars(
            owned_select(StrategyCapital, owner_id)
            .where(StrategyCapital.strategy_id == strategy.id)
            .order_by(StrategyCapital.id)
        )
    ).all()
    return StrategyResponse(
        id=strategy.id,
        profile_id=strategy.profile_id,
        name=strategy.name,
        description=strategy.description,
        risk_percent=strategy.risk_percent,
        reward_multiple=int(strategy.reward_multiple),
        status=strategy.status,
        is_archived=strategy.is_archived,
        allocations=[
            StrategyCapitalResponse.model_validate(item)
            for item in allocations
        ],
    )


async def allocation_has_snapshot(
    session: SessionDependency,
    allocation: StrategyCapital,
) -> bool:
    """Return whether immutable history has locked allocation capital."""
    statement = (
        select(TradeSnapshot.id)
        .where(
            TradeSnapshot.strategy_capital_id == allocation.id,
        )
        .limit(1)
    )
    return await session.scalar(statement) is not None


@router.get("", response_model=Page[ProfileResponse])
async def list_profiles(
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[ProfileResponse]:
    """Search and page only the authenticated user's trading profiles."""
    statement = owned_select(TradingProfile, user.id)
    if query.visibility != "all":
        statement = statement.where(
            TradingProfile.is_archived.is_(query.visibility == "archived")
        )
    if query.q.strip():
        statement = statement.where(
            search_text([TradingProfile.name]).icontains(
                query.q.strip(), autoescape=True
            )
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {"name": TradingProfile.name},
        "name",
        TradingProfile.id,
    )
    return Page(
        items=[ProfileResponse.model_validate(item) for item in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    request: ProfileCreate,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingProfile:
    """Create a profile and its required one-to-one wallet atomically."""
    profile = TradingProfile(
        owner_id=user.id,
        venue_type=request.venue_type,
        name=request.name,
        description=request.description,
    )
    session.add(profile)
    await session.flush()
    session.add(Wallet(profile_id=profile.id))
    await session.flush()
    return profile


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingProfile:
    """Return one profile without exposing another owner's identifiers."""
    return await get_owned(
        session,
        TradingProfile,
        profile_id,
        user.id,
    )


@router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: int,
    request: ProfilePatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradingProfile:
    """Edit profile metadata or toggle its archive state."""
    profile = await get_owned(
        session,
        TradingProfile,
        profile_id,
        user.id,
        for_update=True,
    )
    values = request.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(profile, field, value)
    await session.flush()
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> Response:
    """Permanently remove an archived profile that has no journal history."""
    profile = await get_owned(
        session,
        TradingProfile,
        profile_id,
        user.id,
        for_update=True,
    )
    if not profile.is_archived:
        conflict("Only an archived profile can be deleted")
    has_history = await session.scalar(
        select(Trade.id).where(Trade.profile_id == profile.id).limit(1)
    )
    has_strategies = await session.scalar(
        select(TradingStrategy.id)
        .where(TradingStrategy.profile_id == profile.id)
        .limit(1)
    )
    wallet = await session.scalar(
        select(Wallet).where(Wallet.profile_id == profile.id)
    )
    if has_history is not None or has_strategies is not None:
        conflict("A profile with journal history cannot be deleted")
    if wallet is not None:
        asset_ids = select(WalletAsset.id).where(
            WalletAsset.wallet_id == wallet.id,
        )
        has_operations = await session.scalar(
            select(WalletOperation.id)
            .where(WalletOperation.wallet_asset_id.in_(asset_ids))
            .limit(1)
        )
        if has_operations is not None:
            conflict("A profile with wallet history cannot be deleted")
        await session.execute(
            delete(WalletAsset).where(WalletAsset.wallet_id == wallet.id)
        )
        await session.delete(wallet)
    await session.execute(
        delete(TradingInstrument).where(
            TradingInstrument.profile_id == profile.id
        )
    )
    await session.execute(
        delete(TradingAsset).where(TradingAsset.profile_id == profile.id)
    )
    await session.delete(profile)
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{profile_id}/wallet", response_model=WalletResponse)
async def get_wallet(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    include_archived: bool = False,
) -> WalletResponse:
    """Return the profile wallet with derived balances and reservations."""
    profile = await get_owned(
        session,
        TradingProfile,
        profile_id,
        user.id,
    )
    wallet = await session.scalar(
        owned_select(Wallet, user.id).where(Wallet.profile_id == profile.id)
    )
    if wallet is None:
        not_found("Wallet")
    statement = (
        owned_select(WalletAsset, user.id)
        .where(
            WalletAsset.wallet_id == wallet.id,
        )
        .order_by(WalletAsset.id)
    )
    if not include_archived:
        statement = statement.where(WalletAsset.is_archived.is_(False))
    items = (await session.scalars(statement)).all()
    return WalletResponse(
        id=wallet.id,
        profile_id=profile.id,
        assets=[await wallet_asset_response(session, item) for item in items],
    )


@router.post(
    "/{profile_id}/wallet/assets",
    response_model=WalletAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_wallet_asset(
    profile_id: int,
    request: WalletAssetCreate,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> WalletAssetResponse:
    """Add an active asset capability belonging to the profile venue."""
    profile = await get_owned(
        session,
        TradingProfile,
        profile_id,
        user.id,
        for_update=True,
    )
    if profile.is_archived:
        conflict("Archived profiles cannot accept new wallet assets")
    capability = await session.get(
        TradingAsset,
        request.asset_id,
    )
    if (
        capability is None
        or not capability.is_active
        or capability.profile_id != profile.id
    ):
        api_error(
            422,
            "invalid_wallet_asset",
            "Asset must be active on the profile venue",
        )
    wallet = await session.scalar(
        owned_select(Wallet, user.id).where(Wallet.profile_id == profile.id)
    )
    if wallet is None:
        not_found("Wallet")
    item = WalletAsset(
        wallet_id=wallet.id,
        asset_id=capability.id,
        risk_stop_capital=request.risk_stop_capital,
        status=wallet_asset_status(Decimal(0), request.risk_stop_capital),
    )
    session.add(item)
    await flush_unique(session, "Wallet asset is already present")
    return await wallet_asset_response(session, item)


@router.patch(
    "/{profile_id}/wallet/assets/{wallet_asset_id}",
    response_model=WalletAssetResponse,
)
async def update_wallet_asset(
    profile_id: int,
    wallet_asset_id: int,
    request: WalletAssetPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> WalletAssetResponse:
    """Edit a risk floor or archive an unused zero-balance wallet asset."""
    item = await get_owned(
        session,
        WalletAsset,
        wallet_asset_id,
        user.id,
        for_update=True,
    )
    await require_wallet_profile(session, item, profile_id)
    values = request.model_dump(exclude_unset=True)
    if values.get("is_archived") is False and item.is_archived:
        wallet = await session.get(Wallet, item.wallet_id)
        capability = await session.get(
            TradingAsset,
            item.asset_id,
        )
        profile = (
            await get_owned(
                session,
                TradingProfile,
                wallet.profile_id,
                user.id,
            )
            if wallet is not None
            else None
        )
        if (
            profile is None
            or profile.is_archived
            or capability is None
            or not capability.is_active
        ):
            conflict("A wallet asset requires active profile capability")
    if values.get("is_archived") is True:
        balance = await wallet_balance(session, item)
        reserved = await wallet_reserved(session, item)
        active_allocations = await session.scalar(
            select(func.count())
            .select_from(StrategyCapital)
            .where(
                StrategyCapital.wallet_asset_id == item.id,
                StrategyCapital.is_archived.is_(False),
            )
        )
        if balance != 0 or reserved != 0 or active_allocations:
            conflict(
                "Only an unused zero-balance wallet asset can be archived"
            )
    for field, value in values.items():
        setattr(item, field, value)
    await recompute_wallet_asset(session, item)
    await session.flush()
    return await wallet_asset_response(session, item)


@router.get(
    "/{profile_id}/wallet/operations",
    response_model=Page[WalletOperationResponse],
)
async def list_wallet_operations(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[WalletOperationResponse]:
    """List immutable ledger facts for one owned wallet asset."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    statement = owned_select(WalletOperation, user.id).where(
        WalletOperation.wallet_asset_id.in_(
            select(WalletAsset.id)
            .join(Wallet)
            .where(Wallet.profile_id == profile_id)
        ),
    )
    total = await session.scalar(
        select(func.count()).select_from(statement.subquery()),
    )
    items = await session.scalars(
        statement.order_by(
            WalletOperation.created_at.desc(),
            WalletOperation.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    return Page(
        items=[WalletOperationResponse.model_validate(item) for item in items],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{profile_id}/wallet/operations",
    response_model=WalletOperationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_wallet_operation(
    profile_id: int,
    request: WalletOperationCreate,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> WalletOperation:
    """Append a deposit or withdrawal to an active wallet asset."""
    item = await get_owned(
        session,
        WalletAsset,
        request.wallet_asset_id,
        user.id,
        for_update=True,
    )
    await require_wallet_profile(session, item, profile_id)
    if item.is_archived:
        conflict("Archived wallet assets cannot accept operations")
    wallet = await session.get(Wallet, item.wallet_id)
    profile = (
        await get_owned(
            session,
            TradingProfile,
            wallet.profile_id,
            user.id,
        )
        if wallet is not None
        else None
    )
    if profile is None or profile.is_archived:
        conflict("Archived profiles cannot accept wallet operations")
    return await record_wallet_operation(
        session,
        item,
        request.kind,
        request.amount,
        request.note,
    )


@router.patch(
    "/{profile_id}/wallet/operations/{operation_id}",
    response_model=WalletOperationResponse,
)
async def update_wallet_operation_note(
    profile_id: int,
    operation_id: int,
    request: WalletOperationPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> WalletOperation:
    """Correct an operation note without changing its financial fact."""
    operation = await get_owned(
        session,
        WalletOperation,
        operation_id,
        user.id,
        for_update=True,
    )
    item = await get_owned(
        session, WalletAsset, operation.wallet_asset_id, user.id
    )
    await require_wallet_profile(session, item, profile_id)
    operation.note = request.note
    await session.flush()
    return operation


@router.get("/{profile_id}/strategies", response_model=Page[StrategyResponse])
async def list_strategies(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[StrategyResponse]:
    """Search and page strategies before loading their allocations."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    statement = owned_select(TradingStrategy, user.id).where(
        TradingStrategy.profile_id == profile_id
    )
    if query.visibility != "all":
        statement = statement.where(
            TradingStrategy.is_archived.is_(query.visibility == "archived")
        )
    if query.q.strip():
        statement = statement.where(
            TradingStrategy.name.icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {"name": TradingStrategy.name},
        "name",
        TradingStrategy.id,
    )
    return Page(
        items=[
            await strategy_response(session, item, user.id) for item in items
        ],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.post(
    "/{profile_id}/strategies",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_strategy(
    profile_id: int,
    request: StrategyCreate,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> StrategyResponse:
    """Create reusable risk and reward rules inside an active profile."""
    profile = await get_owned(
        session,
        TradingProfile,
        profile_id,
        user.id,
        for_update=True,
    )
    if profile.is_archived:
        conflict("Archived profiles cannot accept new strategies")
    strategy = TradingStrategy(
        profile_id=profile.id,
        name=request.name,
        description=request.description,
        risk_percent=request.risk_percent,
        reward_multiple=Decimal(request.reward_multiple),
        status=StrategyStatus.ACTIVE,
    )
    session.add(strategy)
    await session.flush()
    return await strategy_response(session, strategy, user.id)


@router.patch(
    "/{profile_id}/strategies/{strategy_id}", response_model=StrategyResponse
)
async def update_strategy(
    profile_id: int,
    strategy_id: int,
    request: StrategyPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> StrategyResponse:
    """Edit strategy rules while preserving frozen snapshot history."""
    strategy = await session.scalar(
        owned_select(TradingStrategy, user.id)
        .where(TradingStrategy.id == strategy_id)
        .options(selectinload(TradingStrategy.profile))
        .with_for_update()
    )
    if strategy is None or strategy.profile_id != profile_id:
        not_found("TradingStrategy")
    values = request.model_dump(exclude_unset=True)
    rule_fields = {"risk_percent", "reward_multiple"}
    rules_changed = any(
        field in values and values[field] != getattr(strategy, field)
        for field in rule_fields
    )
    if rules_changed:
        has_submitted = await session.scalar(
            select(TradeSnapshot.id)
            .join(Trade, Trade.id == TradeSnapshot.trade_id)
            .where(Trade.strategy_id == strategy.id)
            .limit(1)
        )
        if has_submitted is not None:
            conflict("Risk rules are locked after the first submitted trade")
    if (
        values.get("is_archived") is False
        and strategy.is_archived
        and strategy.profile.is_archived
    ):
        conflict("A strategy requires an active profile")
    if values.get("is_archived") is True and not strategy.is_archived:
        active_allocations = await session.scalar(
            select(func.count())
            .select_from(StrategyCapital)
            .where(
                StrategyCapital.strategy_id == strategy.id,
                StrategyCapital.is_archived.is_(False),
            )
        )
        if active_allocations:
            conflict("Archive strategy allocations before the strategy")
    for field, value in values.items():
        if field == "reward_multiple":
            value = Decimal(value)
        setattr(strategy, field, value)
    await session.flush()
    return await strategy_response(session, strategy, user.id)


@router.delete(
    "/{profile_id}/strategies/{strategy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_strategy(
    profile_id: int,
    strategy_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> Response:
    """Delete an archived strategy that has no trade history."""
    strategy = await get_owned(
        session,
        TradingStrategy,
        strategy_id,
        user.id,
        for_update=True,
    )
    if strategy.profile_id != profile_id:
        not_found("TradingStrategy")
    if not strategy.is_archived:
        conflict("Only an archived strategy can be deleted")
    if (
        await session.scalar(
            select(Trade.id).where(Trade.strategy_id == strategy.id).limit(1)
        )
        is not None
    ):
        conflict("A strategy with trade history cannot be deleted")
    await session.execute(
        delete(StrategyCapital).where(
            StrategyCapital.strategy_id == strategy.id,
        )
    )
    await session.delete(strategy)
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{profile_id}/strategies/{strategy_id}/allocations",
    response_model=StrategyCapitalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_allocation(
    profile_id: int,
    strategy_id: int,
    request: StrategyCapitalCreate,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> StrategyCapital:
    """Allocate available wallet capital to an active strategy."""
    strategy = await get_owned(
        session,
        TradingStrategy,
        strategy_id,
        user.id,
        for_update=True,
    )
    if strategy.profile_id != profile_id:
        not_found("TradingStrategy")
    wallet_asset = await get_owned(
        session,
        WalletAsset,
        request.wallet_asset_id,
        user.id,
        for_update=True,
    )
    profile_wallet = await session.scalar(
        select(Wallet.id).where(
            Wallet.id == wallet_asset.wallet_id,
            Wallet.profile_id == strategy.profile_id,
        )
    )
    if profile_wallet is None:
        conflict("Allocation asset must belong to the strategy profile")
    profile = await get_owned(
        session,
        TradingProfile,
        strategy.profile_id,
        user.id,
    )
    capability = await session.get(
        TradingAsset,
        wallet_asset.asset_id,
    )
    if (
        profile.is_archived
        or strategy.is_archived
        or wallet_asset.is_archived
        or capability is None
        or not capability.is_active
    ):
        conflict("Archived records cannot accept new allocations")
    balance = await wallet_balance(session, wallet_asset)
    allocated = sum(
        (
            await session.scalars(
                select(StrategyCapital.capital).where(
                    StrategyCapital.wallet_asset_id == wallet_asset.id,
                    StrategyCapital.is_archived.is_(False),
                )
            )
        ).all(),
        Decimal(0),
    )
    if allocated + request.capital > balance:
        conflict("Allocation exceeds wallet asset balance")
    allocation = StrategyCapital(
        strategy_id=strategy.id,
        wallet_asset_id=wallet_asset.id,
        capital=request.capital,
    )
    session.add(allocation)
    await flush_unique(session, "Strategy already allocates this wallet asset")
    await recompute_wallet_asset(session, wallet_asset)
    return allocation


@router.patch(
    "/{profile_id}/strategies/{strategy_id}/allocations/{allocation_id}",
    response_model=StrategyCapitalResponse,
)
async def update_allocation(
    profile_id: int,
    strategy_id: int,
    allocation_id: int,
    request: StrategyCapitalPatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> StrategyCapital:
    """Edit unlocked capital or archive a strategy allocation."""
    allocation = await get_owned(
        session,
        StrategyCapital,
        allocation_id,
        user.id,
        for_update=True,
    )
    parent = await get_owned(
        session, TradingStrategy, allocation.strategy_id, user.id
    )
    if parent.profile_id != profile_id or parent.id != strategy_id:
        not_found("StrategyCapital")
    values = request.model_dump(exclude_unset=True)
    capital_changed = (
        "capital" in values and values["capital"] != allocation.capital
    )
    reactivated = values.get("is_archived") is False and allocation.is_archived
    if capital_changed and await allocation_has_snapshot(session, allocation):
        conflict("Allocation capital is locked by submitted trade history")
    if capital_changed or reactivated:
        wallet_asset = await get_owned(
            session,
            WalletAsset,
            allocation.wallet_asset_id,
            user.id,
        )
        strategy = await get_owned(
            session,
            TradingStrategy,
            allocation.strategy_id,
            user.id,
        )
        profile = await get_owned(
            session,
            TradingProfile,
            strategy.profile_id,
            user.id,
        )
        capability = await session.get(
            TradingAsset,
            wallet_asset.asset_id,
        )
        if reactivated and (
            wallet_asset.is_archived
            or strategy.is_archived
            or profile.is_archived
            or capability is None
            or not capability.is_active
        ):
            conflict("An allocation requires active parent records")
        other = sum(
            (
                await session.scalars(
                    select(StrategyCapital.capital).where(
                        StrategyCapital.wallet_asset_id == wallet_asset.id,
                        StrategyCapital.is_archived.is_(False),
                        StrategyCapital.id != allocation.id,
                    )
                )
            ).all(),
            Decimal(0),
        )
        capital = values.get("capital", allocation.capital)
        if other + capital > await wallet_balance(
            session,
            wallet_asset,
        ):
            conflict("Allocation exceeds wallet asset balance")
    for field, value in values.items():
        setattr(allocation, field, value)
    wallet_asset = await get_owned(
        session,
        WalletAsset,
        allocation.wallet_asset_id,
        user.id,
    )
    await recompute_wallet_asset(session, wallet_asset)
    await recompute_strategy(session, allocation.strategy_id)
    await session.flush()
    return allocation


async def require_wallet_profile(
    session: SessionDependency, item: WalletAsset, profile_id: int
) -> None:
    """Reject a nested wallet identifier from a different profile."""
    wallet = await session.get(Wallet, item.wallet_id)
    if wallet is None or wallet.profile_id != profile_id:
        not_found("WalletAsset")


@router.get(
    "/{profile_id}/strategies/{strategy_id}", response_model=StrategyResponse
)
async def get_strategy(
    profile_id: int,
    strategy_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> StrategyResponse:
    """Return a strategy only within its owning profile."""
    item = await get_owned(session, TradingStrategy, strategy_id, user.id)
    if item.profile_id != profile_id:
        not_found("TradingStrategy")
    return await strategy_response(session, item, user.id)


@router.get(
    "/{profile_id}/strategies/{strategy_id}/allocations",
    response_model=Page[StrategyCapitalResponse],
)
async def list_allocations(
    profile_id: int,
    strategy_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[StrategyCapitalResponse]:
    """Page allocations within their exact owning strategy and profile."""
    await get_strategy(profile_id, strategy_id, session, user)
    statement = owned_select(StrategyCapital, user.id).where(
        StrategyCapital.strategy_id == strategy_id
    )
    if query.visibility != "all":
        statement = statement.where(
            StrategyCapital.is_archived.is_(query.visibility == "archived")
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {"id": StrategyCapital.id},
        "id",
        StrategyCapital.id,
    )
    return Page(
        items=[StrategyCapitalResponse.model_validate(item) for item in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get(
    "/{profile_id}/wallet/assets", response_model=Page[WalletAssetResponse]
)
async def list_wallet_assets(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[ListQuery, Query()],
) -> Page[WalletAssetResponse]:
    """Search and page owned wallet denominations independently."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    statement = (
        owned_select(WalletAsset, user.id)
        .join(Wallet)
        .join(TradingAsset, TradingAsset.id == WalletAsset.asset_id)
        .where(Wallet.profile_id == profile_id)
    )
    if query.visibility != "all":
        statement = statement.where(
            WalletAsset.is_archived.is_(query.visibility == "archived")
        )
    if query.q.strip():
        statement = statement.where(
            TradingAsset.symbol.icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {"symbol": TradingAsset.symbol},
        "symbol",
        WalletAsset.id,
    )
    return Page(
        items=[await wallet_asset_response(session, item) for item in items],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
