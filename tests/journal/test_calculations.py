"""Focused tests for deterministic position sizing."""

from decimal import Decimal

from pytest import raises

from tradefog.journal.calculations import (
    PositionPlanError,
    calculate_position_plan,
)


def test_long_plan_rounds_quantity_down_without_exceeding_risk() -> None:
    """An arbitrary quantity step may only reduce the configured risk."""
    plan = calculate_position_plan(
        direction="LONG",
        entry=Decimal(100),
        stop=Decimal(95),
        target_risk_amount=Decimal(100),
        price_step=Decimal("0.5"),
        quantity_step=Decimal("0.3"),
    )

    assert plan.distance == Decimal(5)
    assert plan.stop_loss == Decimal(95)
    assert plan.take_profit == Decimal(115)
    assert plan.quantity == Decimal("19.8")
    assert plan.planned_risk_amount == Decimal(99)
    assert plan.planned_profit_amount == Decimal(297)
    assert plan.notional == Decimal(1980)


def test_short_plan_uses_stop_above_entry_and_fixed_reward() -> None:
    """A linear SHORT should mirror the LONG distance calculation."""
    plan = calculate_position_plan(
        direction="SHORT",
        entry=Decimal(100),
        stop=Decimal(105),
        target_risk_amount=Decimal(100),
        price_step=Decimal("0.5"),
        quantity_step=Decimal("0.1"),
    )

    assert plan.distance == Decimal(5)
    assert plan.take_profit == Decimal(85)
    assert plan.quantity == Decimal(20)
    assert plan.planned_risk_amount == Decimal(100)


def test_long_rejects_stop_above_entry() -> None:
    """Directionally invalid protective stops should identify their field."""
    with raises(PositionPlanError) as error:
        _ = calculate_position_plan(
            direction="LONG",
            entry=Decimal(100),
            stop=Decimal(101),
            target_risk_amount=Decimal(100),
            price_step=Decimal(1),
            quantity_step=Decimal(1),
        )

    assert error.value.field == "planned_stop"


def test_plan_rejects_prices_outside_instrument_step() -> None:
    """A plan must use prices that can be sent to its market."""
    with raises(PositionPlanError) as error:
        _ = calculate_position_plan(
            direction="LONG",
            entry=Decimal("100.1"),
            stop=Decimal(95),
            target_risk_amount=Decimal(100),
            price_step=Decimal("0.5"),
            quantity_step=Decimal("0.1"),
        )

    assert error.value.field == "planned_entry"


def test_plan_rejects_order_below_minimum_notional() -> None:
    """Instrument minimums should reject a technically unusable plan."""
    with raises(PositionPlanError):
        _ = calculate_position_plan(
            direction="LONG",
            entry=Decimal(10),
            stop=Decimal(9),
            target_risk_amount=Decimal(1),
            price_step=Decimal(1),
            quantity_step=Decimal(1),
            minimum_notional=Decimal(20),
        )
