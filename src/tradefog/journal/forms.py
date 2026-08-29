"""Forms for user-managed journal configuration."""

# Django model forms are generic only in the static stub package; their
# runtime classes cannot be parameterized.
# pyright: reportAny=false, reportMissingTypeArgument=false, reportUnknownMemberType=false

from decimal import Decimal
from typing import ClassVar, cast, override

from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import (
    ACTIVE_MARKET_EXISTS,
    CapitalOperation,
    ProfileInstrument,
    TradingProfile,
)
from tradefog.journal.presentation import compact_decimal


class CompactDecimalInput(forms.NumberInput):
    """Render stored decimal values without insignificant trailing zeros."""

    @override
    def format_value(self, value: object) -> str:
        """Keep exact meaningful digits while removing storage padding."""
        return compact_decimal(value)


class TradingProfileForm(forms.ModelForm):
    """Collect identity, initial allocation, and profile risk policy."""

    class Meta:
        """Configure profile fields and their browser controls."""

        model: ClassVar[type[TradingProfile]] = TradingProfile
        fields: ClassVar[list[str]] = [
            "name",
            "capital_currency",
            "initial_capital",
            "risk_per_trade_percent",
            "risk_stop_capital",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "capital_currency": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "USDT"}
            ),
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
        data: QueryDict | None = None,
        *,
        instance: TradingProfile | None = None,
    ) -> None:
        """Mark the accounting asset immutable after instruments exist."""
        super().__init__(data=data, instance=instance)
        profile = cast(TradingProfile, self.instance)
        if profile.pk is not None and profile.instruments.exists():
            field = self.fields["capital_currency"]
            field.disabled = True
            field.help_text = _(
                "Capital currency is locked because instruments exist."
            )

    def clean_capital_currency(self) -> str:
        """Normalize the profile's accounting currency identifier."""
        value = self.cleaned_data.get("capital_currency")
        return value.strip().upper() if isinstance(value, str) else ""

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


class ProfileInstrumentForm(forms.ModelForm):
    """Collect a profile-scoped instrument and its precision limits."""

    profile: TradingProfile

    def __init__(
        self,
        profile: TradingProfile,
        data: QueryDict | None = None,
        *,
        instance: ProfileInstrument | None = None,
    ) -> None:
        """Bind market validation to the profile being configured."""
        bound_instance = instance or ProfileInstrument(profile=profile)
        super().__init__(data=data, instance=bound_instance)
        self.profile = profile

    class Meta:
        """Configure instrument fields and their browser controls."""

        model: ClassVar[type[ProfileInstrument]] = ProfileInstrument
        fields: ClassVar[list[str]] = [
            "base_asset",
            "display_name",
            "market_type",
            "price_step",
            "quantity_step",
            "minimum_quantity",
            "minimum_notional",
        ]
        help_texts: ClassVar[dict[str, object]] = {
            "market_type": _(
                "Spot supports LONG; linear supports LONG and SHORT."
            ),
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
            "base_asset": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "BTC"}
            ),
            "display_name": forms.TextInput(attrs={"class": "form-control"}),
            "market_type": forms.Select(attrs={"class": "form-select"}),
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

    def clean_base_asset(self) -> str:
        """Normalize the user-supplied side of the canonical pair."""
        value = self.cleaned_data.get("base_asset")
        return value.strip().upper() if isinstance(value, str) else ""

    @override
    def clean(self) -> dict[str, object] | None:
        """Enforce active market uniqueness within the selected profile."""
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        base_asset = cleaned_data.get("base_asset")
        market_type = cleaned_data.get("market_type")
        if not isinstance(base_asset, str) or not isinstance(market_type, str):
            return cleaned_data
        instance = cast(ProfileInstrument, self.instance)
        duplicates = ProfileInstrument.objects.filter(
            profile=self.profile,
            base_asset=base_asset,
            market_type=market_type,
            archived_at__isnull=True,
        ).exclude(pk=instance.pk)
        if duplicates.exists():
            self.add_error("base_asset", ACTIVE_MARKET_EXISTS)
        return cleaned_data
