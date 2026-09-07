"""Focused regression tests for executable position sizing."""

from decimal import Decimal

import pytest

from tradefog.domain.calculations import (
    PositionPlanError,
    calculate_position_plan,
)


def test_position_plan_rounds_down_without_exceeding_risk() -> None:
    """Exchange precision may reduce, but never increase, monetary risk."""
    plan = calculate_position_plan(
        direction="long",
        entry=Decimal(100),
        stop=Decimal(97),
        target_risk_amount=Decimal(10),
        reward_multiple=Decimal(2),
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.7"),
    )

    assert plan.quantity == Decimal("2.8")
    assert plan.planned_risk_amount == Decimal("8.4")
    assert plan.planned_risk_amount <= plan.target_risk_amount
    assert plan.take_profit == Decimal(106)
    assert plan.notional == Decimal(280)


@pytest.mark.parametrize(
    ("entry", "stop", "target_risk", "expected_message"),
    [
        (Decimal(100), Decimal(100), Decimal(10), "below entry"),
        (Decimal(100), Decimal(90), Decimal("0.1"), "rounds down to zero"),
    ],
)
def test_position_plan_rejects_non_executable_boundaries(
    entry: Decimal,
    stop: Decimal,
    target_risk: Decimal,
    expected_message: str,
) -> None:
    """Invalid stops and zero executable quantity fail explicitly."""
    with pytest.raises(PositionPlanError, match=expected_message):
        calculate_position_plan(
            direction="long",
            entry=entry,
            stop=stop,
            target_risk_amount=target_risk,
            reward_multiple=Decimal(3),
            price_step=Decimal("0.01"),
            quantity_step=Decimal(1),
        )
