"""Forms for user-managed journal configuration."""

# Django model forms are generic only in the static stub package; their
# runtime classes cannot be parameterized.
# pyright: reportAny=false, reportMissingTypeArgument=false, reportUnknownMemberType=false

from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar, cast, override

from django import forms
from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tradefog.accounts.models import User
from tradefog.journal.models import (
    ACTIVE_PAIR_EXISTS,
    Asset,
    CapitalOperation,
    ProfileTradingPair,
    Trade,
    TradeChecklist,
    TradingProfile,
)
from tradefog.journal.presentation import compact_decimal


class CompactDecimalInput(forms.NumberInput):
    """Render stored decimal values without insignificant trailing zeros."""

    @override
    def format_value(self, value: object) -> str:
        """Keep exact meaningful digits while removing storage padding."""
        return compact_decimal(value)


class ProfileTradingPairChoiceField(forms.ModelChoiceField):
    """Present a profile pair as its canonical structured identity."""

    @override
    def label_from_instance(self, obj: object) -> str:
        """Show the canonical pair without exchange-specific formatting."""
        trading_pair = cast(ProfileTradingPair, obj)
        return trading_pair.symbol


class AnalyticsPeriod(StrEnum):
    """Supported rolling and explicit analytics date ranges."""

    ALL = "ALL"
    DAYS_30 = "30D"
    DAYS_90 = "90D"
    YEAR_TO_DATE = "YTD"
    YEAR_1 = "1Y"
    CUSTOM = "CUSTOM"


class AnalyticsProfileChoiceField(forms.ModelChoiceField):
    """Present profiles consistently in the analytics filter."""

    @override
    def label_from_instance(self, obj: object) -> str:
        """Show the user-defined profile name."""
        return cast(TradingProfile, obj).name


class AnalyticsPairChoiceField(forms.ModelChoiceField):
    """Present a canonical pair inside an explicit profile filter."""

    @override
    def label_from_instance(self, obj: object) -> str:
        """Show only the pair because the profile is selected separately."""
        return cast(ProfileTradingPair, obj).symbol


class AnalyticsFilterForm(forms.Form):
    """Validate owner-scoped dimensions and analytics date ranges."""

    period: forms.ChoiceField = forms.ChoiceField(
        label=_("Period"),
        required=False,
        initial=AnalyticsPeriod.ALL.value,
        choices=(
            (AnalyticsPeriod.ALL.value, _("All time")),
            (AnalyticsPeriod.DAYS_30.value, _("Last 30 days")),
            (AnalyticsPeriod.DAYS_90.value, _("Last 90 days")),
            (AnalyticsPeriod.YEAR_TO_DATE.value, _("Year to date")),
            (AnalyticsPeriod.YEAR_1.value, _("Last year")),
            (AnalyticsPeriod.CUSTOM.value, _("Custom range")),
        ),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from: forms.DateField = forms.DateField(
        label=_("From"),
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date"}
        ),
    )
    date_to: forms.DateField = forms.DateField(
        label=_("To"),
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date"}
        ),
    )
    profile: AnalyticsProfileChoiceField = AnalyticsProfileChoiceField(
        label=_("Profile"),
        required=False,
        queryset=TradingProfile.objects.none(),
        empty_label=_("All profiles"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    market_type: forms.ChoiceField = forms.ChoiceField(
        label=_("Market"),
        required=False,
        choices=(("", _("All markets")), *TradingProfile.MarketType.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    trading_pair: AnalyticsPairChoiceField = AnalyticsPairChoiceField(
        label=_("Trading pair"),
        required=False,
        queryset=ProfileTradingPair.objects.none(),
        empty_label=_("All pairs"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(
        self,
        owner: User,
        data: QueryDict | None = None,
    ) -> None:
        """Enable pairs only within one selected owner-scoped profile."""
        normalized_data = data.copy() if data is not None else None
        selected_profile_id: int | None = None
        if normalized_data is not None:
            raw_profile_id = normalized_data.get("profile")
            try:
                requested_profile_id = int(raw_profile_id or "")
            except ValueError:
                requested_profile_id = None
            if (
                requested_profile_id is not None
                and TradingProfile.objects.filter(
                    id=requested_profile_id,
                    owner=owner,
                ).exists()
            ):
                selected_profile_id = requested_profile_id

            raw_pair_id = normalized_data.get("trading_pair")
            pair_matches_profile = (
                selected_profile_id is not None
                and raw_pair_id
                and ProfileTradingPair.objects.filter(
                    id=raw_pair_id,
                    profile_id=selected_profile_id,
                ).exists()
            )
            if not pair_matches_profile:
                _removed_pair_values = normalized_data.pop(
                    "trading_pair",
                    None,
                )

        super().__init__(data=normalized_data)
        profile_field = cast(
            AnalyticsProfileChoiceField,
            self.fields["profile"],
        )
        profile_field.queryset = TradingProfile.objects.filter(owner=owner)
        pair_field = cast(
            AnalyticsPairChoiceField,
            self.fields["trading_pair"],
        )
        pair_field.queryset = ProfileTradingPair.objects.filter(
            profile_id=selected_profile_id,
            profile__owner=owner,
        ).select_related("asset", "profile__capital_asset")
        pair_field.disabled = selected_profile_id is None
        if pair_field.disabled:
            pair_field.empty_label = _("Unavailable")
            pair_field.widget.attrs["title"] = _(
                "Choose a profile to enable this filter."
            )

    @override
    def clean(self) -> dict[str, object] | None:
        """Resolve rolling periods and keep pair/profile filters coherent."""
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None

        period = cleaned_data.get("period") or AnalyticsPeriod.ALL.value
        today = timezone.localdate()
        if period == AnalyticsPeriod.DAYS_30.value:
            cleaned_data["date_from"] = today - timedelta(days=29)
            cleaned_data["date_to"] = today
        elif period == AnalyticsPeriod.DAYS_90.value:
            cleaned_data["date_from"] = today - timedelta(days=89)
            cleaned_data["date_to"] = today
        elif period == AnalyticsPeriod.YEAR_TO_DATE.value:
            cleaned_data["date_from"] = today.replace(month=1, day=1)
            cleaned_data["date_to"] = today
        elif period == AnalyticsPeriod.YEAR_1.value:
            cleaned_data["date_from"] = today - timedelta(days=364)
            cleaned_data["date_to"] = today
        elif period == AnalyticsPeriod.ALL.value:
            cleaned_data["date_from"] = None
            cleaned_data["date_to"] = None

        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            self.add_error(
                "date_to",
                _("The end date must not be earlier than the start date."),
            )

        profile = cleaned_data.get("profile")
        trading_pair = cleaned_data.get("trading_pair")
        if (
            isinstance(profile, TradingProfile)
            and isinstance(trading_pair, ProfileTradingPair)
            and trading_pair.profile_id != profile.id
        ):
            self.add_error(
                "trading_pair",
                _("Select a trading pair from the chosen profile."),
            )
        return cleaned_data


class AssetForm(forms.ModelForm):
    """Create or correct one user-owned canonical asset."""

    class Meta:
        """Expose stable identity and lightweight classification fields."""

        model: ClassVar[type[Asset]] = Asset
        fields: ClassVar[list[str]] = ["symbol", "name", "asset_class"]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "symbol": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "BTC"}
            ),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Bitcoin"}
            ),
            "asset_class": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_symbol(self) -> str:
        """Normalize symbols before uniqueness validation and persistence."""
        value = self.cleaned_data.get("symbol")
        return value.strip().upper() if isinstance(value, str) else ""


class TradingProfileForm(forms.ModelForm):
    """Collect identity, initial allocation, and profile risk policy."""

    class Meta:
        """Configure profile fields and their browser controls."""

        model: ClassVar[type[TradingProfile]] = TradingProfile
        fields: ClassVar[list[str]] = [
            "name",
            "capital_asset",
            "market_type",
            "initial_capital",
            "risk_per_trade_percent",
            "risk_stop_capital",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "capital_asset": forms.Select(attrs={"class": "form-select"}),
            "market_type": forms.Select(attrs={"class": "form-select"}),
            "initial_capital": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "risk_per_trade_percent": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "0.01"}
            ),
            "risk_stop_capital": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
        }

    def __init__(
        self,
        owner: User,
        data: QueryDict | None = None,
        *,
        instance: TradingProfile | None = None,
    ) -> None:
        """Limit assets by owner and lock submitted profile policy."""
        bound_instance = instance or TradingProfile(owner=owner)
        super().__init__(data=data, instance=bound_instance)
        asset_field = cast(  # pyright: ignore[reportUnknownVariableType]
            forms.ModelChoiceField,
            self.fields["capital_asset"],
        )
        profile = cast(TradingProfile, self.instance)
        available_assets = Q(archived_at__isnull=True)
        if profile.pk is not None:
            available_assets |= Q(pk=profile.capital_asset_id)
        asset_field.queryset = Asset.objects.filter(
            available_assets,
            owner=owner,
        )
        if profile.pk is not None and profile.trading_pairs.exists():
            for field_name in ("capital_asset", "market_type"):
                self.fields[field_name].disabled = True
            self.fields["capital_asset"].help_text = _(
                "Capital asset is locked because trading pairs exist."
            )
            self.fields["market_type"].help_text = _(
                "Market type is locked because trading pairs exist."
            )
        if (
            profile.pk is not None
            and profile.trades.exclude(
                status=Trade.Status.DRAFT.value
            ).exists()
        ):
            initial_capital = self.fields["initial_capital"]
            initial_capital.disabled = True
            initial_capital.help_text = _(
                "Initial capital is locked because a trade was submitted."
            )
            risk_percent = self.fields["risk_per_trade_percent"]
            risk_percent.disabled = True
            risk_percent.help_text = _(
                "Risk per trade is locked because a trade was submitted."
            )

    @override
    def clean(self) -> dict[str, object] | None:
        """Keep the explicit risk stop below projected current capital."""
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        initial_capital = cleaned_data.get("initial_capital")
        risk_stop_capital = cleaned_data.get("risk_stop_capital")
        if not isinstance(initial_capital, Decimal) or not isinstance(
            risk_stop_capital, Decimal
        ):
            return cleaned_data
        profile = cast(TradingProfile, self.instance)
        projected_capital = initial_capital
        if profile.pk is not None:
            projected_capital += (
                profile.capital_operation_total + profile.realized_pnl_total
            )
        if risk_stop_capital >= projected_capital:
            self.add_error(
                "risk_stop_capital",
                _("Risk stop must be lower than current capital."),
            )
        return cleaned_data


class CapitalOperationForm(forms.ModelForm):
    """Collect an amount and note for one fixed capital-operation type."""

    operation_type: str

    def __init__(
        self,
        operation_type: str,
        data: QueryDict | None = None,
        *,
        instance: CapitalOperation | None = None,
    ) -> None:
        """Bind the direction outside user-controlled form data."""
        bound_instance = instance or CapitalOperation(
            operation_type=operation_type
        )
        super().__init__(data=data, instance=bound_instance)
        self.operation_type = operation_type
        if operation_type == CapitalOperation.Type.DEPOSIT.value:
            self.fields["amount"].label = _("Deposit amount")
        else:
            self.fields["amount"].label = _("Withdrawal amount")

    class Meta:
        """Expose only correctable capital-operation facts."""

        model: ClassVar[type[CapitalOperation]] = CapitalOperation
        fields: ClassVar[list[str]] = ["amount", "note"]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "amount": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "note": forms.TextInput(
                attrs={"class": "form-control", "maxlength": "200"}
            ),
        }


class ProfileTradingPairForm(forms.ModelForm):
    """Collect an asset pairing and provider-specific execution limits."""

    profile: TradingProfile

    def __init__(
        self,
        profile: TradingProfile,
        data: QueryDict | None = None,
        *,
        instance: ProfileTradingPair | None = None,
    ) -> None:
        """Bind market validation to the profile being configured."""
        bound_instance = instance or ProfileTradingPair(profile=profile)
        super().__init__(data=data, instance=bound_instance)
        self.profile = profile
        asset_field = cast(  # pyright: ignore[reportUnknownVariableType]
            forms.ModelChoiceField,
            self.fields["asset"],
        )
        available_assets = Q(archived_at__isnull=True)
        if instance is not None:
            available_assets |= Q(pk=instance.asset_id)
        asset_field.queryset = Asset.objects.filter(
            available_assets,
            owner=profile.owner,
        ).exclude(pk=profile.capital_asset_id)

    class Meta:
        """Configure instrument fields and their browser controls."""

        model: ClassVar[type[ProfileTradingPair]] = ProfileTradingPair
        fields: ClassVar[list[str]] = [
            "asset",
            "price_step",
            "quantity_step",
            "minimum_quantity",
            "minimum_notional",
        ]
        help_texts: ClassVar[dict[str, object]] = {
            "price_step": _(
                "The smallest allowed change in the quoted price."
            ),
            "quantity_step": _(
                "The smallest allowed change in the order quantity."
            ),
            "minimum_quantity": _(
                "Leave empty when the market has no minimum quantity."
            ),
        }
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "price_step": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "quantity_step": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "minimum_quantity": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "minimum_notional": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
        }

    @override
    def clean(self) -> dict[str, object] | None:
        """Enforce active market uniqueness within the selected profile."""
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        asset = cleaned_data.get("asset")
        if not isinstance(asset, Asset):
            return cleaned_data
        instance = cast(ProfileTradingPair, self.instance)
        duplicates = ProfileTradingPair.objects.filter(
            profile=self.profile,
            asset=asset,
            archived_at__isnull=True,
        ).exclude(pk=instance.pk)
        if duplicates.exists():
            self.add_error("asset", ACTIVE_PAIR_EXISTS)
        return cleaned_data


class TradeDraftForm(forms.ModelForm):
    """Collect editable facts for one profile-owned trade draft."""

    trading_pair: forms.ModelChoiceField = ProfileTradingPairChoiceField(
        label=_("Trading pair"),
        queryset=ProfileTradingPair.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    profile: TradingProfile

    def __init__(
        self,
        profile: TradingProfile,
        data: QueryDict | None = None,
        *,
        instance: Trade | None = None,
        plan_url: str | None = None,
    ) -> None:
        """Bind instrument choices and optional reactive plan updates."""
        bound_instance = instance or Trade(
            profile=profile,
            trade_date=timezone.localdate(),
        )
        super().__init__(data=data, instance=bound_instance)
        self.profile = profile
        trading_pairs = profile.trading_pairs.filter(
            archived_at__isnull=True
        )
        pair_field = cast(  # pyright: ignore[reportUnknownVariableType]
            forms.ModelChoiceField,
            self.fields["trading_pair"],
        )
        pair_field.queryset = trading_pairs
        direction_field = cast(forms.ChoiceField, self.fields["direction"])
        if profile.market_type == TradingProfile.MarketType.SPOT.value:
            direction_field.choices = [
                (Trade.Direction.LONG.value, Trade.Direction.LONG.label)
            ]
        else:
            direction_field.choices = Trade.Direction.choices
        if plan_url is not None:
            reactive_attributes = {
                "hx-post": plan_url,
                "hx-trigger": "change, input changed delay:300ms",
                "hx-target": "#trade-plan",
                "hx-swap": "innerHTML",
                "hx-include": "#trade-form",
            }
            for field_name in (
                "trading_pair",
                "direction",
                "planned_entry",
                "planned_stop",
            ):
                self.fields[field_name].widget.attrs.update(
                    reactive_attributes
                )

    class Meta:
        """Expose only draft facts that the owner may edit."""

        model: ClassVar[type[Trade]] = Trade
        fields: ClassVar[list[str]] = [
            "trade_date",
            "trading_pair",
            "direction",
            "planned_entry",
            "planned_stop",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "trade_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "form-control", "type": "date"}
            ),
            "direction": forms.RadioSelect(
                attrs={
                    "class": "btn-check",
                    "autocomplete": "off",
                }
            ),
            "planned_entry": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "planned_stop": CompactDecimalInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
        }


class TradeChecklistForm(forms.ModelForm):
    """Collect the fixed advisory observations for a trade draft."""

    FIELD_CHOICES: ClassVar[dict[str, tuple[tuple[str, object], ...]]] = {
        "market_sentiment": (
            ("NEGATIVE", _("Bearish")),
            ("NEUTRAL", _("Neutral")),
            ("POSITIVE", _("Bullish")),
        ),
        "information_background": (
            ("NEGATIVE", _("Negative")),
            ("NEUTRAL", _("Neutral")),
            ("POSITIVE", _("Positive")),
        ),
        "global_daily_direction": (
            ("NEGATIVE", _("Down")),
            ("NEUTRAL", _("Sideways")),
            ("POSITIVE", _("Up")),
        ),
        "local_daily_movement": (
            ("NEGATIVE", _("Down")),
            ("NEUTRAL", _("Sideways")),
            ("POSITIVE", _("Up")),
        ),
    }

    def __init__(
        self,
        data: QueryDict | None = None,
        *,
        instance: TradeChecklist | None = None,
        assessment_url: str | None = None,
    ) -> None:
        """Configure contextual labels and optional reactive assessment."""
        super().__init__(data=data, instance=instance, prefix="checklist")
        for field_name, choices in self.FIELD_CHOICES.items():
            field = cast(forms.ChoiceField, self.fields[field_name])
            field.choices = choices
            if assessment_url is not None:
                field.widget.attrs.update(
                    {
                        "hx-post": assessment_url,
                        "hx-trigger": "change",
                        "hx-target": "#checklist-assessment",
                        "hx-swap": "innerHTML",
                        "hx-include": "#trade-form",
                    }
                )

    class Meta:
        """Expose only the fixed version-one directional observations."""

        model: ClassVar[type[TradeChecklist]] = TradeChecklist
        fields: ClassVar[list[str]] = [
            "market_sentiment",
            "information_background",
            "global_daily_direction",
            "local_daily_movement",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "market_sentiment": forms.RadioSelect(
                attrs={"class": "btn-check"}
            ),
            "information_background": forms.RadioSelect(
                attrs={"class": "btn-check"}
            ),
            "global_daily_direction": forms.RadioSelect(
                attrs={"class": "btn-check"}
            ),
            "local_daily_movement": forms.RadioSelect(
                attrs={"class": "btn-check"}
            ),
        }


class CloseTradeForm(forms.Form):
    """Collect the one aggregate result used to close an open trade."""

    realized_pnl: forms.DecimalField = forms.DecimalField(
        label=_("Realized P&L"),
        max_digits=24,
        decimal_places=8,
        help_text=_("Net result including fees, slippage, and manual exits."),
        widget=CompactDecimalInput(attrs={"class": "form-control"}),
    )
    actual_exit_price: forms.DecimalField = forms.DecimalField(
        label=_("Actual exit price"),
        max_digits=24,
        decimal_places=12,
        min_value=Decimal("0.000000000001"),
        required=False,
        help_text=_("Optional reference price for the fully closed position."),
        widget=CompactDecimalInput(
            attrs={"class": "form-control", "min": "0", "step": "any"}
        ),
    )
    commission_total: forms.DecimalField = forms.DecimalField(
        label=_("Commission"),
        max_digits=24,
        decimal_places=8,
        min_value=Decimal(0),
        required=False,
        help_text=_("Optional reference amount already included in net P&L."),
        widget=CompactDecimalInput(
            attrs={"class": "form-control", "min": "0", "step": "any"}
        ),
    )
    funding_result: forms.DecimalField = forms.DecimalField(
        label=_("Funding result"),
        max_digits=24,
        decimal_places=8,
        required=False,
        help_text=_(
            "Optional signed amount already included in net P&L: negative "
            + "when paid, positive when received."
        ),
        widget=CompactDecimalInput(attrs={"class": "form-control"}),
    )

    def __init__(
        self,
        data: QueryDict | None = None,
        *,
        trade: Trade,
        initial: dict[str, object] | None = None,
    ) -> None:
        """Show funding only for linear perpetual profiles."""
        super().__init__(data=data, initial=initial)
        if trade.profile.market_type == TradingProfile.MarketType.SPOT.value:
            del self.fields["funding_result"]


class TradeDateForm(forms.ModelForm):
    """Correct the analytical date without changing execution timestamps."""

    class Meta:
        """Expose only the editable analytical date."""

        model: ClassVar[type[Trade]] = Trade
        fields: ClassVar[list[str]] = ["trade_date"]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "trade_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "form-control", "type": "date"}
            )
        }
