"""Tests for journal presentation filters."""

from decimal import Decimal

from tradefog.journal.templatetags.journal import (
    compact_decimal,
    rounded_decimal,
)


def test_compact_decimal_removes_only_insignificant_fractional_zeros() -> None:
    """Precision values should remain exact without fixed-width noise."""
    assert compact_decimal(Decimal("0.100000000000")) == "0.1"
    assert compact_decimal(Decimal("0.000010000000")) == "0.00001"
    assert compact_decimal(Decimal("10000.00000000")) == "10000"


def test_rounded_decimal_limits_display_precision_and_removes_padding() -> (
    None
):
    """Ratios should remain readable without changing their source value."""
    value = Decimal("2.9126213592233")

    assert rounded_decimal(value, 2) == "2.91"
    assert rounded_decimal(Decimal("3.000000"), 2) == "3"
    assert value == Decimal("2.9126213592233")
