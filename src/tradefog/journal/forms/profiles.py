"""Forms for owner-scoped trading profiles and their wallet."""

from typing import Any, ClassVar, final

from django import forms
from django.forms import ModelChoiceField
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import TradingProfile, Venue


@final
class TradingProfileForm(forms.ModelForm):
    """Create or edit an owner-scoped trading profile.

    The venue select offers every shared catalog venue. Venue binding
    is permanent for the profile's lifetime.
    """

    class Meta:
        model: type[TradingProfile] = TradingProfile
        fields: tuple[str, ...] = ("name", "venue")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Bybit Main"),
                    "autocomplete": "off",
                }
            ),
            "venue": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        venue = self.fields["venue"]
        assert isinstance(venue, ModelChoiceField)
        venue.queryset = Venue.objects.order_by("name")
        self.fields["name"].help_text = _(
            "A short label for this trading context."
        )
        venue.help_text = _(
            "The exchange or broker this profile is bound to."
        )
