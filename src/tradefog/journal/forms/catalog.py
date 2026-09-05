"""Forms for the shared, staff-managed reference catalog."""

from typing import Any, ClassVar, cast, final, override

from django import forms
from django.forms import ModelChoiceField
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import (
    Asset,
    TradingPair,
    Venue,
    VenueInstrument,
    VenueWalletAsset,
)
from tradefog.journal.models.enums import ProductKind
from tradefog.journal.widgets import CompactNumberInput


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


@final
class VenueForm(forms.ModelForm):
    """Create or edit a shared catalog venue."""

    class Meta:
        model: type[Venue] = Venue
        fields: tuple[str, ...] = ("name", "website")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Bybit"),
                    "autocomplete": "off",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("https://"),
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["name"].help_text = _(
            "Display name, unique across the catalog."
        )
        self.fields["website"].help_text = _(
            "Optional official website for this venue."
        )

    def clean_name(self) -> str:
        """Reject a case-insensitive duplicate venue name."""
        name = self.cleaned_data["name"].strip()
        if (
            Venue.objects.filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(
                _("A venue with this name already exists.")
            )
        return name


@final
class VenueWalletAssetForm(forms.ModelForm):
    """Link a shared asset as wallet-capable on one venue.

    The venue is supplied by the caller so the asset choices can be limited to
    assets that are not already linked, preventing a duplicate link.
    """

    venue: Venue

    class Meta:
        model: type[VenueWalletAsset] = VenueWalletAsset
        fields: tuple[str, ...] = ("asset",)
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "asset": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args: Any, venue: Venue, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.venue = venue
        asset_field = cast(ModelChoiceField, self.fields["asset"])
        linked = VenueWalletAsset.objects.filter(venue=venue).values_list(
            "asset_id", flat=True
        )
        asset_field.queryset = Asset.objects.exclude(pk__in=linked).order_by(
            "symbol"
        )
        asset_field.error_messages["invalid_choice"] = _(
            "This asset is already available on the venue."
        )
        asset_field.help_text = _(
            "The asset becomes available to wallet balances on this venue."
        )

    @override
    def save(self, commit: bool = True) -> VenueWalletAsset:
        """Persist the link, binding the venue supplied by the caller."""
        instance = super().save(commit=False)
        instance.venue = self.venue
        if commit:
            instance.save()
        return instance


@final
class VenueInstrumentForm(forms.ModelForm):
    """Create or edit an executable venue instrument.

    The venue is supplied by the caller so the form can validate that the
    pair and execution symbol are unique on that venue and apply the product
    settlement rules.
    """

    venue: Venue

    class Meta:
        model: type[VenueInstrument] = VenueInstrument
        fields: tuple[str, ...] = (
            "pair",
            "product",
            "exec_symbol",
            "price_step",
            "qty_step",
            "min_qty",
            "min_notional",
            "settlement_asset",
            "active",
        )
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "pair": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "exec_symbol": forms.TextInput(attrs={"class": "form-control"}),
            "price_step": CompactNumberInput(
                attrs={"class": "form-control"}
            ),
            "qty_step": CompactNumberInput(
                attrs={"class": "form-control"}
            ),
            "min_qty": CompactNumberInput(
                attrs={"class": "form-control"}
            ),
            "min_notional": CompactNumberInput(
                attrs={"class": "form-control"}
            ),
            "settlement_asset": forms.Select(attrs={"class": "form-select"}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args: Any, venue: Venue, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.venue = venue
        cast(ModelChoiceField, self.fields["pair"]).queryset = (
            TradingPair.objects.select_related("base", "quote").order_by(
                "base", "quote"
            )
        )
        cast(ModelChoiceField, self.fields["settlement_asset"]).queryset = (
            Asset.objects.order_by("symbol")
        )
        settlement = cast(ModelChoiceField, self.fields["settlement_asset"])
        settlement.empty_label = _("Settles in quote asset")
        pair = cast(ModelChoiceField, self.fields["pair"])
        pair.help_text = _("The logical BASE/QUOTE market traded on the venue.")
        self.fields["product"].help_text = _(
            "Settlement derives from the quote asset for Spot and Cash Equity."
        )
        self.fields["exec_symbol"].help_text = _(
            "The venue's own execution symbol, unique on this venue."
        )
        self.fields["price_step"].help_text = _(
            "Smallest price movement the venue accepts."
        )
        self.fields["qty_step"].help_text = _(
            "Smallest quantity increment the venue accepts."
        )
        self.fields["min_qty"].help_text = _(
            "Optional minimum order quantity."
        )
        self.fields["min_notional"].help_text = _(
            "Optional minimum order notional."
        )
        self.fields["settlement_asset"].help_text = _(
            "Optional explicit settlement for a Perpetual Future."
        )
        self.fields["active"].help_text = _(
            "Delisted instruments stop appearing in trade selection."
        )

    @override
    def clean(self) -> dict[str, Any]:
        """Enforce pair/product and exec-symbol uniqueness on the venue.

        For Spot and Cash Equity the settlement asset is derived from the
        quote, so any entered settlement asset is cleared. The active pair and
        product combination must be unique on the venue.
        """
        cleaned = super().clean()
        pair = cleaned.get("pair")
        product = cleaned.get("product")
        if pair and product:
            duplicate = (
                VenueInstrument.objects.filter(
                    venue=self.venue, pair=pair, product=product
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate:
                self.add_error(
                    "pair",
                    _("This pair and product already exist on the venue."),
                )
        if product in (ProductKind.SPOT, ProductKind.CASH_EQUITY):
            cleaned["settlement_asset"] = None
        return cleaned

    def clean_exec_symbol(self) -> str:
        """Reject an execution symbol already used on this venue."""
        symbol = self.cleaned_data["exec_symbol"].strip()
        if (
            VenueInstrument.objects.filter(
                venue=self.venue, exec_symbol__iexact=symbol
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(
                _("This execution symbol already exists on the venue.")
            )
        return symbol

    @override
    def save(self, commit: bool = True) -> VenueInstrument:
        """Persist the instrument, binding the venue supplied by the caller."""
        instance = super().save(commit=False)
        instance.venue = self.venue
        if commit:
            instance.save()
        return instance