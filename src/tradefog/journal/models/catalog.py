# Django injects primary keys and reverse managers into model classes.
# pyright: reportUninitializedInstanceVariable=false
"""Shared, staff-managed reference catalog models.

These records form the installation-wide directory that regular users read
and reuse but never create or edit. Ownership of catalog data is not
journal-specific; the journal refers back to it through ``PROTECT`` foreign
keys so referenced catalog facts are never silently deleted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from django.db import models
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models.enums import AssetType, ProductKind

if TYPE_CHECKING:
    from django.db.models import Manager


@final
class Asset(models.Model):
    """A globally reusable identity for one tradable or payable asset.

    A symbol maps to exactly one asset across the whole installation, so the
    same BTC is shared by every venue. Symbols are stored normalized to
    upper case so uniqueness is effectively case-insensitive.
    """

    if TYPE_CHECKING:
        id: int
        pairs_base: Manager[TradingPair]
        pairs_quote: Manager[TradingPair]
        instruments_settled: Manager[VenueInstrument]
        wallet_venues: Manager[VenueWalletAsset]

    symbol = models.CharField(
        max_length=32, unique=True, verbose_name=_("Symbol")
    )
    name = models.CharField(
        max_length=255, blank=True, verbose_name=_("Name")
    )
    asset_type = models.CharField(
        max_length=16,
        choices=AssetType.choices,
        verbose_name=_("Asset type"),
    )

    @final
    class Meta:
        ordering = ("symbol",)
        verbose_name = _("asset")
        verbose_name_plural = _("assets")

    @override
    def __str__(self) -> str:
        return self.symbol


@final
class TradingPair(models.Model):
    """A reusable logical ``BASE/QUOTE`` market.

    The pair carries no execution parameters and is entered once for the
    whole installation. Concrete executable markets live on
    :class:`VenueInstrument`.
    """

    if TYPE_CHECKING:
        id: int
        instruments: Manager[VenueInstrument]

    base = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="pairs_base",
        verbose_name=_("Base asset"),
    )
    quote = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="pairs_quote",
        verbose_name=_("Quote asset"),
    )
    canonical_symbol = models.CharField(
        max_length=32,
        unique=True,
        help_text="Normalized display identity, for example BTC/USD.",
        verbose_name=_("Symbol"),
    )

    @final
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("base", "quote"),
                name="trading_pair_base_quote_idx",
            ),
        )
        ordering = ("base", "quote")
        verbose_name = _("trading pair")
        verbose_name_plural = _("trading pairs")

    @override
    def __str__(self) -> str:
        return f"{self.base.symbol}/{self.quote.symbol}"


@final
class Venue(models.Model):
    """A shared exchange, broker, or other execution destination.

    A venue carries no market class; supported markets are derived from the
    products of its instruments, so one venue can host several products.
    """

    if TYPE_CHECKING:
        id: int
        instruments: Manager[VenueInstrument]
        wallet_assets: Manager[VenueWalletAsset]

    name = models.CharField(
        max_length=128, unique=True, verbose_name=_("Name")
    )
    website = models.URLField(blank=True, verbose_name=_("Website"))

    @final
    class Meta:
        ordering = ("name",)
        verbose_name = _("venue")
        verbose_name_plural = _("venues")

    @override
    def __str__(self) -> str:
        return self.name


@final
class VenueInstrument(models.Model):
    """An executable market on one venue for one product.

    This is the only record holding per-venue, per-product execution
    parameters. The underlying asset and pair stay shared and are never
    duplicated. Settlement is explicit for a Perpetual Future instrument and
    left unset (derived from quote) for Spot and Cash Equity.
    """

    if TYPE_CHECKING:
        id: int
        venue_id: int
        pair_id: int
        settlement_asset_id: int | None

    venue = models.ForeignKey(
        Venue,
        on_delete=models.PROTECT,
        related_name="instruments",
        verbose_name=_("Venue"),
    )
    pair = models.ForeignKey(
        TradingPair,
        on_delete=models.PROTECT,
        related_name="instruments",
        verbose_name=_("Trading pair"),
    )
    product = models.CharField(
        max_length=32,
        choices=ProductKind.choices,
        verbose_name=_("Product"),
    )
    exec_symbol = models.CharField(
        max_length=64, verbose_name=_("Execution symbol")
    )
    price_step = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Price step"),
    )
    qty_step = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        verbose_name=_("Quantity step"),
    )
    min_qty = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Minimum quantity"),
    )
    min_notional = models.DecimalField(
        max_digits=30,
        decimal_places=18,
        null=True,
        blank=True,
        verbose_name=_("Minimum notional"),
    )
    settlement_asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="instruments_settled",
        null=True,
        blank=True,
        verbose_name=_("Settlement asset"),
    )
    active = models.BooleanField(
        default=True, verbose_name=_("Active")
    )

    @final
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("venue", "pair", "product"),
                name="venue_instrument_venue_pair_product_idx",
            ),
            models.UniqueConstraint(
                fields=("venue", "exec_symbol"),
                name="venue_instrument_venue_exec_symbol_idx",
            ),
        )
        ordering = ("venue", "pair", "product")
        verbose_name = _("venue instrument")
        verbose_name_plural = _("venue instruments")

    @override
    def __str__(self) -> str:
        return f"{self.pair} {ProductKind(self.product).label}"


@final
class VenueWalletAsset(models.Model):
    """A shared asset that can be held in a wallet on one venue.

    This deliberate subset marks which assets a profile wallet may reference
    on the venue; not every available asset is wallet-capable there.
    """

    if TYPE_CHECKING:
        id: int
        venue_id: int
        asset_id: int

    venue = models.ForeignKey(
        Venue,
        on_delete=models.PROTECT,
        related_name="wallet_assets",
        verbose_name=_("Venue"),
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="wallet_venues",
        verbose_name=_("Asset"),
    )

    @final
    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("venue", "asset"),
                name="venue_wallet_asset_venue_asset_idx",
            ),
        )
        verbose_name = _("venue wallet asset")
        verbose_name_plural = _("venue wallet assets")

    @override
    def __str__(self) -> str:
        return f"{self.venue} / {self.asset}"
