"""Transport models for owner-scoped trading-quality analytics."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from tradefog.api.documentation import (
    ALLOCATION_MONETARY_EXAMPLE,
    ANALYTICS_EXAMPLE,
    DISCIPLINE_REFERENCE_EXAMPLE,
    MONETARY_POINT_EXAMPLE,
    REFERENCE_POINT_EXAMPLE,
    TRAJECTORY_POINT_EXAMPLE,
)
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

    model_config = ConfigDict(
        json_schema_extra={"examples": [TRAJECTORY_POINT_EXAMPLE]},
    )

    sequence: int
    trade_id: int
    profile_id: int
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

    model_config = ConfigDict(
        json_schema_extra={"examples": [REFERENCE_POINT_EXAMPLE]},
    )

    sequence: int
    cumulative_result_r: Decimal = Decimal(0)


class DisciplineReferencePointResponse(BaseModel):
    """One coordinate on the decision-discipline break-even diagonal."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [DISCIPLINE_REFERENCE_EXAMPLE]},
    )

    x: Decimal
    y: Decimal


class MonetaryTrajectoryPointResponse(BaseModel):
    """One realized result in a single allocation's settlement asset."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [MONETARY_POINT_EXAMPLE]},
    )

    sequence: int
    trade_id: int
    profile_id: int
    closed_at: datetime
    realized_pnl: Decimal
    cumulative_pnl: Decimal


class AllocationMonetaryResponse(BaseModel):
    """Money totals scoped to one immutable allocation and asset."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [ALLOCATION_MONETARY_EXAMPLE]},
    )

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

    model_config = ConfigDict(
        json_schema_extra={"examples": [ANALYTICS_EXAMPLE]},
    )

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
