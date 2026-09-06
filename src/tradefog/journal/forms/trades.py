"""Forms for journal trade decisions, checklists, and execution."""

import datetime
from typing import Any, ClassVar, final, override

from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from tradefog.journal.checklists import (
    ChecklistAnswers,
    DirectionalValue,
    calculate_checklist_assessment,
)
from tradefog.journal.models import (
    StrategyCapital,
    Trade,
    TradingProfile,
    TradingStrategy,
    VenueInstrument,
)
from tradefog.journal.models.enums import Direction, ProductKind
from tradefog.journal.widgets import CompactNumberInput


@final
class TradeDecisionForm(forms.ModelForm):
    """Create or edit one working trade draft."""

    planned_entry = forms.DecimalField(
        required=False,
        label=_("Planned entry"),
        widget=CompactNumberInput(
            attrs={
                "class": "form-control",
                "step": "any",
                "inputmode": "decimal",
                "id": "planned-entry",
            }
        ),
    )
    planned_stop = forms.DecimalField(
        required=False,
        label=_("Planned stop"),
        widget=CompactNumberInput(
            attrs={
                "class": "form-control",
                "step": "any",
                "inputmode": "decimal",
                "id": "planned-stop",
            }
        ),
    )

    product_kind = forms.ChoiceField(
        required=False,
        label=_("Product"),
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "trade-product-kind",
            }
        ),
    )

    class Meta:
        model: type[Trade] = Trade
        fields: tuple[str, ...] = (
            "profile",
            "strategy",
            "venue_instrument",
            "trade_date",
            "direction",
            "description_markdown",
        )
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "profile": forms.Select(
                attrs={
                    "class": "form-select",
                    "id": "trade-profile",
                }
            ),
            "strategy": forms.Select(
                attrs={
                    "class": "form-select",
                    "id": "trade-strategy",
                }
            ),
            "venue_instrument": forms.Select(
                attrs={
                    "class": "form-select",
                    "id": "trade-instrument",
                }
            ),
            "trade_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "id": "trade-date",
                }
            ),
            "direction": forms.RadioSelect(
                attrs={
                    "class": "btn-check",
                }
            ),
            "description_markdown": forms.Textarea(
                attrs={
                    "class": "tf-description-source",
                }
            ),
        }

    def __init__(
        self,
        *args: Any,
        user: Any,
        profile: TradingProfile | None = None,
        strategy: TradingStrategy | None = None,
        product_kind: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.user = user

        # Filter profiles to current user active profiles
        profile_field = self.fields["profile"]
        assert isinstance(profile_field, forms.ModelChoiceField)
        profile_field.queryset = TradingProfile.objects.filter(
            owner=user, is_archived=False
        ).select_related("venue", "wallet")
        profile_field.empty_label = _("Select a profile")

        # Determine active profile
        resolved_profile = (
            profile
            or getattr(self.instance, "profile", None)
            or profile_field.queryset.first()
        )

        strategy_field = self.fields["strategy"]
        assert isinstance(strategy_field, forms.ModelChoiceField)
        instrument_field = self.fields["venue_instrument"]
        assert isinstance(instrument_field, forms.ModelChoiceField)

        available_kinds: list[str] = []

        if resolved_profile:
            strategy_field.queryset = TradingStrategy.objects.filter(
                profile=resolved_profile, is_archived=False
            ).prefetch_related("capitals__wallet_asset__venue_wallet_asset")
            strategy_field.empty_label = _("Select a strategy")

            resolved_strategy = (
                strategy
                or getattr(self.instance, "strategy", None)
                or strategy_field.queryset.first()
            )

            if resolved_strategy:
                # Get settlement asset IDs allocated by this strategy
                allocated_asset_ids = StrategyCapital.objects.filter(
                    strategy=resolved_strategy, is_archived=False
                ).values_list(
                    "wallet_asset__venue_wallet_asset__asset_id", flat=True
                )

                # All instruments supported by venue and allocated assets
                all_instruments = (
                    VenueInstrument.objects.filter(
                        venue=resolved_profile.venue,
                        is_active=True,
                    )
                    .filter(
                        Q(settlement_asset_id__in=allocated_asset_ids)
                        | Q(
                            settlement_asset__isnull=True,
                            pair__quote_id__in=allocated_asset_ids,
                        )
                    )
                    .select_related("pair__base", "pair__quote")
                )

                available_kinds = sorted(
                    set(all_instruments.values_list("product", flat=True))
                )
                self.fields["product_kind"].choices = [
                    (kind, ProductKind(kind).label) for kind in available_kinds
                ]

                # Determine active product kind
                resolved_kind = (
                    product_kind
                    or self.data.get("product_kind")
                    or (
                        self.instance.venue_instrument.product
                        if self.instance.pk and self.instance.venue_instrument
                        else None
                    )
                    or (available_kinds[0] if available_kinds else None)
                )
                self.initial["product_kind"] = resolved_kind

                if resolved_kind:
                    instrument_field.queryset = all_instruments.filter(
                        product=resolved_kind
                    )
                else:
                    instrument_field.queryset = all_instruments
            else:
                self.fields["product_kind"].choices = []
                instrument_field.queryset = VenueInstrument.objects.none()

            instrument_field.empty_label = _("Select an instrument")
        else:
            strategy_field.queryset = TradingStrategy.objects.none()
            self.fields["product_kind"].choices = []
            instrument_field.queryset = VenueInstrument.objects.none()

        if not self.is_bound and not self.instance.pk:
            self.initial["trade_date"] = datetime.datetime.now(
                datetime.UTC
            ).date()
            self.initial["direction"] = Direction.LONG

    @override
    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        profile: TradingProfile | None = cleaned_data.get("profile")
        strategy: TradingStrategy | None = cleaned_data.get("strategy")
        instrument: VenueInstrument | None = cleaned_data.get(
            "venue_instrument"
        )
        direction: str | None = cleaned_data.get("direction")

        if not profile or not strategy or not instrument:
            return cleaned_data

        if strategy.profile_id != profile.pk:
            raise forms.ValidationError(
                _("Selected strategy does not belong to the selected profile.")
            )

        if instrument.venue_id != profile.venue_id:
            raise forms.ValidationError(
                _(
                    "Selected instrument does not belong to the profile's venue."
                )
            )

        # Check product direction compatibility
        if (
            instrument.product == ProductKind.SPOT.value
            and direction != Direction.LONG.value
        ):
            raise forms.ValidationError(
                _("Spot instruments only support LONG direction.")
            )
        if (
            instrument.product == ProductKind.CASH_EQUITY.value
            and direction != Direction.LONG.value
        ):
            raise forms.ValidationError(
                _("Cash equity instruments only support LONG direction.")
            )

        # Verify strategy allocation in instrument settlement asset
        effective_settlement_id = (
            instrument.settlement_asset_id or instrument.pair.quote_id
        )
        has_allocation = StrategyCapital.objects.filter(
            strategy=strategy,
            wallet_asset__venue_wallet_asset__asset_id=effective_settlement_id,
            is_archived=False,
        ).exists()

        if not has_allocation:
            raise forms.ValidationError(
                _(
                    "Strategy has no capital allocation for this instrument's settlement asset."
                )
            )

        return cleaned_data


@final
class ChecklistForm(forms.Form):
    """Advisory directional checklist form."""

    market_sentiment = forms.ChoiceField(
        choices=[
            (DirectionalValue.NEGATIVE.value, _("Bearish")),
            (DirectionalValue.NEUTRAL.value, _("Neutral")),
            (DirectionalValue.POSITIVE.value, _("Bullish")),
        ],
        widget=forms.RadioSelect(attrs={"class": "btn-check"}),
        required=False,
    )
    information_background = forms.ChoiceField(
        choices=[
            (DirectionalValue.NEGATIVE.value, _("Negative")),
            (DirectionalValue.NEUTRAL.value, _("Neutral")),
            (DirectionalValue.POSITIVE.value, _("Positive")),
        ],
        widget=forms.RadioSelect(attrs={"class": "btn-check"}),
        required=False,
    )
    global_daily_direction = forms.ChoiceField(
        choices=[
            (DirectionalValue.NEGATIVE.value, _("Down")),
            (DirectionalValue.NEUTRAL.value, _("Sideways")),
            (DirectionalValue.POSITIVE.value, _("Up")),
        ],
        widget=forms.RadioSelect(attrs={"class": "btn-check"}),
        required=False,
    )
    local_daily_movement = forms.ChoiceField(
        choices=[
            (DirectionalValue.NEGATIVE.value, _("Down")),
            (DirectionalValue.NEUTRAL.value, _("Sideways")),
            (DirectionalValue.POSITIVE.value, _("Up")),
        ],
        widget=forms.RadioSelect(attrs={"class": "btn-check"}),
        required=False,
    )

    def assessment(self, selected_direction: str | None = None) -> Any:
        """Calculate the checklist assessment result from current cleaned data."""
        answers = ChecklistAnswers(
            market_sentiment=self.cleaned_data.get("market_sentiment"),
            information_background=self.cleaned_data.get(
                "information_background"
            ),
            global_daily_direction=self.cleaned_data.get(
                "global_daily_direction"
            ),
            local_daily_movement=self.cleaned_data.get("local_daily_movement"),
        )
        return calculate_checklist_assessment(
            answers, selected_direction=selected_direction
        )
