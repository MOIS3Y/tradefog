"""Forms for owner-scoped profile wallet management."""

from decimal import Decimal
from typing import Any, ClassVar, cast, final, override

from django import forms
from django.db.models import Sum
from django.forms import ModelChoiceField
from django.utils.translation import gettext_lazy as _

from tradefog.journal.calculations import (
    available_balance,
    wallet_balance,
)
from tradefog.journal.models import (
    VenueWalletAsset,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.journal.models.enums import WalletOperationKind
from tradefog.journal.services import reserved_notional
from tradefog.journal.widgets import CompactNumberInput


@final
class WalletAssetAddForm(forms.ModelForm):
    """Add one venue-capable asset to the profile wallet.

    The wallet is supplied by the caller so the choices can be limited to the
    assets the profile venue exposes that are not already in the wallet. New
    assets a staff member adds to the venue automatically appear here.
    """

    wallet: Wallet

    class Meta:
        model: type[WalletAsset] = WalletAsset
        fields: tuple[str, ...] = ("venue_wallet_asset",)
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "venue_wallet_asset": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args: Any, wallet: Wallet, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.wallet = wallet
        linked = wallet.assets.values_list("venue_wallet_asset_id", flat=True)
        venue_asset = self.fields["venue_wallet_asset"]
        assert isinstance(venue_asset, ModelChoiceField)
        venue_asset.queryset = (
            VenueWalletAsset.objects.filter(
                venue=wallet.profile.venue,
                is_active=True,
            )
            .exclude(pk__in=linked)
            .select_related("asset")
            .order_by("asset__symbol")
        )
        venue_asset.empty_label = _("Choose an asset")
        venue_asset.label_from_instance = lambda obj: (
            cast(VenueWalletAsset, obj).asset.symbol
        )
        venue_asset.error_messages["invalid_choice"] = _(
            "This asset is already in the wallet."
        )
        venue_asset.help_text = _(
            "An asset that the profile venue can hold in a wallet."
        )

    @override
    def save(self, commit: bool = True) -> WalletAsset:
        """Persist the wallet asset, binding the wallet supplied by caller."""
        instance = super().save(commit=False)
        instance.wallet = self.wallet
        if commit:
            instance.save()
        return instance


@final
class WalletOperationForm(forms.ModelForm):
    """Record a deposit or withdrawal against one wallet asset.

    The wallet asset and the operation kind are supplied by the caller. A
    withdrawal cannot exceed the asset's positive available balance.
    """

    wallet_asset: WalletAsset

    class Meta:
        model: type[WalletOperation] = WalletOperation
        fields: tuple[str, ...] = ("amount", "note")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "amount": CompactNumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                    "inputmode": "decimal",
                }
            ),
            "note": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(
        self,
        *args: Any,
        wallet_asset: WalletAsset,
        kind: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.wallet_asset = wallet_asset
        self.kind = kind
        self.fields["amount"].label = _("Amount")
        self.fields["amount"].help_text = _("A positive amount to record.")
        self.fields["note"].help_text = _("Optional note for this operation.")

    def clean_amount(self) -> Decimal:
        """Reject a zero or negative amount."""
        amount = self.cleaned_data["amount"]
        if amount <= Decimal(0):
            raise forms.ValidationError(_("The amount must be positive."))
        return amount

    @override
    def clean(self) -> dict[str, Any]:
        """Reject a withdrawal that exceeds the available balance or deposit on delisted asset."""
        cleaned = super().clean()
        amount = cleaned.get("amount")
        if (
            amount
            and self.kind == WalletOperationKind.DEPOSIT.value
            and not self.wallet_asset.venue_wallet_asset.is_active
        ):
            self.add_error(
                "amount",
                _("Deposits are not allowed for delisted venue assets."),
            )
        if amount and self.kind == WalletOperationKind.WITHDRAWAL.value:
            total_deposits = self.wallet_asset.operations.filter(
                kind=WalletOperationKind.DEPOSIT
            ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
            total_withdrawals = self.wallet_asset.operations.filter(
                kind=WalletOperationKind.WITHDRAWAL
            ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
            balance = wallet_balance(total_deposits, total_withdrawals)
            reserved = reserved_notional(
                self.wallet_asset.wallet.profile,
                self.wallet_asset.venue_wallet_asset.asset_id,
            )
            available = available_balance(balance, reserved)
            if amount > available:
                message = _(
                    "The withdrawal cannot exceed the available balance "
                    + "of %(balance)s."
                ) % {"balance": available}
                self.add_error("amount", message)
        return cleaned

    @override
    def save(self, commit: bool = True) -> WalletOperation:
        """Persist the operation, binding asset and kind from the caller."""
        instance = super().save(commit=False)
        instance.wallet_asset = self.wallet_asset
        instance.kind = self.kind
        if commit:
            instance.save()
        return instance


@final
class WalletAssetEditForm(forms.ModelForm):
    """Edit the advisory deposit floor of one wallet asset."""

    class Meta:
        model: type[WalletAsset] = WalletAsset
        fields: tuple[str, ...] = ("risk_stop_capital",)
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "risk_stop_capital": CompactNumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                    "inputmode": "decimal",
                }
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        help_text = _(
            "Advisory deposit floor that highlights a bleeding deposit. "
            + "Leave empty for none."
        )
        self.fields["risk_stop_capital"].help_text = help_text
        self.fields["risk_stop_capital"].required = False


@final
class WalletOperationNoteForm(forms.ModelForm):
    """Edit the note of one recorded wallet operation."""

    class Meta:
        model: type[WalletOperation] = WalletOperation
        fields: tuple[str, ...] = ("note",)
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "note": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["note"].label = _("Note")
        self.fields["note"].help_text = _(
            "Optional note to describe this operation."
        )
        self.fields["note"].required = False
