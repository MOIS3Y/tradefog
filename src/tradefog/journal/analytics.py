"""Deterministic trading-quality analytics for closed journal trades."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


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
    market_type: str
    pair_symbol: str
    direction: str
    result_r: Decimal
    reward_multiple: Decimal


@dataclass(frozen=True, slots=True)
class TrajectoryPoint:
    """The cumulative X/Y coordinate after one closed journal decision."""

    sequence: int
    trade: ClosedTradeResult
    outcome: Outcome
    x: Decimal
    y: Decimal


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
    gross_profit_r: Decimal
    gross_loss_r: Decimal
    current_streak: Streak
    maximum_winning_streak: int
    maximum_losing_streak: int
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
    """Calculate statistics and X/Y path from ordered closed trades.

    Every invocation starts at ``(0, 0)``. Losses advance X by their absolute
    R result, while profits advance Y by their fraction of the trade's
    snapshotted reward multiple. Break-even trades advance neither axis and
    interrupt a winning or losing streak.
    """
    points: list[TrajectoryPoint] = []
    x = Decimal(0)
    y = Decimal(0)
    net_result_r = Decimal(0)
    gross_profit_r = Decimal(0)
    gross_loss_r = Decimal(0)
    win_count = 0
    loss_count = 0
    break_even_count = 0
    maximum_winning_streak = 0
    maximum_losing_streak = 0
    streak_outcome: Outcome | None = None
    streak_count = 0

    for sequence, trade in enumerate(trades, start=1):
        if trade.reward_multiple <= 0:
            raise ValueError("A closed trade reward multiple must be positive.")

        outcome = _outcome(trade.result_r)
        net_result_r += trade.result_r
        if outcome is Outcome.WIN:
            win_count += 1
            gross_profit_r += trade.result_r
            y += trade.result_r / trade.reward_multiple
        elif outcome is Outcome.LOSS:
            loss_count += 1
            gross_loss_r += abs(trade.result_r)
            x += abs(trade.result_r)
        else:
            break_even_count += 1

        if outcome is Outcome.BREAK_EVEN:
            streak_outcome = None
            streak_count = 0
        elif outcome is streak_outcome:
            streak_count += 1
        else:
            streak_outcome = outcome
            streak_count = 1

        if streak_outcome is Outcome.WIN:
            maximum_winning_streak = max(
                maximum_winning_streak,
                streak_count,
            )
        elif streak_outcome is Outcome.LOSS:
            maximum_losing_streak = max(
                maximum_losing_streak,
                streak_count,
            )

        points.append(
            TrajectoryPoint(
                sequence=sequence,
                trade=trade,
                outcome=outcome,
                x=x,
                y=y,
            )
        )

    closed_trade_count = len(points)
    denominator = Decimal(closed_trade_count)
    win_rate = (
        Decimal(win_count) * Decimal(100) / denominator
        if closed_trade_count
        else Decimal(0)
    )
    average_result_r = (
        net_result_r / denominator if closed_trade_count else Decimal(0)
    )
    return TradeAnalytics(
        closed_trade_count=closed_trade_count,
        win_count=win_count,
        loss_count=loss_count,
        break_even_count=break_even_count,
        win_rate=win_rate,
        net_result_r=net_result_r,
        average_result_r=average_result_r,
        gross_profit_r=gross_profit_r,
        gross_loss_r=gross_loss_r,
        current_streak=Streak(streak_outcome, streak_count),
        maximum_winning_streak=maximum_winning_streak,
        maximum_losing_streak=maximum_losing_streak,
        points=tuple(points),
    )
