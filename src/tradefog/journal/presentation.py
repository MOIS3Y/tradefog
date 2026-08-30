"""Shared formatting helpers for journal values."""

from decimal import ROUND_HALF_UP, Decimal, localcontext


def compact_decimal(value: object) -> str:
    """Render a decimal without insignificant trailing fractional zeros."""
    if value is None:
        return ""
    if not isinstance(value, Decimal):
        return str(value)
    return format(value.normalize(), "f")


def rounded_decimal(value: object, places: int = 2) -> str:
    """Round a decimal for display without changing its stored precision."""
    if value is None:
        return ""
    if not isinstance(value, Decimal):
        return str(value)
    if places < 0:
        raise ValueError("Decimal places cannot be negative.")
    quantum = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = 96
        rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return compact_decimal(rounded)


def rounded_to_step(value: object, step: object) -> str:
    """Round a calculated price to the configured price-step precision."""
    if value is None:
        return ""
    if not isinstance(value, Decimal) or not isinstance(step, Decimal):
        return str(value)
    normalized_step = step.normalize()
    exponent = normalized_step.as_tuple().exponent
    if not isinstance(exponent, int):
        return compact_decimal(value)
    places = max(0, -exponent)
    return rounded_decimal(value, places)
