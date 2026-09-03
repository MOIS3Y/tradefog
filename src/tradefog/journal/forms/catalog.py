"""Forms for the shared, staff-managed reference catalog."""

from typing import Any, ClassVar, final

from django import forms
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import Asset


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