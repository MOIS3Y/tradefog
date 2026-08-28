"""Presentation filters for exact journal values."""

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def compact_decimal(value: object) -> str:
    """Render a decimal without insignificant trailing fractional zeros."""
    if not isinstance(value, Decimal):
        return str(value)
    return format(value.normalize(), "f")
