"""Forms for user-managed journal configuration."""

# Django model forms are generic only in the static stub package; their
# runtime classes cannot be parameterized.
# pyright: reportAny=false, reportMissingTypeArgument=false, reportUnknownMemberType=false

from decimal import Decimal
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
