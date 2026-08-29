"""Shared formatting helpers for journal values."""

from decimal import Decimal


def compact_decimal(value: object) -> str:
    """Render a decimal without insignificant trailing fractional zeros."""
    if value is None:
        return ""
    if not isinstance(value, Decimal):
        return str(value)
    return format(value.normalize(), "f")
