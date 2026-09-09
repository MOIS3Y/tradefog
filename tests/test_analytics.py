"""Focused regression tests for trading-quality analytics."""

from datetime import UTC, date, datetime
from decimal import Decimal

from tradefog.domain.analytics import (
    ClosedTradeResult,
    Outcome,
    calculate_monetary_analytics,
    calculate_trade_analytics,
)
from tradefog.domain.enums import Direction, ProductKind


def closed_trade(
    identifier: int,
    result_r: str,
    reward_multiple: str = "3",
    *,
    allocation_id: int = 1,
    realized_pnl: str | None = None,
    quality_rating: int | None = None,
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
        closed_at=datetime(2026, 9, identifier, tzinfo=UTC),
        strategy_capital_id=allocation_id,
        settlement_asset_id=10 + allocation_id,
        settlement_asset_symbol="USD" if allocation_id == 1 else "EUR",
        allocation_capital=Decimal(1000),
        realized_pnl=(
            Decimal(realized_pnl)
            if realized_pnl is not None
            else Decimal(result_r) * Decimal(10)
        ),
        quality_rating=quality_rating,
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
            closed_trade(6, "3", quality_rating=8),
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
    assert analytics.average_quality_rating == Decimal(8)


def test_monetary_analytics_keeps_allocations_separate() -> None:
    """Money remains meaningful without conversion or persisted rollups."""
    analytics = calculate_monetary_analytics(
        [
            closed_trade(1, "3", realized_pnl="300"),
            closed_trade(2, "-1", realized_pnl="-100"),
            closed_trade(
                3,
                "3",
                allocation_id=2,
                realized_pnl="30",
            ),
        ]
    )

    assert len(analytics) == 2
    usd, eur = analytics
    assert usd.gross_profit == Decimal(300)
    assert usd.gross_loss == Decimal(100)
    assert usd.net_pnl == Decimal(200)
    assert usd.allocation_return_percent == Decimal(20)
    assert usd.points[-1].cumulative_pnl == Decimal(200)
    assert eur.net_pnl == Decimal(30)
    assert eur.settlement_asset_symbol == "EUR"
