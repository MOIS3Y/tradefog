# Django injects primary keys and reverse managers into model classes.
# pyright: reportUninitializedInstanceVariable=false
"""Trade and write-once decision snapshot models.

A trade is the working journal record and lifecycle. When it leaves the
draft state, its decision context is frozen into a :class:`TradeSnapshot`
that never changes afterwards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from django.db import models
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models.catalog import VenueInstrument
from tradefog.journal.models.enums import ATRSource, Direction, TradeStatus
from tradefog.journal.models.profiles import TradingProfile
from tradefog.journal.models.strategies import TradingStrategy


@final
class Trade(models.Model):
    """A working journal decision and its lifecycle.

    Working fields are editable while the trade is a draft. On the
    draft-to-pending transition the plan, risk, wallet, and ATR context are
    frozen into the one-to-one :class:`TradeSnapshot`, and the trade working
    fields are locked from then on. A trade references a shared venue
    instrument directly.
    """

    if TYPE_CHECKING:
        id: int
        profile_id: int
        strategy_id: int
        venue_instrument_id: int
        snapshot: TradeSnapshot | None

    profile = models.ForeignKey(
        TradingProfile,
        on_delete=models.CASCADE,
        related_name="trades",
    )
    strategy = models.ForeignKey(
        TradingStrategy,
        on_delete=models.PROTECT,
        related_name="trades",
    )
    venue_instrument = models.ForeignKey(
        VenueInstrument,
        on_delete=models.PROTECT,
        related_name="trades",
    )
    trade_date = models.DateField()
    status = models.CharField(
        max_length=32,
        choices=TradeStatus.choices,
        default=TradeStatus.DRAFT,
    )
    direction = models.CharField(max_length=8, choices=Direction.choices)
    description_markdown = models.TextField(blank=True)
    review_completed_at = models.DateTimeField(null=True, blank=True)
    realized_pnl = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    actual_exit_price = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    total_commission = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    funding_result = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @final
    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("trade")
        verbose_name_plural = _("trades")

    @override
    def __str__(self) -> str:
        return (
            f"{self.trade_date} {self.venue_instrument.pair} "
            f"{Direction(self.direction).label}"
        )


@final
class TradeSnapshot(models.Model):
    """Immutable decision context for one trade.

    Created atomically on the draft-to-pending transition and never mutated
    afterwards. Its ``planned_notional`` backs the derived wallet reservation
    while the trade is pending or open.
    """

    if TYPE_CHECKING:
        id: int
        trade_id: int

    trade = models.OneToOneField(
        Trade,
        on_delete=models.CASCADE,
        related_name="snapshot",
    )
    planned_entry = models.DecimalField(max_digits=30, decimal_places=18)
    planned_stop = models.DecimalField(max_digits=30, decimal_places=18)
    planned_take_profit = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    reward_multiple = models.DecimalField(max_digits=10, decimal_places=6)
    planned_risk_percent = models.DecimalField(max_digits=10, decimal_places=6)
    planned_risk_amount = models.DecimalField(max_digits=30, decimal_places=18)
    planned_notional = models.DecimalField(max_digits=30, decimal_places=18)
    strategy_equity = models.DecimalField(max_digits=30, decimal_places=18)
    strategic_capital = models.DecimalField(max_digits=30, decimal_places=18)
    risk_stop_capital = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    already_reserved_risk = models.DecimalField(
        max_digits=30, decimal_places=18
    )
    remaining_risk_capacity = models.DecimalField(
        max_digits=30, decimal_places=18
    )
    risk_limit_breach = models.BooleanField(default=False)
    wallet_balance = models.DecimalField(max_digits=30, decimal_places=18)
    wallet_reserved = models.DecimalField(max_digits=30, decimal_places=18)
    wallet_available = models.DecimalField(max_digits=30, decimal_places=18)
    atr_value = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    atr_source = models.CharField(
        max_length=16,
        choices=ATRSource.choices,
        null=True,
        blank=True,
    )
    atr_contributing_date = models.DateField(null=True, blank=True)
    atr_observation_time = models.DateTimeField(null=True, blank=True)
    atr_stale = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @final
    class Meta:
        verbose_name = _("trade snapshot")
        verbose_name_plural = _("trade snapshots")

    @override
    def __str__(self) -> str:
        return f"Snapshot of {self.trade}"