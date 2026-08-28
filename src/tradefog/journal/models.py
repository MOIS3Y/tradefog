"""Core models for trading profiles and their instruments."""

# Django injects primary keys and reverse managers into model classes.
# pyright: reportUninitializedInstanceVariable=false

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, cast, override

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from tradefog.accounts.models import User

POSITIVE_VALUE = MinValueValidator(Decimal("0.000000000001"))
PERCENTAGE_VALIDATORS = [
    MinValueValidator(Decimal("0.001")),
    MaxValueValidator(Decimal(100)),
]
ASSET_IDENTIFIER = RegexValidator(
    regex=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    message=_("Use letters, numbers, dots, underscores, or hyphens."),
)
ACTIVE_MARKET_EXISTS = _("An active instrument already uses this market.")
CAPITAL_CURRENCY_LOCKED = _(
    "Capital currency is locked after the first instrument."
)


class TradingProfile(models.Model):
    """A user-owned capital allocation with one set of risk rules."""

    id: int
    instruments: models.Manager[ProfileInstrument]

    owner: models.ForeignKey[User, User] = models.ForeignKey(
        cast(str, settings.AUTH_USER_MODEL),
        on_delete=models.CASCADE,
        related_name="trading_profiles",
    )
    name: models.CharField[str, str] = models.CharField(
        _("Name"), max_length=100
    )
    venue_name: models.CharField[str, str] = models.CharField(
        _("Venue"), max_length=100
    )
    capital_currency: models.CharField[str, str] = models.CharField(
        _("Capital currency"),
        max_length=12,
        validators=[ASSET_IDENTIFIER],
        help_text=_("Currency used for capital, risk, and realized P&L."),
    )
    initial_capital: models.DecimalField[Decimal, Decimal] = (
        models.DecimalField(
            _("Initial trading capital"),
            max_digits=24,
            decimal_places=8,
            validators=[POSITIVE_VALUE],
        )
    )
    risk_per_trade_percent: models.DecimalField[Decimal, Decimal] = (
        models.DecimalField(
            _("Risk per trade, %"),
            max_digits=6,
            decimal_places=3,
            default=Decimal("0.330"),
            validators=PERCENTAGE_VALIDATORS,
        )
    )
    reward_multiple: models.DecimalField[Decimal, Decimal] = (
        models.DecimalField(
            _("Reward multiple"),
            max_digits=6,
            decimal_places=2,
            default=Decimal("3.00"),
            validators=[MinValueValidator(Decimal("0.01"))],
            help_text=_(
                "Target profit expressed as a multiple of trade risk."
            ),
        )
    )
    daily_risk_limit_percent: models.DecimalField[Decimal, Decimal] = (
        models.DecimalField(
            _("Daily risk limit, %"),
            max_digits=6,
            decimal_places=3,
            default=Decimal("1.000"),
            validators=PERCENTAGE_VALIDATORS,
        )
    )
    monthly_target_percent: models.DecimalField[Decimal, Decimal] = (
        models.DecimalField(
            _("Monthly target, %"),
            max_digits=6,
            decimal_places=3,
            default=Decimal("3.000"),
            validators=PERCENTAGE_VALIDATORS,
        )
    )
    archived_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True, editable=False)
    )
    created_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now_add=True)
    )
    updated_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now=True)
    )

    class Meta:
        """Order profiles consistently in overview pages."""

        ordering: ClassVar[list[str]] = ["name", "id"]

    @override
    def __str__(self) -> str:
        """Return the profile name used throughout the interface."""
        return self.name

    def get_absolute_url(self) -> str:
        """Return the localized detail URL for this profile."""
        return reverse("profile_detail", kwargs={"profile_id": self.id})

    @override
    def clean(self) -> None:
        """Normalize profile identifiers and validate related risk limits."""
        super().clean()
        self.name = self.name.strip()
        self.venue_name = self.venue_name.strip()
        self.capital_currency = self.capital_currency.strip().upper()
        if not self._state.adding:
            original_currency = (
                type(self)
                .objects.filter(pk=self.id)
                .values_list("capital_currency", flat=True)
                .first()
            )
            if (
                original_currency is not None
                and original_currency != self.capital_currency
                and self.instruments.exists()
            ):
                raise ValidationError(
                    {"capital_currency": CAPITAL_CURRENCY_LOCKED}
                )
        daily_limit = cast(Decimal | None, self.daily_risk_limit_percent)
        trade_risk = cast(Decimal | None, self.risk_per_trade_percent)
        if (
            daily_limit is not None
            and trade_risk is not None
            and daily_limit < trade_risk
        ):
            raise ValidationError(
                {
                    "daily_risk_limit_percent": _(
                        "The daily risk limit cannot be lower than the risk per trade."
                    )
                }
            )

    @property
    def is_archived(self) -> bool:
        """Return whether the profile is hidden from active workflows."""
        return self.archived_at is not None


class ProfileInstrument(models.Model):
    """A venue-specific linear instrument available to one profile."""

    class MarketType(models.TextChoices):
        """Instrument types supported by the initial journal."""

        SPOT = "SPOT", _("Spot")
        LINEAR = "LINEAR", _("Linear")

    id: int

    profile: models.ForeignKey[TradingProfile, TradingProfile] = (
        models.ForeignKey(
            TradingProfile,
            on_delete=models.CASCADE,
            related_name="instruments",
        )
    )
    base_asset: models.CharField[str, str] = models.CharField(
        _("Base asset"),
        max_length=20,
        validators=[ASSET_IDENTIFIER],
        help_text=_("The traded asset; profile capital is the quote asset."),
    )
    display_name: models.CharField[str, str] = models.CharField(
        _("Display name"),
        max_length=100,
        blank=True,
    )
    market_type: models.CharField[str, str] = models.CharField(
        _("Market type"),
        max_length=10,
        choices=MarketType,
        default=MarketType.SPOT,
    )
    price_step: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Price step"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    quantity_step: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Quantity step"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    minimum_quantity: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Minimum quantity"),
            max_digits=24,
            decimal_places=12,
            null=True,
            blank=True,
            validators=[POSITIVE_VALUE],
        )
    )
    minimum_notional: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Minimum notional"),
            max_digits=24,
            decimal_places=8,
            null=True,
            blank=True,
            validators=[POSITIVE_VALUE],
            help_text=_(
                "Minimum order value in the profile capital currency."
            ),
        )
    )
    archived_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True, editable=False)
    )
    created_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now_add=True)
    )
    updated_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now=True)
    )

    class Meta:
        """Keep active markets unique within each trading profile."""

        ordering: ClassVar[list[str]] = ["base_asset", "market_type", "id"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["profile", "base_asset", "market_type"],
                condition=models.Q(archived_at__isnull=True),
                name="unique_active_profile_instrument_market",
                violation_error_message=ACTIVE_MARKET_EXISTS,
            )
        ]

    @override
    def __str__(self) -> str:
        """Return the canonical market pair and its owning profile."""
        return f"{self.symbol} — {self.profile.name}"

    @override
    def clean(self) -> None:
        """Normalize the base asset and optional display name."""
        super().clean()
        self.base_asset = self.base_asset.strip().upper()
        self.display_name = self.display_name.strip()
        if self.base_asset == self.profile.capital_currency:
            raise ValidationError(
                {
                    "base_asset": _(
                        "The traded asset must differ from the capital asset."
                    )
                }
            )

    @property
    def quote_asset(self) -> str:
        """Return the profile asset in which this market is settled."""
        return self.profile.capital_currency

    @property
    def symbol(self) -> str:
        """Return the canonical pair shown in the journal interface."""
        return f"{self.base_asset}/{self.quote_asset}"

    @property
    def is_archived(self) -> bool:
        """Return whether the instrument is hidden from active workflows."""
        return self.archived_at is not None
