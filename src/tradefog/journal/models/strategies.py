# Django injects primary keys and reverse managers into model classes.
# pyright: reportUninitializedInstanceVariable=false
"""Trading strategy model.

A strategy is a fixed-capital, fixed-risk cohort inside one profile. All of
its trades settle in exactly one wallet asset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from django.db import models
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models.enums import StrategyStatus
from tradefog.journal.models.profiles import TradingProfile, WalletAsset


@final
class TradingStrategy(models.Model):
    """A fixed strategic risk cohort with one settlement wallet asset.

    Settlement, strategic capital, risk percent, and risk stop remain
    correctable while every trade is a draft and become locked after the
    first submitted trade. Strategies are archived rather than deleted.
    """

    if TYPE_CHECKING:
        id: int
        profile_id: int
        settlement_wallet_asset_id: int

    profile = models.ForeignKey(
        TradingProfile,
        on_delete=models.CASCADE,
        related_name="strategies",
    )
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    settlement_wallet_asset = models.ForeignKey(
        WalletAsset,
        on_delete=models.PROTECT,
        related_name="strategies",
    )
    strategic_capital = models.DecimalField(max_digits=30, decimal_places=18)
    risk_percent = models.DecimalField(max_digits=10, decimal_places=6)
    risk_stop_capital = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=StrategyStatus.choices,
        default=StrategyStatus.ACTIVE,
    )

    @final
    class Meta:
        ordering = ("name",)
        verbose_name = _("trading strategy")
        verbose_name_plural = _("trading strategies")

    @override
    def __str__(self) -> str:
        return self.name