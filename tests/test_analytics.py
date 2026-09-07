"""Focused regression tests for trading-quality analytics."""

from datetime import date
from decimal import Decimal

from tradefog.domain.analytics import (
    ClosedTradeResult,
    Outcome,
    calculate_trade_analytics,
)
from tradefog.domain.enums import Direction, ProductKind


def closed_trade(
    identifier: int,
    result_r: str,
    reward_multiple: str = "3",
) -> ClosedTradeResult:
    """Build one minimal closed-trade fact for deterministic analytics."""
    return ClosedTradeResult(
        trade_id=identifier,
        trade_date=date(2026, 9, identifier),
        profile_name="Main",
        market_type=ProductKind.SPOT,
        pair_symbol="BTC/USD",
        direction=Direction.LONG,
        result_r=Decimal(result_r),
        reward_multiple=Decimal(reward_multiple),
    )


def test_analytics_handles_empty_cohort() -> None:
    """An empty selection returns useful zeros without invented ratios."""
    analytics = calculate_trade_analytics([])

    assert analytics.closed_trade_count == 0
    assert analytics.win_rate == 0
    assert analytics.net_result_r == 0
    assert analytics.expectancy_r == 0
    assert analytics.maximum_drawdown_r == 0
    assert analytics.profit_factor_r is None
    assert analytics.current_streak.outcome is None
    assert analytics.points == ()


def test_analytics_calculates_mixed_results_drawdown_and_streaks() -> None:
    """Wins, losses and break-even trades produce one coherent trajectory."""
    analytics = calculate_trade_analytics(
        [
            closed_trade(1, "3"),
            closed_trade(2, "-1"),
            closed_trade(3, "-0.5"),
            closed_trade(4, "0"),
            closed_trade(5, "1.5"),
            closed_trade(6, "3"),
        ]
    )

    assert (
        analytics.win_count,
        analytics.loss_count,
        analytics.break_even_count,
    ) == (3, 2, 1)
    assert analytics.win_rate == Decimal("0.5")
    assert analytics.net_result_r == Decimal(6)
    assert analytics.average_result_r == Decimal(1)
    assert analytics.profit_factor_r == Decimal(5)
    assert analytics.expectancy_r == Decimal(1)
    assert analytics.maximum_drawdown_r == Decimal("1.5")
    assert analytics.maximum_winning_streak == 2
    assert analytics.maximum_losing_streak == 2
    assert analytics.current_streak.outcome is Outcome.WIN
    assert analytics.current_streak.count == 2
    assert analytics.points[3].outcome is Outcome.BREAK_EVEN
    assert analytics.points[3].x == analytics.points[2].x
    assert analytics.points[3].y == analytics.points[2].y
    assert analytics.final_x == Decimal("1.5")
    assert analytics.final_y == Decimal("2.5")
