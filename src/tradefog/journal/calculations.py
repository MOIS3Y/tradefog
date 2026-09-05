"""Deterministic financial calculations for journal trade plans."""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import final

from django.utils.translation import gettext as _

REWARD_MULTIPLE = Decimal(3)


@final
class PositionPlanError(ValueError):
    """Describe one user-correctable position-plan validation failure."""

    def __init__(self, field: str, message: str) -> None:
        """Retain the form field associated with the invalid value."""
        super().__init__(message)
        self.field: str = field
        self.message: str = message


@dataclass(frozen=True, slots=True)
class PositionPlan:
    """A position sized to an instrument's executable precision."""

    distance: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    notional: Decimal
    planned_risk_amount: Decimal
    target_risk_amount: Decimal

    @property
    def planned_profit_amount(self) -> Decimal:
        """Return the executable target profit for the fixed reward ratio."""
        with localcontext() as context:
            context.prec = 96
            return self.planned_risk_amount * REWARD_MULTIPLE

    @property
    def take_profit_distance(self) -> Decimal:
        """Return the exact planned price move from entry to take profit."""
        return self.distance * REWARD_MULTIPLE


def _is_step_aligned(value: Decimal, step: Decimal) -> bool:
    """Return whether an exact financial value is a multiple of its step."""
    return value % step == 0


def _round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Round down to an arbitrary positive exchange quantity step."""
    with localcontext() as context:
        context.prec = 96
        steps = (value / step).to_integral_value(rounding=ROUND_FLOOR)
        return steps * step


def calculate_position_plan(
    *,
    direction: str,
    entry: Decimal,
    stop: Decimal,
    target_risk_amount: Decimal,
    price_step: Decimal,
    quantity_step: Decimal,
    minimum_quantity: Decimal | None = None,
    minimum_notional: Decimal | None = None,
) -> PositionPlan:
    """Calculate an exact 1:3 plan without exceeding target monetary risk.

    Entry and stop must already be executable at the instrument price step.
    Quantity is rounded down so precision normalization can only reduce risk.
    """
    if entry <= 0:
        raise PositionPlanError("planned_entry", _("Entry must be positive."))
    if stop <= 0:
        raise PositionPlanError("planned_stop", _("Stop must be positive."))
    if target_risk_amount <= 0:
        raise PositionPlanError(
            "planned_entry",
            _("The profile does not currently provide positive trade risk."),
        )
    if not _is_step_aligned(entry, price_step):
        raise PositionPlanError(
            "planned_entry",
            _("Entry must be aligned with the instrument price step."),
        )
    if not _is_step_aligned(stop, price_step):
        raise PositionPlanError(
            "planned_stop",
            _("Stop must be aligned with the instrument price step."),
        )

    if direction == "LONG":
        distance = entry - stop
        if distance <= 0:
            raise PositionPlanError(
                "planned_stop",
                _("A LONG stop must be below the entry price."),
            )
        take_profit = entry + distance * REWARD_MULTIPLE
    elif direction == "SHORT":
        distance = stop - entry
        if distance <= 0:
            raise PositionPlanError(
                "planned_stop",
                _("A SHORT stop must be above the entry price."),
            )
        take_profit = entry - distance * REWARD_MULTIPLE
        if take_profit <= 0:
            raise PositionPlanError(
                "planned_stop",
                _("The calculated SHORT take profit must remain positive."),
            )
    else:
        raise PositionPlanError("direction", _("Select a trade direction."))

    quantity = _round_down_to_step(
        target_risk_amount / distance,
        quantity_step,
    )
    if quantity <= 0:
        raise PositionPlanError(
            "planned_entry",
            _("Risk and stop distance produce a quantity below one step."),
        )
    if minimum_quantity is not None and quantity < minimum_quantity:
        raise PositionPlanError(
            "planned_entry",
            _("Calculated quantity is below the instrument minimum."),
        )

    with localcontext() as context:
        context.prec = 96
        notional = entry * quantity
        planned_risk_amount = quantity * distance
    if minimum_notional is not None and notional < minimum_notional:
        raise PositionPlanError(
            "planned_entry",
            _("Calculated order value is below the instrument minimum."),
        )

    return PositionPlan(
        distance=distance,
        stop_loss=stop,
        take_profit=take_profit,
        quantity=quantity,
        notional=notional,
        planned_risk_amount=planned_risk_amount,
        target_risk_amount=target_risk_amount,
    )


def wallet_balance(
    total_deposits: Decimal, total_withdrawals: Decimal
) -> Decimal:
    """Return the virtual balance of a wallet asset from its operations."""
    return total_deposits - total_withdrawals


def available_balance(
    balance: Decimal, reserved_notional: Decimal
) -> Decimal:
    """Return the spendable balance after active trade reservations."""
    return balance - reserved_notional


def wallet_asset_status(
    balance: Decimal,
    worst_case_balance: Decimal,
    risk_stop_capital: Decimal | None,
) -> str:
    """Return the money-health status of a wallet asset against its floor.

    A wallet asset is ``RISK_STOPPED`` when its balance is at or below its
    advisory deposit floor, ``AT_RISK`` when the balance is above the floor
    but its worst-case balance (after active trade reservations) is at or
    below it, and ``ACTIVE`` otherwise.
    """
    if risk_stop_capital is None:
        return "active"
    if balance <= risk_stop_capital:
        return "risk_stopped"
    if worst_case_balance <= risk_stop_capital:
        return "at_risk"
    return "active"
