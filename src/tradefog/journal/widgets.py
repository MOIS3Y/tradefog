"""Reusable Django form widgets for journal values."""

from typing import final, override

from django import forms

from tradefog.journal.presentation import compact_decimal


@final
class CompactNumberInput(forms.NumberInput):
    """Render a decimal without insignificant trailing fractional zeros.

    A value keeps its full fractional part but trailing zeros are stripped,
    so ``1.000000`` renders as ``1`` and ``0.000100`` renders as ``0.0001``
    while ``0.000001`` is preserved. Only display is affected; the parsed
    value keeps the stored precision.
    """

    @override
    def format_value(self, value: object) -> str | None:
        """Return the value compacted for display in the input."""
        if value == "" or value is None:
            return None
        return compact_decimal(value)
