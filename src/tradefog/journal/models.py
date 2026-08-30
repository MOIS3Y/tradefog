"""Core models for assets, trading profiles, pairs, and trades."""

# Django injects primary keys and reverse managers into model classes.
# pyright: reportUninitializedInstanceVariable=false

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, localcontext
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
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tradefog.journal.checklists import (
    ChecklistAnswers,
    ChecklistAssessment,
    DirectionalValue,
    calculate_checklist_assessment,
)

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
ACTIVE_PAIR_EXISTS = _("An active trading pair already uses this asset.")
CAPITAL_ASSET_LOCKED = _(
    "Capital asset is locked after the first trading pair."
)
MARKET_TYPE_LOCKED = _("Market type is locked after the first trading pair.")
ASSET_SYMBOL_LOCKED = _("Asset symbol is locked while the asset is in use.")
PROVIDER_LOCKED = _("The execution provider cannot be changed.")
INITIAL_CAPITAL_LOCKED = _(
    "Initial capital is locked after the first submitted trade."
)
RISK_PERCENT_LOCKED = _(
    "Risk per trade is locked after the first submitted trade."
)


class Asset(models.Model):
    """A reusable owner-scoped asset identity."""

    class AssetClass(models.TextChoices):
        """Broad classifications used for presentation and future providers."""

        CRYPTO = "CRYPTO", _("Cryptocurrency")
        EQUITY = "EQUITY", _("Equity")
        FIAT = "FIAT", _("Fiat currency")
        OTHER = "OTHER", _("Other")

    id: int
    owner_id: int
    capital_profiles: models.Manager[TradingProfile]
    trading_pairs: models.Manager[ProfileTradingPair]

    owner: models.ForeignKey[User, User] = models.ForeignKey(
        cast(str, settings.AUTH_USER_MODEL),
        on_delete=models.CASCADE,
        related_name="assets",
    )
    symbol: models.CharField[str, str] = models.CharField(
        _("Symbol"),
        max_length=20,
        validators=[ASSET_IDENTIFIER],
        help_text=_("Canonical symbol used inside Tradefog, for example BTC."),
    )
    name: models.CharField[str, str] = models.CharField(
        _("Name"), max_length=100, blank=True
    )
    asset_class: models.CharField[str, str] = models.CharField(
        _("Asset class"),
        max_length=20,
        choices=AssetClass,
        default=AssetClass.CRYPTO,
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
        """Keep symbols unique and consistently ordered per owner."""

        ordering: ClassVar[list[str]] = ["symbol", "id"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                Lower("symbol"),
                models.F("owner"),
                name="unique_owner_asset_symbol",
            )
        ]

    @override
    def __str__(self) -> str:
        """Return the stable canonical symbol used in selectors."""
        return self.symbol

    @override
    def clean(self) -> None:
        """Normalize identity and prevent changing a referenced symbol."""
        super().clean()
        self.symbol = self.symbol.strip().upper()
        self.name = self.name.strip()
        if self._state.adding:
            return
        original_symbol = (
            type(self).objects.filter(pk=self.id).values_list(
                "symbol", flat=True
            ).first()
        )
        if original_symbol == self.symbol:
            return
        if self.capital_profiles.exists() or self.trading_pairs.exists():
            raise ValidationError({"symbol": ASSET_SYMBOL_LOCKED})

    @property
    def is_archived(self) -> bool:
        """Return whether the asset is hidden from active selectors."""
        return self.archived_at is not None


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

    class MarketType(models.TextChoices):
        """Markets whose execution rules are shared by this profile."""

        SPOT = "SPOT", _("Spot")
        LINEAR_PERPETUAL = "LINEAR_PERPETUAL", _("Linear perpetual")

    id: int
    owner_id: int
    capital_asset_id: int
    capital_operations: models.Manager[CapitalOperation]
    trading_pairs: models.Manager[ProfileTradingPair]
    trades: models.Manager[Trade]

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
    capital_asset: models.ForeignKey[Asset, Asset] = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="capital_profiles",
        verbose_name=_("Capital asset"),
        help_text=_("Quote asset used for capital, risk, and realized P&L."),
    )
    market_type: models.CharField[str, str] = models.CharField(
        _("Market type"),
        max_length=24,
        choices=MarketType,
        default=MarketType.SPOT,
        help_text=_(
            "Spot supports LONG only; linear perpetual supports LONG and "
            + "SHORT at 1x."
        ),
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
        if getattr(self, "capital_asset_id", None) is None:
            return
        if self.capital_asset.owner_id != self.owner_id:
            raise ValidationError(
                {"capital_asset": _("Select an asset owned by this user.")}
            )
        if self._state.adding:
            return
        original = (
            type(self)
            .objects.filter(pk=self.id)
            .values(
                "capital_asset_id",
                "market_type",
                "initial_capital",
                "provider",
                "risk_per_trade_percent",
            )
            .first()
        )
        if original is None:
            return
        if original["provider"] != self.provider:
            raise ValidationError({"provider": PROVIDER_LOCKED})
        if (
            original["capital_asset_id"] != self.capital_asset_id
            and self.trading_pairs.exists()
        ):
            raise ValidationError({"capital_asset": CAPITAL_ASSET_LOCKED})
        if (
            original["market_type"] != self.market_type
            and self.trading_pairs.exists()
        ):
            raise ValidationError({"market_type": MARKET_TYPE_LOCKED})
        submitted_trades = self.trades.exclude(status=Trade.Status.DRAFT.value)
        if not submitted_trades.exists():
            return
        if original["initial_capital"] != self.initial_capital:
            raise ValidationError({"initial_capital": INITIAL_CAPITAL_LOCKED})
        if original["risk_per_trade_percent"] != self.risk_per_trade_percent:
            raise ValidationError(
                {"risk_per_trade_percent": RISK_PERCENT_LOCKED}
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
        """Return aggregate realized P&L registered on closed trades."""
        aggregate = cast(
            dict[str, Decimal | None],
            self.trades.filter(status=Trade.Status.CLOSED.value).aggregate(
                total=Sum("realized_pnl")
            ),
        )
        return aggregate["total"] or Decimal(0)

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
        """Return snapshotted risk reserved by pending and open trades."""
        aggregate = cast(
            dict[str, Decimal | None],
            self.trades.filter(
                status__in=(
                    Trade.Status.PENDING_ENTRY.value,
                    Trade.Status.OPEN.value,
                )
            ).aggregate(total=Sum("planned_risk_amount")),
        )
        return aggregate["total"] or Decimal(0)

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


class ProfileTradingPair(models.Model):
    """An executable base/quote pair configured for one profile."""

    class MarketDataProvider(models.TextChoices):
        """Daily-candle sources available to one configured pair."""

        MANUAL = "MANUAL", _("Manual")
        BYBIT = "BYBIT", "Bybit"

    id: int
    profile_id: int
    asset_id: int
    daily_candles: models.Manager[DailyCandle]
    market_data_state: MarketDataState

    profile: models.ForeignKey[TradingProfile, TradingProfile] = (
        models.ForeignKey(
            TradingProfile,
            on_delete=models.CASCADE,
            related_name="trading_pairs",
        )
    )
    asset: models.ForeignKey[Asset, Asset] = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="trading_pairs",
        verbose_name=_("Base asset"),
        help_text=_("Asset traded against the profile capital asset."),
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
    market_data_provider: models.CharField[str, str] = models.CharField(
        _("Market data source"),
        max_length=10,
        choices=MarketDataProvider,
        default=MarketDataProvider.MANUAL,
        help_text=_(
            "Tradefog always calculates ATR from the stored daily candles."
        ),
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

        ordering: ClassVar[list[str]] = ["asset__symbol", "id"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["profile", "asset"],
                condition=models.Q(archived_at__isnull=True),
                name="unique_active_profile_trading_pair",
                violation_error_message=ACTIVE_PAIR_EXISTS,
            )
        ]

    @override
    def __str__(self) -> str:
        """Return the canonical market pair and its owning profile."""
        return f"{self.symbol} | {self.profile.name}"

    @override
    def clean(self) -> None:
        """Keep both assets owner-scoped and distinct."""
        super().clean()
        if (
            getattr(self, "asset_id", None) is None
            or getattr(self, "profile_id", None) is None
        ):
            return
        if self.asset.owner_id != self.profile.owner_id:
            raise ValidationError(
                {"asset": _("Select an asset owned by the profile owner.")}
            )
        if self.asset_id == self.profile.capital_asset_id:
            raise ValidationError(
                {"asset": _("Base and quote assets must differ.")}
            )

    @property
    def base_symbol(self) -> str:
        """Return the structured base side of the pair."""
        return self.asset.symbol

    @property
    def quote_symbol(self) -> str:
        """Return the structured quote and settlement side of the pair."""
        return self.profile.capital_asset.symbol

    @property
    def symbol(self) -> str:
        """Return the canonical pair shown in the journal interface."""
        return f"{self.base_symbol}/{self.quote_symbol}"

    @property
    def is_archived(self) -> bool:
        """Return whether the instrument is hidden from active workflows."""
        return self.archived_at is not None


class DailyCandle(models.Model):
    """One closed provider-session daily candle for a profile pair."""

    id: int
    trading_pair_id: int

    trading_pair: models.ForeignKey[ProfileTradingPair, ProfileTradingPair] = (
        models.ForeignKey(
            ProfileTradingPair,
            on_delete=models.CASCADE,
            related_name="daily_candles",
        )
    )
    trading_date: models.DateField[date, date] = models.DateField(
        _("Trading date"),
        help_text=_("Bybit daily candles use UTC session dates."),
    )
    open_price: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Open price"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    high_price: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("High price"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    low_price: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Low price"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    close_price: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Close price"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    source: models.CharField[str, str] = models.CharField(
        _("Source"),
        max_length=10,
        choices=ProfileTradingPair.MarketDataProvider,
        default=ProfileTradingPair.MarketDataProvider.MANUAL,
        editable=False,
    )
    fetched_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(default=timezone.now, editable=False)
    )
    created_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now_add=True)
    )
    updated_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now=True)
    )

    class Meta:
        """Keep one canonical closed candle per pair and session date."""

        ordering: ClassVar[list[str]] = ["-trading_date", "-id"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["trading_pair", "trading_date"],
                name="unique_pair_daily_candle",
            ),
            models.CheckConstraint(
                condition=models.Q(high_price__gte=models.F("low_price")),
                name="daily_candle_high_gte_low",
            ),
        ]

    @override
    def __str__(self) -> str:
        """Return the pair and provider-session date."""
        return f"{self.trading_pair.symbol} — {self.trading_date}"

    @override
    def clean(self) -> None:
        """Ensure open and close lie inside the recorded daily range."""
        super().clean()
        if self.low_price > self.high_price:
            raise ValidationError(
                {"high_price": _("High must not be below low.")}
            )
        if not self.low_price <= self.open_price <= self.high_price:
            raise ValidationError(
                {"open_price": _("Open must be inside the daily range.")}
            )
        if not self.low_price <= self.close_price <= self.high_price:
            raise ValidationError(
                {"close_price": _("Close must be inside the daily range.")}
            )


class MarketDataState(models.Model):
    """Cached refresh state and the latest unclosed provider session."""

    id: int
    trading_pair_id: int

    trading_pair: models.OneToOneField[
        ProfileTradingPair, ProfileTradingPair
    ] = models.OneToOneField(
        ProfileTradingPair,
        on_delete=models.CASCADE,
        related_name="market_data_state",
    )
    current_session_date: models.DateField[date | None, date | None] = (
        models.DateField(null=True, blank=True)
    )
    current_high: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            max_digits=24,
            decimal_places=12,
            null=True,
            blank=True,
        )
    )
    current_low: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            max_digits=24,
            decimal_places=12,
            null=True,
            blank=True,
        )
    )
    current_observed_at: models.DateTimeField[
        datetime | None, datetime | None
    ] = models.DateTimeField(null=True, blank=True)
    last_attempt_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    last_success_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    last_error: models.CharField[str, str] = models.CharField(
        max_length=300,
        blank=True,
    )

    @property
    def is_stale(self) -> bool:
        """Return whether the most recent provider refresh failed."""
        return bool(self.last_error)

    @override
    def clean(self) -> None:
        """Keep the optional current-session observation coherent."""
        super().clean()
        values = (
            self.current_session_date,
            self.current_high,
            self.current_low,
            self.current_observed_at,
        )
        if any(value is not None for value in values) and any(
            value is None for value in values
        ):
            raise ValidationError(
                _("Current-session values must be recorded together.")
            )
        if (
            self.current_high is not None
            and self.current_low is not None
            and self.current_high < self.current_low
        ):
            raise ValidationError(
                {"current_high": _("High must not be below low.")}
            )


class Trade(models.Model):
    """One independent journal decision and its execution facts."""

    class Status(models.TextChoices):
        """Small lifecycle shared by manual and future provider workflows."""

        DRAFT = "DRAFT", _("Draft")
        PENDING_ENTRY = "PENDING_ENTRY", _("Pending entry")
        OPEN = "OPEN", _("Open")
        CLOSED = "CLOSED", _("Closed")
        CANCELLED = "CANCELLED", _("Cancelled")

    class Direction(models.TextChoices):
        """Directions supported by ordinary spot and linear instruments."""

        LONG = "LONG", "LONG"
        SHORT = "SHORT", "SHORT"

    id: int
    profile_id: int
    trading_pair_id: int
    checklist: TradeChecklist

    profile: models.ForeignKey[TradingProfile, TradingProfile] = (
        models.ForeignKey(
            TradingProfile,
            on_delete=models.PROTECT,
            related_name="trades",
        )
    )
    trading_pair: models.ForeignKey[ProfileTradingPair, ProfileTradingPair] = (
        models.ForeignKey(
            ProfileTradingPair,
            on_delete=models.PROTECT,
            related_name="trades",
        )
    )
    status: models.CharField[str, str] = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status,
        default=Status.DRAFT,
        editable=False,
    )
    direction: models.CharField[str, str] = models.CharField(
        _("Direction"),
        max_length=10,
        choices=Direction,
    )
    trade_date: models.DateField[date, date] = models.DateField(
        _("Trade date")
    )
    planned_entry: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Planned entry"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    planned_stop: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        _("Planned stop"),
        max_digits=24,
        decimal_places=12,
        validators=[POSITIVE_VALUE],
    )
    planned_take_profit: models.DecimalField[
        Decimal | None, Decimal | None
    ] = models.DecimalField(
        _("Planned take profit"),
        max_digits=24,
        decimal_places=12,
        null=True,
        blank=True,
        editable=False,
    )
    planned_quantity: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Planned quantity"),
            max_digits=24,
            decimal_places=12,
            null=True,
            blank=True,
            editable=False,
        )
    )
    planned_risk_percent: models.DecimalField[
        Decimal | None, Decimal | None
    ] = models.DecimalField(
        _("Planned risk percent"),
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        editable=False,
    )
    planned_risk_amount: models.DecimalField[
        Decimal | None, Decimal | None
    ] = models.DecimalField(
        _("Planned risk amount"),
        max_digits=48,
        decimal_places=24,
        null=True,
        blank=True,
        editable=False,
    )
    reward_multiple: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Reward multiple"),
            max_digits=6,
            decimal_places=3,
            null=True,
            blank=True,
            editable=False,
        )
    )
    capital_snapshot: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Capital snapshot"),
            max_digits=24,
            decimal_places=8,
            null=True,
            blank=True,
            editable=False,
        )
    )
    risk_base_snapshot: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Risk base snapshot"),
            max_digits=24,
            decimal_places=8,
            null=True,
            blank=True,
            editable=False,
        )
    )
    risk_stop_snapshot: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Risk stop snapshot"),
            max_digits=24,
            decimal_places=8,
            null=True,
            blank=True,
            editable=False,
        )
    )
    reserved_risk_snapshot: models.DecimalField[
        Decimal | None, Decimal | None
    ] = models.DecimalField(
        _("Reserved risk snapshot"),
        max_digits=48,
        decimal_places=24,
        null=True,
        blank=True,
        editable=False,
    )
    risk_capacity_snapshot: models.DecimalField[
        Decimal | None, Decimal | None
    ] = models.DecimalField(
        _("Risk capacity snapshot"),
        max_digits=48,
        decimal_places=24,
        null=True,
        blank=True,
        editable=False,
    )
    risk_limit_breached: models.BooleanField[bool, bool] = models.BooleanField(
        _("Risk limit breached"),
        default=False,
        editable=False,
    )
    notional_limit_breached: models.BooleanField[bool, bool] = (
        models.BooleanField(
            _("Notional limit breached"),
            default=False,
            editable=False,
        )
    )
    atr_value_snapshot: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("ATR snapshot"),
            max_digits=24,
            decimal_places=12,
            null=True,
            blank=True,
            editable=False,
        )
    )
    atr_as_of_date_snapshot: models.DateField[date | None, date | None] = (
        models.DateField(
            _("ATR through date"),
            null=True,
            blank=True,
            editable=False,
        )
    )
    atr_source_snapshot: models.CharField[str, str] = models.CharField(
        _("ATR source"),
        max_length=20,
        blank=True,
        editable=False,
    )
    session_range_snapshot: models.DecimalField[
        Decimal | None, Decimal | None
    ] = models.DecimalField(
        _("Observed session range"),
        max_digits=24,
        decimal_places=12,
        null=True,
        blank=True,
        editable=False,
    )
    session_range_percent_snapshot: models.DecimalField[
        Decimal | None, Decimal | None
    ] = models.DecimalField(
        _("Observed range as ATR percent"),
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        editable=False,
    )
    session_observed_at_snapshot: models.DateTimeField[
        datetime | None, datetime | None
    ] = models.DateTimeField(
        _("Session observed at"),
        null=True,
        blank=True,
        editable=False,
    )
    market_data_stale_snapshot: models.BooleanField[bool, bool] = (
        models.BooleanField(
            _("Market data was stale"),
            default=False,
            editable=False,
        )
    )
    realized_pnl: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Realized P&L"),
            max_digits=24,
            decimal_places=8,
            null=True,
            blank=True,
        )
    )
    result_r: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Result in R"),
            max_digits=48,
            decimal_places=24,
            null=True,
            blank=True,
            editable=False,
        )
    )
    actual_exit_price: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Actual exit price"),
            max_digits=24,
            decimal_places=12,
            null=True,
            blank=True,
            validators=[POSITIVE_VALUE],
        )
    )
    commission_total: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Commission"),
            max_digits=24,
            decimal_places=8,
            null=True,
            blank=True,
            validators=[NON_NEGATIVE_VALUE],
            help_text=_("Optional reference total already included in P&L."),
        )
    )
    funding_result: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(
            _("Funding result"),
            max_digits=24,
            decimal_places=8,
            null=True,
            blank=True,
            help_text=_(
                "Optional signed funding already included in P&L: negative "
                + "when paid and positive when received."
            ),
        )
    )
    created_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now_add=True)
    )
    updated_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now=True)
    )
    submitted_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True, editable=False)
    )
    filled_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True, editable=False)
    )
    closed_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True, editable=False)
    )
    cancelled_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True, editable=False)
    )

    class Meta:
        """Order journal decisions by analytical date and creation order."""

        ordering: ClassVar[list[str]] = ["-trade_date", "-created_at", "-id"]

    @override
    def __str__(self) -> str:
        """Return the canonical instrument and analytical date."""
        return f"{self.trading_pair.symbol} — {self.trade_date}"

    def get_absolute_url(self) -> str:
        """Return the localized workspace URL for this trade."""
        return reverse("trade_detail", kwargs={"trade_id": self.id})

    @override
    def clean(self) -> None:
        """Keep a trade inside one profile and supported market direction."""
        super().clean()
        trading_pair_id = getattr(self, "trading_pair_id", None)
        profile_id = getattr(self, "profile_id", None)
        if trading_pair_id is None or profile_id is None:
            return
        if self.trading_pair.profile_id != profile_id:
            raise ValidationError(
                {"trading_pair": _("Select a pair from this profile.")}
            )
        if (
            self.profile.market_type == TradingProfile.MarketType.SPOT.value
            and self.direction == self.Direction.SHORT.value
        ):
            raise ValidationError(
                {"direction": _("Spot profiles support LONG only.")}
            )

    @property
    def is_risk_reserved(self) -> bool:
        """Return whether this trade currently consumes profile risk."""
        return self.status in {
            self.Status.PENDING_ENTRY.value,
            self.Status.OPEN.value,
        }

    @property
    def planned_profit_amount(self) -> Decimal | None:
        """Return profit implied by the frozen executable risk and ratio."""
        if (
            self.planned_risk_amount is None
            or self.reward_multiple is None
        ):
            return None
        with localcontext() as context:
            context.prec = 96
            return self.planned_risk_amount * self.reward_multiple

    @property
    def atr_seventy_five_percent_reference(self) -> Decimal | None:
        """Return the fixed advisory range derived from frozen ATR."""
        if self.atr_value_snapshot is None:
            return None
        with localcontext() as context:
            context.prec = 96
            return self.atr_value_snapshot * Decimal("0.75")


class TradeChecklist(models.Model):
    """Fixed directional observations recorded for one trade decision."""

    ANSWER_CHOICES: ClassVar[tuple[tuple[str, object], ...]] = (
        (DirectionalValue.NEGATIVE.value, _("Negative")),
        (DirectionalValue.NEUTRAL.value, _("Neutral")),
        (DirectionalValue.POSITIVE.value, _("Positive")),
    )

    id: int
    trade_id: int

    trade: models.OneToOneField[Trade, Trade] = models.OneToOneField(
        Trade,
        on_delete=models.CASCADE,
        related_name="checklist",
    )
    schema_version: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(default=1, editable=False)
    )
    market_sentiment: models.CharField[str | None, str | None] = (
        models.CharField(
            _("Broad market sentiment"),
            max_length=10,
            choices=ANSWER_CHOICES,
            null=True,
            blank=True,
        )
    )
    information_background: models.CharField[str | None, str | None] = (
        models.CharField(
            _("Information background"),
            max_length=10,
            choices=ANSWER_CHOICES,
            null=True,
            blank=True,
        )
    )
    global_daily_direction: models.CharField[str | None, str | None] = (
        models.CharField(
            _("Global D1 direction"),
            max_length=10,
            choices=ANSWER_CHOICES,
            null=True,
            blank=True,
        )
    )
    local_daily_movement: models.CharField[str | None, str | None] = (
        models.CharField(
            _("Local D1 movement"),
            max_length=10,
            choices=ANSWER_CHOICES,
            null=True,
            blank=True,
        )
    )
    created_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now_add=True)
    )
    updated_at: models.DateTimeField[datetime, datetime] = (
        models.DateTimeField(auto_now=True)
    )

    @property
    def answers(self) -> ChecklistAnswers:
        """Return the persistence-independent checklist input."""
        return ChecklistAnswers(
            market_sentiment=self.market_sentiment,
            information_background=self.information_background,
            global_daily_direction=self.global_daily_direction,
            local_daily_movement=self.local_daily_movement,
        )

    @property
    def assessment(self) -> ChecklistAssessment:
        """Calculate the current advisory result for this trade."""
        return calculate_checklist_assessment(
            self.answers,
            selected_direction=self.trade.direction,
        )
