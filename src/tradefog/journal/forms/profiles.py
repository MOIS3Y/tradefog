"""Forms for owner-scoped trading profiles and their wallet."""

from typing import Any, ClassVar, final

from django import forms
from django.forms import ModelChoiceField
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import TradingProfile, Venue


@final
class TradingProfileForm(forms.ModelForm):
    """Create an owner-scoped trading profile.

    The venue select offers every active shared catalog venue. Venue binding
    is permanent for the profile's lifetime.
    """

    class Meta:
        model: type[TradingProfile] = TradingProfile
        fields: tuple[str, ...] = ("name", "description", "venue")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Bybit Main"),
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": _(
                        "Brief description of this trading context or notes."
                    ),
                    "rows": 3,
                }
            ),
            "venue": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        venue = self.fields["venue"]
        assert isinstance(venue, ModelChoiceField)
        venue.queryset = Venue.objects.filter(is_active=True).order_by("name")
        self.fields["name"].help_text = _(
            "A short label for this trading context."
        )
        self.fields["description"].help_text = _(
            "Optional notes about the profile or supported trading scope."
        )
        venue.help_text = _("The exchange or broker this profile is bound to.")


@final
class TradingProfileSettingsForm(forms.ModelForm):
    """Edit the settings of an owner-scoped trading profile.

    The venue binding is immutable after creation and therefore excluded.
    """

    class Meta:
        model: type[TradingProfile] = TradingProfile
        fields: tuple[str, ...] = ("name", "description")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Bybit Main"),
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": _(
                        "Brief description of this trading context or notes."
                    ),
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["name"].help_text = _(
            "A short label for this trading context."
        )
        self.fields["description"].help_text = _(
            "Optional notes about the profile or supported trading scope."
        )

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]
        if (
            hasattr(self.instance, "owner_id")
            and TradingProfile.objects.filter(
                owner_id=self.instance.owner_id, name=name
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(
                _("A profile with this name already exists.")
            )
        return name
