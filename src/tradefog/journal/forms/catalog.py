"""Forms for the shared, staff-managed reference catalog."""

from typing import Any, ClassVar, cast, final, override

from django import forms
from django.forms import ModelChoiceField
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import Asset, TradingPair


@final
class AssetForm(forms.ModelForm):
    """Create or edit a shared catalog asset."""

    class Meta:
        model: type[Asset] = Asset
        fields: tuple[str, ...] = ("symbol", "name", "asset_type")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "symbol": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("BTC"),
                    "autocomplete": "off",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Bitcoin"),
                    "autocomplete": "off",
                }
            ),
            "asset_type": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["symbol"].help_text = _(
            "Upper-case symbol, unique across the catalog."
        )
        self.fields["name"].help_text = _("Common display name.")
        self.fields["asset_type"].help_text = _(
            "The unambiguous class of this asset."
        )

    def clean_symbol(self) -> str:
        """Normalize the symbol and reject a case-insensitive duplicate."""
        symbol = self.cleaned_data["symbol"].strip().upper()
        if Asset.objects.filter(symbol__iexact=symbol).exists():
            raise forms.ValidationError(
                _("An asset with this symbol already exists.")
            )
        return symbol


@final
class TradingPairForm(forms.ModelForm):
    """Create or edit a shared catalog trading pair.

    The canonical symbol is derived from the selected base and quote assets
    rather than entered by hand, so the form only asks for the two halves.
    """

    class Meta:
        model: type[TradingPair] = TradingPair
        fields: tuple[str, ...] = ("base", "quote")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "base": forms.Select(attrs={"class": "form-select"}),
            "quote": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        base = cast(ModelChoiceField, self.fields["base"])
        quote = cast(ModelChoiceField, self.fields["quote"])
        base.queryset = Asset.objects.order_by("symbol")
        quote.queryset = Asset.objects.order_by("symbol")
        base.help_text = _("The asset that is bought or sold in the pair.")
        quote.help_text = _("The asset that prices the base asset.")

    @override
    def clean(self) -> dict[str, Any]:
        """Reject duplicate and same-asset pairs.

        The canonical symbol is derived from the halves, so the meaningful
        collisions are a shared base/quote combination and a pair whose base
        equals its quote.
        """
        cleaned = super().clean()
        base = cleaned.get("base")
        quote = cleaned.get("quote")
        if base and quote:
            if base.pk == quote.pk:
                self.add_error(
                    "quote", _("Base and quote must be different assets.")
                )
            elif (
                TradingPair.objects.filter(base=base, quote=quote)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                self.add_error(
                    "base", _("This trading pair already exists.")
                )
        return cleaned

    @override
    def save(self, commit: bool = True) -> TradingPair:
        """Persist the pair, deriving its canonical symbol from the halves."""
        instance = super().save(commit=False)
        instance.canonical_symbol = (
            f"{instance.base.symbol}/{instance.quote.symbol}".upper()
        )
        if commit:
            instance.save()
        return instance