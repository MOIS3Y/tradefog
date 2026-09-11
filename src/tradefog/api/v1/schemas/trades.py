"""Transport models for the trade workspace and lifecycle."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from tradefog.api.v1.schemas.pagination import ListQuery
from tradefog.domain.checklists import (
    AssessmentDirection,
    DirectionalValue,
    TrendRelationship,
)
from tradefog.domain.enums import ATRSource, Direction, TradeStatus


class TradeListQuery(ListQuery):
    """Server-side journal filters independent of pagination."""

    order: Literal["asc", "desc"] = "desc"
    profile_id: int | None = Field(default=None, gt=0)
    strategy_id: int | None = Field(default=None, gt=0)
    trade_status: TradeStatus | None = None
    direction: Direction | None = None
    date_from: date | None = None
    date_to: date | None = None
    review: Literal["all", "reviewed", "unreviewed"] = "all"
    rated: bool | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Reject reversed date intervals rather than returning no rows."""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not exceed date_to")
        return self


class TradeListItem(BaseModel):
    """Compact journal row without draft sections or snapshot payloads."""

    id: int
    profile_id: int
    profile_name: str
    strategy_id: int
    strategy_name: str
    instrument_id: int
    exec_symbol: str
    pair_symbol: str
    settlement_symbol: str
    trade_date: date
    direction: Direction
    status: TradeStatus
    realized_pnl: Decimal | None
    quality_rating: int | None
    review_completed_at: datetime | None


class TradeInput(BaseModel):
    """Reject unknown trade fields so journal edits remain intentional."""

    model_config = ConfigDict(extra="forbid")


class ChecklistWrite(TradeInput):
    """The four fixed directional observations of a draft decision."""

    market_sentiment: DirectionalValue | None = None
    information_background: DirectionalValue | None = None
    global_daily_direction: DirectionalValue | None = None
    local_daily_movement: DirectionalValue | None = None


class ChecklistResponse(ChecklistWrite):
    """Checklist answers plus their deterministic advisory assessment."""

    score: Decimal
    direction: AssessmentDirection
    completeness: Decimal
    answered_count: int
    total_count: int
    gauge_position: int
    trend_relationship: TrendRelationship
    agrees_with_trade: bool | None


class TradeCreate(TradeInput):
    """Create the editable identity and context of a draft trade."""

    profile_id: int = Field(gt=0)
    strategy_id: int = Field(gt=0)
    instrument_id: int = Field(gt=0)
    trade_date: date
    direction: Direction
    description_markdown: str | None = None


class TradePatch(TradeInput):
    """Edit a draft identity or evolving journal metadata."""

    strategy_id: int | None = Field(default=None, gt=0)
    instrument_id: int | None = Field(default=None, gt=0)
    trade_date: date | None = None
    direction: Direction | None = None
    description_markdown: str | None = None
    quality_rating: int | None = Field(default=None, ge=1, le=10)

    @model_validator(mode="after")
    def reject_required_nulls(self) -> "TradePatch":
        """Allow null only for the nullable Markdown description."""
        values = self.model_dump(exclude_unset=True)
        nullable = {"description_markdown", "quality_rating"}
        for field, value in values.items():
            if field not in nullable and value is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ATRRequest(TradeInput):
    """Refresh automatic ATR or supply a manual fallback value."""

    value: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=30,
        decimal_places=18,
    )
    contributing_date: date | None = None
    observed_session_range: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=30,
        decimal_places=18,
    )
    stale: bool = False


class CandleResponse(BaseModel):
    """One daily candle returned only as transient market context."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


class ATRResponse(BaseModel):
    """Current draft ATR context and non-persisted preview candles."""

    value: Decimal
    source: ATRSource
    contributing_date: date
    observation_time: datetime
    stale: bool
    observed_session_range: Decimal | None = None
    session_range_percent: Decimal | None = None
    candles: list[CandleResponse] = Field(default_factory=list)


class TradeSubmit(TradeInput):
    """Freeze the saved draft plan while entering pending or open state."""

    status: TradeStatus

    @model_validator(mode="after")
    def require_submission_status(self) -> "TradeSubmit":
        """Limit submission to the two states that create a snapshot."""
        if self.status not in (TradeStatus.PENDING_ENTRY, TradeStatus.OPEN):
            raise ValueError("status must be pending_entry or open")
        return self


class TradePlanRequest(TradeInput):
    """Editable position anchors persisted as normalized entry and stop."""

    planned_entry: Decimal = Field(gt=0, max_digits=30, decimal_places=18)
    planned_stop: Decimal = Field(gt=0, max_digits=30, decimal_places=18)


class TradePlanSave(TradeInput):
    """Persist partial anchors without inventing missing numeric values."""

    planned_entry: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )
    planned_stop: Decimal | None = Field(
        default=None, gt=0, max_digits=30, decimal_places=18
    )


class PreparationResponse(BaseModel):
    """Typed inputs retained even when the plan is incomplete."""

    model_config = ConfigDict(from_attributes=True)
    planned_entry: Decimal | None
    planned_stop: Decimal | None
    market_sentiment: DirectionalValue | None
    information_background: DirectionalValue | None
    global_daily_direction: DirectionalValue | None
    local_daily_movement: DirectionalValue | None
    atr_value: Decimal | None
    atr_source: ATRSource | None
    atr_contributing_date: date | None
    atr_observation_time: datetime | None
    atr_stale: bool
    observed_session_range: Decimal | None


class TradePlanningContextResponse(BaseModel):
    """Stable inputs required for a local draft position calculation."""

    price_step: Decimal
    quantity_step: Decimal
    minimum_quantity: Decimal | None
    minimum_notional: Decimal | None
    reward_multiple: int
    planned_risk_percent: Decimal
    target_risk_amount: Decimal
    allocation_capital: Decimal
    already_reserved_risk: Decimal
    remaining_risk_capacity: Decimal
    risk_stop_capital: Decimal | None
    wallet_balance: Decimal
    wallet_reserved: Decimal
    wallet_available: Decimal
    deposit_floor_breach: bool
    product: str
    direction: Direction
    base_asset_id: int
    settlement_asset_id: int
    inventory_asset_id: int | None
    inventory_available: Decimal


class ReservationResponse(BaseModel):
    """Exact required amount and availability of one virtual denomination."""

    asset_id: int
    purpose: str
    amount: Decimal
    available: Decimal


class StoredReservationResponse(BaseModel):
    """Immutable requirements retained after release."""

    model_config = ConfigDict(from_attributes=True)
    asset_id: int
    purpose: str
    amount: Decimal


class TradePlanResponse(BaseModel):
    """Executable plan and current capital context before submission."""

    planned_entry: Decimal
    reservations: list[ReservationResponse]
    planned_stop: Decimal
    planned_take_profit: Decimal
    stop_distance: Decimal
    take_profit_distance: Decimal
    quantity: Decimal
    reward_multiple: int
    planned_risk_percent: Decimal
    target_risk_amount: Decimal
    planned_risk_amount: Decimal
    planned_notional: Decimal
    allocation_capital: Decimal
    already_reserved_risk: Decimal
    remaining_risk_capacity: Decimal
    deposit_floor_breach: bool
    wallet_balance: Decimal
    wallet_reserved: Decimal
    wallet_available: Decimal
    capital_remaining: Decimal
    capital_sufficient: bool
    atr_value: Decimal | None
    take_profit_atr_percent: Decimal | None
    fits_atr_limit: bool | None
    atr_limit_percent: Decimal = Decimal(75)


class TradeClose(TradeInput):
    """Record final signed net P&L and execution context."""

    realized_pnl: Decimal = Field(max_digits=30, decimal_places=18)
    actual_exit_price: Decimal = Field(
        gt=0,
        max_digits=30,
        decimal_places=18,
    )
    total_commission: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=30,
        decimal_places=18,
    )
    funding_result: Decimal | None = Field(
        default=None,
        max_digits=30,
        decimal_places=18,
    )


class TradeReview(TradeInput):
    """Mark or clear review completion for a closed trade."""

    completed: bool = True


class SnapshotResponse(BaseModel):
    """Immutable financial and volatility context frozen at submission."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_capital_id: int
    settlement_asset_id: int
    instrument_symbol: str
    instrument_product: str
    price_step: Decimal
    qty_step: Decimal
    min_qty: Decimal | None
    min_notional: Decimal | None
    planned_entry: Decimal
    planned_stop: Decimal
    planned_take_profit: Decimal | None
    quantity: Decimal | None
    reward_multiple: Decimal | None
    planned_risk_percent: Decimal | None
    planned_risk_amount: Decimal | None
    planned_notional: Decimal | None
    allocation_capital: Decimal | None
    risk_stop_capital: Decimal | None
    already_reserved_risk: Decimal | None
    remaining_risk_capacity: Decimal | None
    deposit_floor_breach: bool | None
    wallet_balance: Decimal | None
    wallet_reserved: Decimal | None
    wallet_available: Decimal | None
    atr_value: Decimal | None
    atr_source: ATRSource | None
    atr_contributing_date: date | None
    atr_observation_time: datetime | None
    atr_stale: bool | None
    created_at: datetime

    @computed_field
    @property
    def stop_distance(self) -> Decimal:
        """Return the absolute frozen entry-to-stop distance."""
        return abs(self.planned_entry - self.planned_stop)

    @computed_field
    @property
    def take_profit_distance(self) -> Decimal | None:
        """Return the absolute frozen entry-to-target distance."""
        if self.planned_take_profit is None:
            return None
        return abs(self.planned_take_profit - self.planned_entry)


class TradeResponse(BaseModel):
    """Complete owner-scoped trade workspace representation."""

    id: int
    profile_id: int
    preparation: PreparationResponse
    reservations: list[StoredReservationResponse]
    strategy_id: int
    instrument_id: int
    trade_date: date
    status: TradeStatus
    direction: Direction
    description_markdown: str | None
    quality_rating: int | None
    review_completed_at: datetime | None
    realized_pnl: Decimal | None
    actual_exit_price: Decimal | None
    total_commission: Decimal | None
    funding_result: Decimal | None
    submitted_at: datetime | None
    opened_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    checklist: ChecklistResponse
    plan: TradePlanRequest | None
    atr: ATRResponse | None
    snapshot: SnapshotResponse | None
