"""Focused state changes for assets, profiles, capital, pairs, and trades."""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tradefog.journal.calculations import (
    REWARD_MULTIPLE,
    PositionPlan,
    calculate_position_plan,
)
from tradefog.journal.models import (
    Asset,
    CapitalOperation,
    ProfileTradingPair,
    Trade,
    TradingProfile,
)

INSUFFICIENT_CAPITAL = _(
    "The operation would make the profile capital negative."
)
ZERO = Decimal(0)
RESULT_R_QUANTUM = Decimal("0.000000000000000000000001")
INVALID_TRADE_TRANSITION = _(
    "This action is not available for the trade's current status."
)


def sync_profile_status(profile: TradingProfile) -> str:
    """Persist the status derived from the profile's financial facts."""
    calculated_status = profile.calculated_status
    if profile.status != calculated_status:
        profile.status = calculated_status
        profile.save(update_fields=["status", "updated_at"])
    return calculated_status


def archive_profile(profile: TradingProfile) -> None:
    """Archive a profile while retaining its journal configuration."""
    if profile.status == TradingProfile.Status.ARCHIVED.value:
        return
    profile.status = TradingProfile.Status.ARCHIVED.value
    profile.archived_at = timezone.now()
    profile.save(update_fields=["status", "archived_at", "updated_at"])


def restore_profile(profile: TradingProfile) -> None:
    """Restore a profile and derive its current financial status."""
    if profile.status != TradingProfile.Status.ARCHIVED.value:
        return
    profile.status = TradingProfile.Status.ACTIVE.value
    profile.archived_at = None
    profile.status = profile.calculated_status
    profile.save(update_fields=["status", "archived_at", "updated_at"])


def _projected_capital(
    profile: TradingProfile,
    *,
    removed_amount: Decimal = ZERO,
    added_amount: Decimal = ZERO,
) -> Decimal:
    """Return capital after replacing one signed operation contribution."""
    return profile.current_capital - removed_amount + added_amount


def _validate_projected_capital(
    current_capital: Decimal,
    projected_capital: Decimal,
) -> None:
    """Reject an allocation change that creates or worsens capital debt."""
    if projected_capital < 0 and projected_capital < current_capital:
        raise ValidationError({"amount": INSUFFICIENT_CAPITAL})


@transaction.atomic
def create_capital_operation(
    profile: TradingProfile,
    *,
    operation_type: str,
    amount: Decimal,
    note: str = "",
) -> CapitalOperation:
    """Apply one explicit allocation change and synchronize profile state."""
    locked_profile = TradingProfile.objects.select_for_update().get(
        id=profile.id
    )
    operation = CapitalOperation(
        profile=locked_profile,
        operation_type=operation_type,
        amount=amount,
        note=note,
    )
    operation.full_clean()
    _validate_projected_capital(
        locked_profile.current_capital,
        _projected_capital(
            locked_profile,
            added_amount=operation.signed_amount,
        ),
    )
    operation.save()
    _ = sync_profile_status(locked_profile)
    profile.refresh_from_db()
    return operation


@transaction.atomic
def update_capital_operation(
    operation: CapitalOperation,
    *,
    amount: Decimal,
    note: str,
) -> CapitalOperation:
    """Correct an allocation fact without changing its type or timestamp."""
    locked_operation = (
        CapitalOperation.objects.select_for_update()
        .select_related("profile")
        .get(id=operation.id)
    )
    profile = TradingProfile.objects.select_for_update().get(
        id=locked_operation.profile.id
    )
    previous_amount = locked_operation.signed_amount
    locked_operation.amount = amount
    locked_operation.note = note
    locked_operation.full_clean()
    _validate_projected_capital(
        profile.current_capital,
        _projected_capital(
            profile,
            removed_amount=previous_amount,
            added_amount=locked_operation.signed_amount,
        ),
    )
    locked_operation.save(update_fields=["amount", "note", "updated_at"])
    _profile_status = sync_profile_status(profile)
    return locked_operation


@transaction.atomic
def delete_capital_operation(operation: CapitalOperation) -> None:
    """Remove an erroneous allocation fact when capital remains valid."""
    locked_operation = (
        CapitalOperation.objects.select_for_update()
        .select_related("profile")
        .get(id=operation.id)
    )
    profile = TradingProfile.objects.select_for_update().get(
        id=locked_operation.profile.id
    )
    _validate_projected_capital(
        profile.current_capital,
        _projected_capital(
            profile,
            removed_amount=locked_operation.signed_amount,
        ),
    )
    _ = locked_operation.delete()
    _profile_status = sync_profile_status(profile)


def archive_asset(asset: Asset) -> None:
    """Archive an asset without changing existing pair identities."""
    if asset.archived_at is not None:
        return
    asset.archived_at = timezone.now()
    asset.save(update_fields=["archived_at", "updated_at"])


def restore_asset(asset: Asset) -> None:
    """Restore an archived asset to owner selectors."""
    if asset.archived_at is None:
        return
    asset.archived_at = None
    asset.save(update_fields=["archived_at", "updated_at"])


def archive_trading_pair(trading_pair: ProfileTradingPair) -> None:
    """Archive a pair without deleting historical trade references."""
    if trading_pair.archived_at is not None:
        return
    trading_pair.archived_at = timezone.now()
    trading_pair.save(update_fields=["archived_at", "updated_at"])


def restore_trading_pair(trading_pair: ProfileTradingPair) -> bool:
    """Restore a pair unless the same active asset pair already exists."""
    if trading_pair.archived_at is None:
        return True
    try:
        with transaction.atomic():
            trading_pair.archived_at = None
            trading_pair.save(update_fields=["archived_at", "updated_at"])
    except IntegrityError:
        trading_pair.refresh_from_db()
        return False
    return True


def calculate_trade_plan(trade: Trade) -> PositionPlan:
    """Calculate a draft plan from the profile's current risk state."""
    return calculate_position_plan(
        direction=trade.direction,
        entry=trade.planned_entry,
        stop=trade.planned_stop,
        target_risk_amount=trade.profile.risk_amount,
        price_step=trade.trading_pair.price_step,
        quantity_step=trade.trading_pair.quantity_step,
        minimum_quantity=trade.trading_pair.minimum_quantity,
        minimum_notional=trade.trading_pair.minimum_notional,
    )


def _locked_trade(trade: Trade) -> tuple[TradingProfile, Trade]:
    """Lock a profile before one of its trades for consistent risk state."""
    profile = TradingProfile.objects.select_for_update().get(
        id=trade.profile_id
    )
    locked_trade = (
        Trade.objects.select_for_update()
        .select_related(
            "profile__capital_asset",
            "trading_pair__asset",
        )
        .get(id=trade.id, profile=profile)
    )
    return profile, locked_trade


def _snapshot_trade_plan(
    profile: TradingProfile,
    trade: Trade,
) -> None:
    """Persist the material risk context for a submitted decision."""
    plan = calculate_trade_plan(trade)
    current_capital = profile.current_capital
    reserved_risk = profile.reserved_risk
    post_trade_capacity = (
        current_capital
        - reserved_risk
        - plan.planned_risk_amount
        - profile.risk_stop_capital
    )
    trade.planned_take_profit = plan.take_profit
    trade.planned_quantity = plan.quantity
    trade.planned_risk_percent = profile.risk_per_trade_percent
    trade.planned_risk_amount = plan.planned_risk_amount
    trade.reward_multiple = REWARD_MULTIPLE
    trade.capital_snapshot = current_capital
    trade.risk_base_snapshot = profile.risk_base
    trade.risk_stop_snapshot = profile.risk_stop_capital
    trade.reserved_risk_snapshot = reserved_risk
    trade.risk_capacity_snapshot = post_trade_capacity
    trade.risk_limit_breached = post_trade_capacity <= 0
    trade.notional_limit_breached = plan.notional > current_capital


@transaction.atomic
def submit_trade(trade: Trade) -> Trade:
    """Freeze a draft plan and mark its manual order as pending entry."""
    profile, locked_trade = _locked_trade(trade)
    if locked_trade.status != Trade.Status.DRAFT.value:
        raise ValidationError(INVALID_TRADE_TRANSITION)
    _snapshot_trade_plan(profile, locked_trade)
    locked_trade.status = Trade.Status.PENDING_ENTRY.value
    locked_trade.submitted_at = timezone.now()
    locked_trade.full_clean()
    locked_trade.save()
    _profile_status = sync_profile_status(profile)
    return locked_trade


@transaction.atomic
def open_trade(trade: Trade) -> Trade:
    """Mark a pending manual order as filled without changing its snapshot."""
    profile, locked_trade = _locked_trade(trade)
    if locked_trade.status != Trade.Status.PENDING_ENTRY.value:
        raise ValidationError(INVALID_TRADE_TRANSITION)
    locked_trade.status = Trade.Status.OPEN.value
    locked_trade.filled_at = timezone.now()
    locked_trade.save(update_fields=["status", "filled_at", "updated_at"])
    _profile_status = sync_profile_status(profile)
    return locked_trade


@transaction.atomic
def cancel_trade(trade: Trade) -> Trade:
    """Cancel a draft or unfilled order and release any reserved risk."""
    profile, locked_trade = _locked_trade(trade)
    if locked_trade.status not in {
        Trade.Status.DRAFT.value,
        Trade.Status.PENDING_ENTRY.value,
    }:
        raise ValidationError(INVALID_TRADE_TRANSITION)
    locked_trade.status = Trade.Status.CANCELLED.value
    locked_trade.cancelled_at = timezone.now()
    locked_trade.save(update_fields=["status", "cancelled_at", "updated_at"])
    _profile_status = sync_profile_status(profile)
    return locked_trade


def _calculate_result_r(
    realized_pnl: Decimal,
    planned_risk: Decimal | None,
) -> Decimal:
    """Normalize one aggregate result against its frozen planned risk."""
    if planned_risk is None or planned_risk <= 0:
        raise ValidationError(_("The trade has no valid risk snapshot."))
    with localcontext() as context:
        context.prec = 96
        return (realized_pnl / planned_risk).quantize(
            RESULT_R_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


@transaction.atomic
def close_trade(
    trade: Trade,
    *,
    realized_pnl: Decimal,
    actual_exit_price: Decimal | None = None,
    commission_total: Decimal | None = None,
    funding_result: Decimal | None = None,
) -> Trade:
    """Close an open trade with one aggregate net realized result."""
    profile, locked_trade = _locked_trade(trade)
    if locked_trade.status != Trade.Status.OPEN.value:
        raise ValidationError(INVALID_TRADE_TRANSITION)
    locked_trade.status = Trade.Status.CLOSED.value
    locked_trade.realized_pnl = realized_pnl
    locked_trade.result_r = _calculate_result_r(
        realized_pnl,
        locked_trade.planned_risk_amount,
    )
    locked_trade.actual_exit_price = actual_exit_price
    locked_trade.commission_total = commission_total
    locked_trade.funding_result = funding_result
    locked_trade.closed_at = timezone.now()
    locked_trade.full_clean()
    locked_trade.save()
    _profile_status = sync_profile_status(profile)
    return locked_trade


@transaction.atomic
def update_trade_result(
    trade: Trade,
    *,
    realized_pnl: Decimal,
    actual_exit_price: Decimal | None = None,
    commission_total: Decimal | None = None,
    funding_result: Decimal | None = None,
) -> Trade:
    """Correct a closed trade result and recalculate current profile state."""
    profile, locked_trade = _locked_trade(trade)
    if locked_trade.status != Trade.Status.CLOSED.value:
        raise ValidationError(INVALID_TRADE_TRANSITION)
    locked_trade.realized_pnl = realized_pnl
    locked_trade.result_r = _calculate_result_r(
        realized_pnl,
        locked_trade.planned_risk_amount,
    )
    locked_trade.actual_exit_price = actual_exit_price
    locked_trade.commission_total = commission_total
    locked_trade.funding_result = funding_result
    locked_trade.full_clean()
    locked_trade.save(
        update_fields=[
            "realized_pnl",
            "result_r",
            "actual_exit_price",
            "commission_total",
            "funding_result",
            "updated_at",
        ]
    )
    _profile_status = sync_profile_status(profile)
    return locked_trade
