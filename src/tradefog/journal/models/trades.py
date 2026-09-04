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
        verbose_name=_("Profile"),
    )
    strategy = models.ForeignKey(
        TradingStrategy,
        on_delete=models.PROTECT,
        related_name="trades",
        verbose_name=_("Strategy"),
    )
    venue_instrument = models.ForeignKey(
        VenueInstrument,
        on_delete=models.PROTECT,
        related_name="trades",
        verbose_name=_("Venue instrument"),
    )
    trade_date = models.DateField(verbose_name=_("Trade date"))
    status = models.CharField(
        max_length=32,
        choices=TradeStatus.choices,
        default=TradeStatus.DRAFT,
        verbose_name=_("Status"),
    )
    direction = models.CharField(
        max_length=8,
        choices=Direction.choices,
        verbose_name=_("Direction"),
    )
    description_markdown = models.TextField(
        blank=True, verbose_name=_("Description")
    )
    review_completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Review completed at")
    )
    realized_pnl = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Realized P&L"),
    )
    actual_exit_price = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Actual exit price"),
    )
    total_commission = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Total commission"),
    )
    funding_result = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Funding result"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created at")
    )

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
        verbose_name=_("Trade"),
    )
    planned_entry = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Planned entry"),
    )
    planned_stop = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Planned stop"),
    )
    planned_take_profit = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Planned take profit"),
    )
    quantity = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Quantity"),
    )
    reward_multiple = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name=_("Reward multiple"),
    )
    planned_risk_percent = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name=_("Planned risk percent"),
    )
    planned_risk_amount = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Planned risk amount"),
    )
    planned_notional = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Planned notional"),
    )
    allocation_capital = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Allocation capital"),
    )
    risk_stop_capital = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Risk stop capital"),
    )
    already_reserved_risk = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Already reserved risk"),
    )
    remaining_risk_capacity = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Remaining risk capacity"),
    )
    deposit_floor_breach = models.BooleanField(
        default=False, verbose_name=_("Deposit floor breach")
    )
    wallet_balance = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Wallet balance"),
    )
    wallet_reserved = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Wallet reserved"),
    )
    wallet_available = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Wallet available"),
    )
    atr_value = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("ATR value"),
    )
    atr_source = models.CharField(
        max_length=16,
        choices=ATRSource.choices,
        null=True,
        blank=True,
        verbose_name=_("ATR source"),
    )
    atr_contributing_date = models.DateField(
        null=True, blank=True, verbose_name=_("ATR contributing date")
    )
    atr_observation_time = models.DateTimeField(
        null=True, blank=True, verbose_name=_("ATR observation time")
    )
    atr_stale = models.BooleanField(
        default=False, verbose_name=_("ATR stale")
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created at")
    )

    @final
    class Meta:
        verbose_name = _("trade snapshot")
        verbose_name_plural = _("trade snapshots")

    @override
    def __str__(self) -> str:
        return f"Snapshot of {self.trade}"