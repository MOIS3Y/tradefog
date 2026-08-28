"""Tests for journal presentation filters."""

from decimal import Decimal

from tradefog.journal.templatetags.journal import compact_decimal


def test_compact_decimal_removes_only_insignificant_fractional_zeros() -> None:
    """Precision values should remain exact without fixed-width noise."""
    assert compact_decimal(Decimal("0.100000000000")) == "0.1"
    assert compact_decimal(Decimal("0.000010000000")) == "0.00001"
    assert compact_decimal(Decimal("10000.00000000")) == "10000"
