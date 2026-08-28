"""Forms for user-managed journal configuration."""

# Django model forms are generic only in the static stub package; their
# runtime classes cannot be parameterized.
# pyright: reportAny=false, reportMissingTypeArgument=false, reportUnknownMemberType=false

from typing import ClassVar, cast, override

from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import (
    ACTIVE_MARKET_EXISTS,
    ProfileInstrument,
    TradingProfile,
)


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
            "minimum_quantity": _("Leave empty when the venue has no limit."),
        }
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "base_asset": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "BTC"}
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
