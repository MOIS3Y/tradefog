"""Django template filters for formatting journal values."""

from django import template

from tradefog.journal.presentation import compact_decimal

register = template.Library()


@register.filter
def compact(value: object) -> str:
    """Render a decimal without insignificant trailing fractional zeros.

    Whole values render without a fractional part and trailing zeros are
    stripped, so ``20.000000000000000000`` shows as ``20`` and ``0.000100``
    shows as ``0.0001`` while ``0.000001`` is kept intact.
    """
    return compact_decimal(value)