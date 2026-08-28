"""Forms for user-managed journal configuration."""

# Django model forms are generic only in the static stub package; their
# runtime classes cannot be parameterized.
# pyright: reportAny=false, reportMissingTypeArgument=false, reportUnknownMemberType=false

from typing import ClassVar, cast

from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import ProfileInstrument, TradingProfile


class TradingProfileForm(forms.ModelForm):
    """Collect the allocation and next-period defaults for a profile."""

    class Meta:
        """Configure profile fields and their browser controls."""

        model: ClassVar[type[TradingProfile]] = TradingProfile
        fields: ClassVar[list[str]] = [
            "name",
            "venue_name",
            "capital_currency",
            "initial_capital",
            "risk_per_trade_percent",
            "reward_multiple",
            "daily_risk_limit_percent",
            "monthly_target_percent",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "venue_name": forms.TextInput(attrs={"class": "form-control"}),
            "capital_currency": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "USD"}
            ),
            "initial_capital": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "risk_per_trade_percent": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.001"}
            ),
            "reward_multiple": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.01"}
            ),
            "daily_risk_limit_percent": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.001"}
            ),
            "monthly_target_percent": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.001"}
            ),
        }

    def clean_capital_currency(self) -> str:
        """Normalize the profile's accounting currency identifier."""
        value = self.cleaned_data.get("capital_currency")
        return value.strip().upper() if isinstance(value, str) else ""


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
        """Bind symbol validation to the profile being configured."""
        super().__init__(data=data, instance=instance)
        self.profile = profile

    class Meta:
        """Configure instrument fields and their browser controls."""

        model: ClassVar[type[ProfileInstrument]] = ProfileInstrument
        fields: ClassVar[list[str]] = [
            "symbol",
            "display_name",
            "market_type",
            "price_step",
            "quantity_step",
            "minimum_quantity",
            "minimum_notional",
        ]
        help_texts: ClassVar[dict[str, object]] = {
            "minimum_quantity": _("Leave empty when the venue has no limit."),
        }
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "symbol": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "BTC/USDT"}
            ),
            "display_name": forms.TextInput(attrs={"class": "form-control"}),
            "market_type": forms.Select(attrs={"class": "form-select"}),
            "price_step": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "quantity_step": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "minimum_quantity": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
            "minimum_notional": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "any"}
            ),
        }

    def clean_symbol(self) -> str:
        """Normalize and enforce active symbol uniqueness per profile."""
        value = self.cleaned_data.get("symbol")
        symbol = value.strip().upper() if isinstance(value, str) else ""
        instance = cast(ProfileInstrument, self.instance)
        duplicates = ProfileInstrument.objects.filter(
            profile=self.profile,
            symbol=symbol,
            archived_at__isnull=True,
        ).exclude(pk=instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(
                _("An active instrument with this symbol already exists.")
            )
        return symbol
