"""Presentation filters for exact journal values."""

from django import template

from tradefog.journal.presentation import compact_decimal as format_decimal
from tradefog.journal.presentation import rounded_decimal as format_rounded
from tradefog.journal.presentation import rounded_to_step as format_to_step

register = template.Library()


@register.filter
def compact_decimal(value: object) -> str:
    """Render a decimal without insignificant trailing fractional zeros."""
    return format_decimal(value)


@register.filter
def rounded_decimal(value: object, places: int = 2) -> str:
    """Round a decimal to a compact user-facing number of places."""
    return format_rounded(value, int(places))


@register.filter
def rounded_to_step(value: object, step: object) -> str:
    """Round a calculated price to an instrument's display precision."""
    return format_to_step(value, step)
