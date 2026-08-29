"""Presentation filters for exact journal values."""

from django import template

from tradefog.journal.presentation import compact_decimal as format_decimal

register = template.Library()


@register.filter
def compact_decimal(value: object) -> str:
    """Render a decimal without insignificant trailing fractional zeros."""
    return format_decimal(value)
