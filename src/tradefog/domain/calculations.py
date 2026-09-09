"""Deterministic financial calculations for journal trade plans."""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import final


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
    reward_multiple: Decimal

    @property
    def planned_profit_amount(self) -> Decimal:
        """Return the executable target profit for the strategy reward ratio."""
        with localcontext() as context:
            context.prec = 96
            return self.planned_risk_amount * self.reward_multiple

    @property
    def take_profit_distance(self) -> Decimal:
        """Return the exact planned price move from entry to take profit."""
        return self.distance * self.reward_multiple


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
    reward_multiple: Decimal,
    price_step: Decimal,
    quantity_step: Decimal,
    minimum_quantity: Decimal | None = None,
    minimum_notional: Decimal | None = None,
) -> PositionPlan:
    """Calculate an exact plan without exceeding target monetary risk.

    Entry and stop must already be executable at the instrument price step.
    Quantity is rounded down so precision normalization can only reduce risk.
    """
    if entry <= 0:
        raise PositionPlanError("planned_entry", "Entry must be positive.")
    if stop <= 0:
        raise PositionPlanError("planned_stop", "Stop must be positive.")
    if target_risk_amount <= 0:
        raise PositionPlanError(
            "planned_entry",
            "The profile does not currently provide positive trade risk.",
        )
    if (
        reward_multiple < 3
        or reward_multiple > 100
        or reward_multiple != reward_multiple.to_integral_value()
    ):
        raise PositionPlanError(
            "planned_entry",
            "Strategy reward multiple must be a whole number from 3 to 100.",
        )
    if not _is_step_aligned(entry, price_step):
        raise PositionPlanError(
            "planned_entry",
            "Entry must be aligned with the instrument price step.",
        )
    if not _is_step_aligned(stop, price_step):
        raise PositionPlanError(
            "planned_stop",
            "Stop must be aligned with the instrument price step.",
        )

    normalized_direction = direction.lower().strip()
    if normalized_direction == "long":
        if stop >= entry:
            raise PositionPlanError(
                "planned_stop",
                "Stop loss must be below entry for a long trade.",
            )
        distance = entry - stop
        take_profit = entry + (distance * reward_multiple)
    elif normalized_direction == "short":
        if stop <= entry:
            raise PositionPlanError(
                "planned_stop",
                "Stop loss must be above entry for a short trade.",
            )
        distance = stop - entry
        take_profit = entry - (distance * reward_multiple)
        if take_profit <= 0:
            raise PositionPlanError(
                "planned_entry",
                "Take profit calculation results in a non-positive price.",
            )
    else:
        raise PositionPlanError(
            "direction",
            f"Unsupported trade direction: {direction}",
        )

    with localcontext() as context:
        context.prec = 96
        raw_quantity = target_risk_amount / distance
        quantity = _round_down_to_step(raw_quantity, quantity_step)

    if quantity <= 0:
        raise PositionPlanError(
            "planned_entry",
            "Calculated quantity rounds down to zero for the given risk.",
        )

    if minimum_quantity is not None and quantity < minimum_quantity:
        raise PositionPlanError(
            "planned_entry",
            f"Calculated quantity {quantity} is below minimum {minimum_quantity}.",
        )

    with localcontext() as context:
        context.prec = 96
        notional = quantity * entry
        planned_risk = quantity * distance

    if minimum_notional is not None and notional < minimum_notional:
        raise PositionPlanError(
            "planned_entry",
            f"Calculated notional {notional} is below minimum {minimum_notional}.",
        )

    return PositionPlan(
        distance=distance,
        stop_loss=stop,
        take_profit=take_profit,
        quantity=quantity,
        notional=notional,
        planned_risk_amount=planned_risk,
        target_risk_amount=target_risk_amount,
        reward_multiple=reward_multiple,
    )
