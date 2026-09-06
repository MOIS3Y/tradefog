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


@register.filter
def display_url(url: str | None) -> str:
    """Format a URL for display by stripping scheme and trailing slash."""
    if not url:
        return ""
    cleaned = url.strip()
    for prefix in ("https://", "http://"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.rstrip("/")
