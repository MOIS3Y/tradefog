"""Transport models for owner-scoped trading-quality analytics."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from tradefog.domain.analytics import Outcome
from tradefog.domain.enums import Direction, ProductKind


class AnalyticsPeriod(StrEnum):
    """Named date cohorts supported by the analytics endpoint."""

    ALL_TIME = "all_time"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    YEAR_TO_DATE = "year_to_date"
    CUSTOM = "custom"


class StreakResponse(BaseModel):
    """Current consecutive winning or losing sequence."""

    outcome: Outcome | None
    count: int


class TrajectoryPointResponse(BaseModel):
    """One ordered closed trade and its cumulative quality coordinates."""

    sequence: int
    trade_id: int
    trade_date: date
    closed_at: datetime
    profile_name: str
    product: ProductKind
    pair_symbol: str
    direction: Direction
    result_r: Decimal
    outcome: Outcome
    cumulative_result_r: Decimal
    discipline_x: Decimal | None
    discipline_y: Decimal | None


class ReferencePointResponse(BaseModel):
    """One point on the cumulative break-even reference line."""

    sequence: int
    cumulative_result_r: Decimal = Decimal(0)


class DisciplineReferencePointResponse(BaseModel):
    """One coordinate on the decision-discipline break-even diagonal."""

    x: Decimal
    y: Decimal


class MonetaryTrajectoryPointResponse(BaseModel):
    """One realized result in a single allocation's settlement asset."""

    sequence: int
    trade_id: int
    closed_at: datetime
    realized_pnl: Decimal
    cumulative_pnl: Decimal


class AllocationMonetaryResponse(BaseModel):
    """Money totals scoped to one immutable allocation and asset."""

    strategy_capital_id: int
    settlement_asset_id: int
    settlement_asset_symbol: str
    allocation_capital: Decimal
    trade_count: int
    gross_profit: Decimal
    gross_loss: Decimal
    net_pnl: Decimal
    allocation_return_percent: Decimal
    trajectory: list[MonetaryTrajectoryPointResponse]


class AnalyticsResponse(BaseModel):
    """Comprehensive metrics for one owner-scoped closed-trade cohort."""

    closed_trade_count: int
    reviewed_trade_count: int
    excluded_trade_count: int
    win_count: int
    loss_count: int
    break_even_count: int
    win_rate_percent: Decimal
    net_result_r: Decimal
    average_result_r: Decimal
    average_win_r: Decimal
    average_loss_r: Decimal
    gross_profit_r: Decimal
    gross_loss_r: Decimal
    profit_factor_r: Decimal | None
    expectancy_r: Decimal
    maximum_drawdown_r: Decimal
    current_streak: StreakResponse
    maximum_winning_streak: int
    maximum_losing_streak: int
    average_quality_rating: Decimal | None
    trajectory: list[TrajectoryPointResponse]
    break_even_reference: list[ReferencePointResponse]
    discipline_available: bool
    discipline_reward_multiple: int | None
    discipline_break_even_reference: list[DisciplineReferencePointResponse]
    monetary: list[AllocationMonetaryResponse]
