# Django injects primary keys and reverse managers into model classes.
# pyright: reportUninitializedInstanceVariable=false
"""Owner-scoped trading profile and virtual wallet models.

All journal data is scoped through ``TradingProfile.owner``, the single
ownership root. Child records carry no redundant owner field; their owner is
reached transitively through the profile. Catalog references use ``PROTECT``
so shared facts are never silently deleted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final, override

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models.catalog import Venue, VenueWalletAsset
from tradefog.journal.models.enums import (
    WalletAssetStatus,
    WalletOperationKind,
)

if TYPE_CHECKING:
    from django.db.models import Manager

    from tradefog.accounts.models import User


@final
class TradingProfile(models.Model):
    """A user's trading context bound to exactly one venue.

    The profile owns its wallet, strategies, and trades and reuses the venue's
    shared instruments without copying catalog facts.
    """

    if TYPE_CHECKING:
        id: int
        owner_id: int
        venue_id: int
        wallet: Wallet

    owner: models.ForeignKey[User] = models.ForeignKey(
        cast(str, settings.AUTH_USER_MODEL),
        on_delete=models.CASCADE,
        related_name="profiles",
        verbose_name=_("Owner"),
    )
    venue = models.ForeignKey(
        Venue,
        on_delete=models.PROTECT,
        related_name="profiles",
        verbose_name=_("Venue"),
    )
    name = models.CharField(max_length=128, verbose_name=_("Name"))
    archived = models.BooleanField(
        default=False, verbose_name=_("Archived")
    )

    @final
    class Meta:
        ordering = ("name",)
        verbose_name = _("trading profile")
        verbose_name_plural = _("trading profiles")

    @override
    def __str__(self) -> str:
        return self.name


@final
class Wallet(models.Model):
    """The profile wallet, strictly one-to-one with its profile.

    The wallet holds no money itself; it groups :class:`WalletAsset` balances.
    A global wallet in the interface is a UI-only aggregation over profile
    wallets and is not stored separately.
    """

    if TYPE_CHECKING:
        id: int
        assets: Manager[WalletAsset]

    profile = models.OneToOneField(
        TradingProfile,
        on_delete=models.CASCADE,
        related_name="wallet",
        verbose_name=_("Profile"),
    )

    @final
    class Meta:
        verbose_name = _("wallet")
        verbose_name_plural = _("wallets")

    @override
    def __str__(self) -> str:
        return f"Wallet of {self.profile}"


@final
class WalletAsset(models.Model):
    """A balance for one asset available on the profile venue.

    References a :class:`VenueWalletAsset` rather than a bare asset so the
    held asset is structurally guaranteed to be venue-capable for the
    profile's venue.
    """

    if TYPE_CHECKING:
        id: int
        wallet_id: int
        venue_wallet_asset_id: int
        operations: Manager[WalletOperation]

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="assets",
        verbose_name=_("Wallet"),
    )
    venue_wallet_asset = models.ForeignKey(
        VenueWalletAsset,
        on_delete=models.PROTECT,
        related_name="wallet_assets",
        verbose_name=_("Venue wallet asset"),
    )
    risk_stop_capital = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Risk stop capital"),
        help_text=_("Advisory deposit floor that highlights a bleeding deposit."),
    )
    status = models.CharField(
        max_length=32,
        choices=WalletAssetStatus.choices,
        default=WalletAssetStatus.ACTIVE,
        verbose_name=_("Status"),
    )

    @final
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("wallet", "venue_wallet_asset"),
                name="wallet_asset_wallet_venue_asset_idx",
            ),
        )
        verbose_name = _("wallet asset")
        verbose_name_plural = _("wallet assets")

    @override
    def __str__(self) -> str:
        return str(self.venue_wallet_asset.asset)


@final
class WalletOperation(models.Model):
    """A journal fact introducing or removing virtual funds.

    An operation is not an exchange action; it records a deposit or
    withdrawal against one wallet asset.
    """

    if TYPE_CHECKING:
        id: int
        wallet_asset_id: int

    wallet_asset = models.ForeignKey(
        WalletAsset,
        on_delete=models.PROTECT,
        related_name="operations",
        verbose_name=_("Wallet asset"),
    )
    kind = models.CharField(
        max_length=16,
        choices=WalletOperationKind.choices,
        verbose_name=_("Kind"),
    )
    amount = models.DecimalField(
        max_digits=30, decimal_places=18, verbose_name=_("Amount")
    )
    note = models.CharField(
        max_length=255, blank=True, verbose_name=_("Note")
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created at")
    )

    @final
    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("wallet operation")
        verbose_name_plural = _("wallet operations")

    @override
    def __str__(self) -> str:
        return f"{WalletOperationKind(self.kind).label} {self.amount}"
