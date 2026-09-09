"""Deterministic trading-quality analytics for closed journal trades."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext
from enum import StrEnum

from tradefog.domain.enums import Direction, ProductKind


class Outcome(StrEnum):
    """Normalized signs used for counts and consecutive streaks."""

    WIN = "WIN"
    LOSS = "LOSS"
    BREAK_EVEN = "BREAK_EVEN"


@dataclass(frozen=True, slots=True)
class ClosedTradeResult:
    """The closed-trade facts needed by quality analytics and presentation."""

    trade_id: int
    trade_date: date
    profile_name: str
    market_type: ProductKind
    pair_symbol: str
    direction: Direction
    result_r: Decimal
    reward_multiple: Decimal
    closed_at: datetime
    strategy_capital_id: int
    settlement_asset_id: int
    settlement_asset_symbol: str
    allocation_capital: Decimal
    realized_pnl: Decimal
    quality_rating: int | None = None


@dataclass(frozen=True, slots=True)
class MonetaryTrajectoryPoint:
    """One realized monetary result inside an exact allocation cohort."""

    sequence: int
    trade_id: int
    closed_at: datetime
    realized_pnl: Decimal
    cumulative_pnl: Decimal


@dataclass(frozen=True, slots=True)
class AllocationMonetaryAnalytics:
    """Money totals that never cross allocation or asset boundaries."""

    strategy_capital_id: int
    settlement_asset_id: int
    settlement_asset_symbol: str
    allocation_capital: Decimal
    trade_count: int
    gross_profit: Decimal
    gross_loss: Decimal
    net_pnl: Decimal
    allocation_return_percent: Decimal
    points: tuple[MonetaryTrajectoryPoint, ...]


@dataclass(frozen=True, slots=True)
class TrajectoryPoint:
    """The cumulative X/Y coordinate after one closed journal decision."""

    sequence: int
    trade: ClosedTradeResult
    outcome: Outcome
    x: Decimal
    y: Decimal
    cumulative_result_r: Decimal


@dataclass(frozen=True, slots=True)
class Streak:
    """A current consecutive run of wins or losses."""

    outcome: Outcome | None
    count: int


@dataclass(frozen=True, slots=True)
class TradeAnalytics:
    """Aggregate metrics and reproducible path for one filtered selection."""

    closed_trade_count: int
    win_count: int
    loss_count: int
    break_even_count: int
    win_rate: Decimal
    net_result_r: Decimal
    average_result_r: Decimal
    average_win_r: Decimal
    average_loss_r: Decimal
    gross_profit_r: Decimal
    gross_loss_r: Decimal
    profit_factor_r: Decimal | None
    expectancy_r: Decimal
    maximum_drawdown_r: Decimal
    current_streak: Streak
    maximum_winning_streak: int
    maximum_losing_streak: int
    average_quality_rating: Decimal | None
    points: tuple[TrajectoryPoint, ...]

    @property
    def final_x(self) -> Decimal:
        """Return the final full-stop-equivalent coordinate."""
        return self.points[-1].x if self.points else Decimal(0)

    @property
    def final_y(self) -> Decimal:
        """Return the final full-target-equivalent coordinate."""
        return self.points[-1].y if self.points else Decimal(0)


def _outcome(result_r: Decimal) -> Outcome:
    """Classify a normalized result without inventing a tolerance."""
    if result_r > 0:
        return Outcome.WIN
    if result_r < 0:
        return Outcome.LOSS
    return Outcome.BREAK_EVEN


def calculate_trade_analytics(
    trades: Iterable[ClosedTradeResult],
) -> TradeAnalytics:
    """Calculate all metrics under one high-precision decimal context."""
    with localcontext() as context:
        context.prec = 96
        return _calculate_trade_analytics(trades)


def _calculate_trade_analytics(
    trades: Iterable[ClosedTradeResult],
) -> TradeAnalytics:
    """Calculate statistics and X/Y path from ordered closed trades.

    Every invocation starts at ``(0, 0)``. Losses advance X by their absolute
    R result, while profits advance Y by their fraction of the trade's
    snapshotted reward multiple. Break-even trades advance neither axis and
    interrupt a winning or losing streak.
    """
    points: list[TrajectoryPoint] = []
    x = Decimal(0)
    y = Decimal(0)

    win_count = 0
    loss_count = 0
    break_even_count = 0
    gross_profit_r = Decimal(0)
    gross_loss_r = Decimal(0)
    cumulative_result_r = Decimal(0)
    peak_result_r = Decimal(0)
    maximum_drawdown_r = Decimal(0)

    current_streak_outcome: Outcome | None = None
    current_streak_count = 0
    max_winning_streak = 0
    max_losing_streak = 0
    rating_total = Decimal(0)
    rating_count = 0

    for sequence, trade in enumerate(trades, start=1):
        if trade.quality_rating is not None:
            rating_total += Decimal(trade.quality_rating)
            rating_count += 1
        outcome = _outcome(trade.result_r)
        if outcome is Outcome.WIN:
            win_count += 1
            gross_profit_r += trade.result_r
            if trade.reward_multiple > 0:
                y += trade.result_r / trade.reward_multiple
        elif outcome is Outcome.LOSS:
            loss_count += 1
            gross_loss_r += abs(trade.result_r)
            x += abs(trade.result_r)
        else:
            break_even_count += 1

        cumulative_result_r += trade.result_r
        peak_result_r = max(peak_result_r, cumulative_result_r)
        maximum_drawdown_r = max(
            maximum_drawdown_r,
            peak_result_r - cumulative_result_r,
        )

        if outcome is Outcome.BREAK_EVEN:
            current_streak_outcome = None
            current_streak_count = 0
        elif outcome == current_streak_outcome:
            current_streak_count += 1
        else:
            current_streak_outcome = outcome
            current_streak_count = 1

        if current_streak_outcome is Outcome.WIN:
            max_winning_streak = max(max_winning_streak, current_streak_count)
        elif current_streak_outcome is Outcome.LOSS:
            max_losing_streak = max(max_losing_streak, current_streak_count)

        points.append(
            TrajectoryPoint(
                sequence=sequence,
                trade=trade,
                outcome=outcome,
                x=x,
                y=y,
                cumulative_result_r=cumulative_result_r,
            )
        )

    closed_trade_count = len(points)
    win_rate = (
        Decimal(win_count) / Decimal(closed_trade_count)
        if closed_trade_count > 0
        else Decimal(0)
    )
    net_result_r = gross_profit_r - gross_loss_r
    average_result_r = (
        net_result_r / Decimal(closed_trade_count)
        if closed_trade_count > 0
        else Decimal(0)
    )
    average_win_r = (
        gross_profit_r / Decimal(win_count) if win_count > 0 else Decimal(0)
    )
    average_loss_r = (
        gross_loss_r / Decimal(loss_count) if loss_count > 0 else Decimal(0)
    )
    profit_factor_r = (
        gross_profit_r / gross_loss_r if gross_loss_r > 0 else None
    )
    loss_rate = (
        Decimal(loss_count) / Decimal(closed_trade_count)
        if closed_trade_count > 0
        else Decimal(0)
    )
    expectancy_r = win_rate * average_win_r - loss_rate * average_loss_r

    return TradeAnalytics(
        closed_trade_count=closed_trade_count,
        win_count=win_count,
        loss_count=loss_count,
        break_even_count=break_even_count,
        win_rate=win_rate,
        net_result_r=net_result_r,
        average_result_r=average_result_r,
        average_win_r=average_win_r,
        average_loss_r=average_loss_r,
        gross_profit_r=gross_profit_r,
        gross_loss_r=gross_loss_r,
        profit_factor_r=profit_factor_r,
        expectancy_r=expectancy_r,
        maximum_drawdown_r=maximum_drawdown_r,
        current_streak=Streak(
            outcome=current_streak_outcome,
            count=current_streak_count,
        ),
        maximum_winning_streak=max_winning_streak,
        maximum_losing_streak=max_losing_streak,
        average_quality_rating=(
            rating_total / Decimal(rating_count) if rating_count > 0 else None
        ),
        points=tuple(points),
    )


def calculate_monetary_analytics(
    trades: Iterable[ClosedTradeResult],
) -> tuple[AllocationMonetaryAnalytics, ...]:
    """Aggregate exact money independently for every frozen allocation."""
    cohorts: dict[int, list[ClosedTradeResult]] = {}
    for trade in trades:
        cohorts.setdefault(trade.strategy_capital_id, []).append(trade)

    results: list[AllocationMonetaryAnalytics] = []
    with localcontext() as context:
        context.prec = 96
        for allocation_id, cohort in cohorts.items():
            first = cohort[0]
            gross_profit = sum(
                (
                    trade.realized_pnl
                    for trade in cohort
                    if trade.realized_pnl > 0
                ),
                Decimal(0),
            )
            gross_loss = sum(
                (
                    abs(trade.realized_pnl)
                    for trade in cohort
                    if trade.realized_pnl < 0
                ),
                Decimal(0),
            )
            net_pnl = gross_profit - gross_loss
            cumulative = Decimal(0)
            points: list[MonetaryTrajectoryPoint] = []
            for sequence, trade in enumerate(cohort, start=1):
                cumulative += trade.realized_pnl
                points.append(
                    MonetaryTrajectoryPoint(
                        sequence=sequence,
                        trade_id=trade.trade_id,
                        closed_at=trade.closed_at,
                        realized_pnl=trade.realized_pnl,
                        cumulative_pnl=cumulative,
                    )
                )
            results.append(
                AllocationMonetaryAnalytics(
                    strategy_capital_id=allocation_id,
                    settlement_asset_id=first.settlement_asset_id,
                    settlement_asset_symbol=first.settlement_asset_symbol,
                    allocation_capital=first.allocation_capital,
                    trade_count=len(cohort),
                    gross_profit=gross_profit,
                    gross_loss=gross_loss,
                    net_pnl=net_pnl,
                    allocation_return_percent=(
                        net_pnl / first.allocation_capital * Decimal(100)
                    ),
                    points=tuple(points),
                )
            )
    return tuple(results)
