"""Forms for owner-scoped trading strategies and their allocations."""

from decimal import Decimal
from typing import Any, ClassVar, final

from django import forms
from django.forms import ModelChoiceField
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import (
    StrategyCapital,
    TradingStrategy,
    WalletAsset,
)
from tradefog.journal.services import settlement_asset_ids
from tradefog.journal.widgets import CompactNumberInput


@final
class TradingStrategyForm(forms.ModelForm):
    """Create or edit one owner-scoped trading strategy."""

    class Meta:
        model: type[TradingStrategy] = TradingStrategy
        fields: tuple[str, ...] = (
            "name",
            "description",
            "risk_percent",
            "reward_multiple",
        )
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Breakout"),
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
            "risk_percent": CompactNumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "inputmode": "decimal",
                }
            ),
            "reward_multiple": CompactNumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.1",
                    "inputmode": "decimal",
                }
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["name"].help_text = _(
            "A short label for this risk and reward cohort."
        )
        self.fields["description"].help_text = _(
            "Optional notes about the strategy."
        )
        self.fields["risk_percent"].help_text = _(
            "Percent of the allocation risked per trade."
        )
        self.fields["reward_multiple"].help_text = _(
            "Take-profit multiple of the risked amount."
        )
        if self.instance.pk:
            self.fields["risk_percent"].disabled = True
            self.fields["reward_multiple"].disabled = True
            self.fields["risk_percent"].help_text = _(
                "Locked after the strategy is created."
            )
            self.fields["reward_multiple"].help_text = _(
                "Locked after the strategy is created."
            )

    def clean_risk_percent(self) -> Decimal:
        risk = self.cleaned_data["risk_percent"]
        if risk <= Decimal(0):
            raise forms.ValidationError(
                _("Risk percent must be positive.")
            )
        return risk

    def clean_reward_multiple(self) -> Decimal:
        reward = self.cleaned_data["reward_multiple"]
        if reward <= Decimal(0):
            raise forms.ValidationError(
                _("Reward multiple must be positive.")
            )
        return reward


@final
class StrategyCapitalForm(forms.Form):
    """Allocate a fixed capital of one strategy to one wallet asset.

    The strategy is supplied by the caller so the wallet-asset choices can be
    limited to the profile's wallet assets that settle an active instrument on
    the venue, excluding assets already allocated by this strategy. Archived
    allocations keep their slot, so their fixed capital can never be replaced.
    """

    strategy: TradingStrategy

    wallet_asset = forms.ModelChoiceField(
        queryset=WalletAsset.objects.none(),
        label=_("Wallet asset"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    capital = forms.DecimalField(
        label=_("Capital"),
        min_value=Decimal("0.000000000000000001"),
        widget=CompactNumberInput(
            attrs={
                "class": "form-control",
                "step": "any",
                "inputmode": "decimal",
            }
        ),
    )

    def __init__(self, *args: Any, strategy: TradingStrategy, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.strategy = strategy
        profile = strategy.profile
        settlement_ids = settlement_asset_ids(profile.venue)
        allocated = strategy.capitals.values_list(
            "wallet_asset_id", flat=True
        )
        field = self.fields["wallet_asset"]
        assert isinstance(field, ModelChoiceField)
        field.queryset = (
            WalletAsset.objects.filter(
                wallet=profile.wallet,
                venue_wallet_asset__asset_id__in=settlement_ids,
            )
            .exclude(pk__in=allocated)
            .select_related("venue_wallet_asset__asset")
            .order_by("venue_wallet_asset__asset__symbol")
        )
        field.empty_label = _("Choose an asset")
        field.help_text = _(
            "A wallet asset that settles an active instrument on the venue."
        )
        self.fields["capital"].help_text = _(
            "Fixed capital committed to this asset."
        )

    def save(self) -> StrategyCapital:
        """Persist a new allocation for the bound strategy."""
        return StrategyCapital.objects.create(
            strategy=self.strategy,
            wallet_asset=self.cleaned_data["wallet_asset"],
            capital=self.cleaned_data["capital"],
        )