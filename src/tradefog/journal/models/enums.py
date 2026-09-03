"""Stored choices for journal and catalog model fields.

Each class is a Django ``TextChoices`` whose values match the normalized
enum values in ``docs/database.dbml``. Labels are wrapped in ``gettext_lazy``
so they are translated in forms, admin, and ``get_FOO_display()``; the active
request language is used at render time.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class AssetType(models.TextChoices):
    """Unambiguous type of a shared asset."""

    CRYPTO = "crypto", _("Crypto")
    EQUITY = "equity", _("Equity")
    FIAT = "fiat", _("Fiat")


class ProductKind(models.TextChoices):
    """Executable market kind placed on a venue instrument.

    The product implies the market class: Spot and Perpetual Future are
    Crypto, Cash Equity is Equity.
    """

    SPOT = "spot", _("Spot")
    PERPETUAL_FUTURE = "perpetual_future", _("Perpetual Future")
    CASH_EQUITY = "cash_equity", _("Cash Equity")


class ATRSource(models.TextChoices):
    """Origin of a frozen ATR snapshot value."""

    AUTO = "auto", _("Auto")
    MANUAL = "manual", _("Manual")


class TradeStatus(models.TextChoices):
    """Lifecycle state of a journal trade."""

    DRAFT = "draft", _("Draft")
    PENDING_ENTRY = "pending_entry", _("Pending entry")
    OPEN = "open", _("Open")
    CLOSED = "closed", _("Closed")
    CANCELLED = "cancelled", _("Cancelled")


class Direction(models.TextChoices):
    """Planned trade side."""

    LONG = "long", _("Long")
    SHORT = "short", _("Short")


class StrategyStatus(models.TextChoices):
    """Operational status recalculated from financial facts."""

    ACTIVE = "active", _("Active")
    AT_RISK = "at_risk", _("At risk")
    RISK_STOPPED = "risk_stopped", _("Risk stopped")
    ARCHIVED = "archived", _("Archived")


class WalletOperationKind(models.TextChoices):
    """Kind of a virtual wallet journal operation."""

    DEPOSIT = "deposit", _("Deposit")
    WITHDRAWAL = "withdrawal", _("Withdrawal")
