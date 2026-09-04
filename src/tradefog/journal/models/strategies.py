# Django injects primary keys and reverse managers into model classes.
# pyright: reportUninitializedInstanceVariable=false
"""Trading strategy and per-asset allocation models.

A strategy is a fixed risk and reward cohort inside one profile (the edge
layer). The capital it commits lives per asset in :class:`StrategyCapital`
(the allocation layer), so one strategy is reused across every wallet asset it
allocates and any instrument whose settlement asset has an allocation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, final, override

from django.db import models
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models.enums import StrategyStatus
from tradefog.journal.models.profiles import TradingProfile, WalletAsset

if TYPE_CHECKING:
    from django.db.models import Manager


@final
class TradingStrategy(models.Model):
    """A fixed strategic risk/reward cohort inside one profile.

    Risk percent and reward multiple are correctable while every strategy
    trade is a draft and become locked after the first submitted trade. The
    strategy name and description remain editable. Strategies are archived
    rather than deleted.
    """

    if TYPE_CHECKING:
        id: int
        profile_id: int
        capitals: Manager[StrategyCapital]

    profile = models.ForeignKey(
        TradingProfile,
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name=_("Profile"),
    )
    name = models.CharField(max_length=128, verbose_name=_("Name"))
    description = models.TextField(
        blank=True, verbose_name=_("Description")
    )
    risk_percent = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name=_("Risk percent"),
    )
    reward_multiple = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal(3),
        verbose_name=_("Reward multiple"),
    )
    status = models.CharField(
        max_length=32,
        choices=StrategyStatus.choices,
        default=StrategyStatus.ACTIVE,
        verbose_name=_("Status"),
    )

    @final
    class Meta:
        ordering = ("name",)
        verbose_name = _("trading strategy")
        verbose_name_plural = _("trading strategies")

    @override
    def __str__(self) -> str:
        return self.name


@final
class StrategyCapital(models.Model):
    """A fixed capital allocation of one strategy to one wallet asset.

    The allocation capital locks after the first submitted trade that settles
    in its asset. New allocations may be added when another wallet asset
    becomes available; a new allocation locks from its own first trade.
    """

    if TYPE_CHECKING:
        id: int
        strategy_id: int
        wallet_asset_id: int

    strategy = models.ForeignKey(
        TradingStrategy,
        on_delete=models.CASCADE,
        related_name="capitals",
        verbose_name=_("Strategy"),
    )
    wallet_asset = models.ForeignKey(
        WalletAsset,
        on_delete=models.PROTECT,
        related_name="capitals",
        verbose_name=_("Wallet asset"),
    )
    capital = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Capital"),
    )

    @final
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("strategy", "wallet_asset"),
                name="strategy_capital_strategy_wallet_asset_idx",
            ),
        )
        ordering = ("strategy", "wallet_asset")
        verbose_name = _("strategy capital")
        verbose_name_plural = _("strategy capitals")

    @override
    def __str__(self) -> str:
        return f"{self.strategy} / {self.wallet_asset}"