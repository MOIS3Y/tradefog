"""Core models for trading profiles, capital, and instruments."""

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
from django.db.models import Sum
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from tradefog.accounts.models import User

POSITIVE_VALUE = MinValueValidator(Decimal("0.000000000001"))
NON_NEGATIVE_VALUE = MinValueValidator(Decimal(0))
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
PROVIDER_LOCKED = _("The execution provider cannot be changed.")


class TradingProfile(models.Model):
    """A user-owned virtual capital allocation with fixed risk rules."""

    class Provider(models.TextChoices):
        """Execution providers currently available to profile owners."""

        MANUAL = "MANUAL", _("Manual")

    class Status(models.TextChoices):
        """Operational states derived from capital and user archiving."""

        ACTIVE = "ACTIVE", _("Active")
        AT_RISK = "AT_RISK", _("At risk")
        RISK_STOPPED = "RISK_STOPPED", _("Risk stopped")
        ARCHIVED = "ARCHIVED", _("Archived")

    id: int
    capital_operations: models.Manager[CapitalOperation]
    instruments: models.Manager[ProfileInstrument]

    owner: models.ForeignKey[User, User] = models.ForeignKey(
        cast(str, settings.AUTH_USER_MODEL),
        on_delete=models.CASCADE,
        related_name="trading_profiles",
    )
    name: models.CharField[str, str] = models.CharField(
        _("Name"), max_length=100
    )
    provider: models.CharField[str, str] = models.CharField(
        _("Execution provider"),
        max_length=20,
        choices=Provider,
        default=Provider.MANUAL,
        editable=False,
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
            default=Decimal("1.000"),
            validators=PERCENTAGE_VALIDATORS,
        )
    )
    risk_stop_capital: models.DecimalField[Decimal, Decimal] = (
        models.DecimalField(
            _("Risk stop capital"),
            max_digits=24,
            decimal_places=8,
            validators=[NON_NEGATIVE_VALUE],
            help_text=_(
                "Trading should stop when current capital reaches this "
                + "absolute amount."
            ),
        )
    )
    status: models.CharField[str, str] = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status,
        default=Status.ACTIVE,
        editable=False,
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
        """Normalize identifiers and enforce immutable profile context."""
        super().clean()
        self.name = self.name.strip()
        self.capital_currency = self.capital_currency.strip().upper()
        if self._state.adding:
            return
        original = (
            type(self)
            .objects.filter(pk=self.id)
            .values("capital_currency", "provider")
            .first()
        )
        if original is None:
            return
        if original["provider"] != self.provider:
            raise ValidationError({"provider": PROVIDER_LOCKED})
        if (
            original["capital_currency"] != self.capital_currency
            and self.instruments.exists()
        ):
            raise ValidationError(
                {"capital_currency": CAPITAL_CURRENCY_LOCKED}
            )

    @property
    def capital_operation_total(self) -> Decimal:
        """Return net explicit capital allocated after profile creation."""
        rows = self.capital_operations.values("operation_type").annotate(
            total=Sum("amount")
        )
        totals = {
            cast(str, row["operation_type"]): cast(Decimal, row["total"])
            for row in rows
        }
        deposits = totals.get(
            CapitalOperation.Type.DEPOSIT.value,
            Decimal(0),
        )
        withdrawals = totals.get(
            CapitalOperation.Type.WITHDRAWAL.value,
            Decimal(0),
        )
        return deposits - withdrawals

    @property
    def realized_pnl_total(self) -> Decimal:
        """Return realized trade P&L included in capital.

        Trades are introduced in Stage 4. Keeping this boundary explicit makes
        the capital formula ready for that source without coupling capital
        operations to the future trade model.
        """
        return Decimal(0)

    @property
    def current_capital(self) -> Decimal:
        """Derive current virtual capital from persisted financial facts."""
        return (
            self.initial_capital
            + self.capital_operation_total
            + self.realized_pnl_total
        )

    @property
    def risk_base(self) -> Decimal:
        """Return the capital base used for the next position plan."""
        return max(self.initial_capital, self.current_capital)

    @property
    def risk_amount(self) -> Decimal:
        """Return the unrounded monetary risk for the next trade."""
        return self.risk_base * self.risk_per_trade_percent / Decimal(100)

    @property
    def reserved_risk(self) -> Decimal:
        """Return risk reserved by pending and open trades.

        Stage 4 adds trade reservations. Profiles expose the boundary now so
        profile-state calculations do not need to change their public shape.
        """
        return Decimal(0)

    @property
    def worst_case_capital(self) -> Decimal:
        """Return capital after every currently reserved risk is lost."""
        return self.current_capital - self.reserved_risk

    @property
    def risk_capacity(self) -> Decimal:
        """Return capital remaining above the stop in the worst case."""
        return self.worst_case_capital - self.risk_stop_capital

    @property
    def calculated_status(self) -> str:
        """Derive the operational status from current financial facts."""
        if self.status == self.Status.ARCHIVED.value:
            return self.Status.ARCHIVED.value
        if self.current_capital <= self.risk_stop_capital:
            return self.Status.RISK_STOPPED.value
        if self.worst_case_capital <= self.risk_stop_capital:
            return self.Status.AT_RISK.value
        return self.Status.ACTIVE.value

    @property
    def is_archived(self) -> bool:
        """Return whether the profile is hidden from active workflows."""
        return self.status == self.Status.ARCHIVED.value


class CapitalOperation(models.Model):
    """An explicit change to the virtual capital allocated to a profile."""

    class Type(models.TextChoices):
        """Supported directions for changing allocated capital."""

        DEPOSIT = "DEPOSIT", _("Deposit")
        WITHDRAWAL = "WITHDRAWAL", _("Withdrawal")

    id: int

    profile: models.ForeignKey[TradingProfile, TradingProfile] = (
        models.ForeignKey(
            TradingProfile,
            on_delete=models.CASCADE,
            related_name="capital_operations",
        )
    )
    operation_type: models.CharField[str, str] = models.CharField(
        _("Operation"),
        max_length=20,
        choices=Type,
    )
    amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Amount"),
        max_digits=24,
        decimal_places=8,
        validators=[POSITIVE_VALUE],
    )
    note: models.CharField[str, str] = models.CharField(
        _("Note"),
        max_length=200,
        blank=True,
    )
    created_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now_add=True)
    )
    updated_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now=True)
    )

    class Meta:
        """Show the newest allocation changes first."""

        ordering: ClassVar[list[str]] = ["-created_at", "-id"]

    @override
    def __str__(self) -> str:
        """Return a concise administrative representation."""
        return f"{self.operation_type.title()} {self.amount}"

    @override
    def clean(self) -> None:
        """Normalize the optional user note."""
        super().clean()
        self.note = self.note.strip()

    @property
    def signed_amount(self) -> Decimal:
        """Return the operation's contribution to current capital."""
        if self.operation_type == self.Type.WITHDRAWAL.value:
            return -self.amount
        return self.amount


class ProfileInstrument(models.Model):
    """A provider-specific instrument available to one profile."""

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
