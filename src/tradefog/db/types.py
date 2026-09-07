"""Exact fixed-point persistence without SQLite float conversion."""

from decimal import Decimal, InvalidOperation, localcontext
from typing import final, override

from sqlalchemy import Numeric, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


@final
class ExactDecimal(TypeDecorator[Decimal]):
    """Use NUMERIC on PostgreSQL and canonical decimal text on SQLite.

    SQLite numeric affinity converts values to binary floats. Text keeps
    every digit; arithmetic, ordering and aggregation of SQLite monetary
    columns must happen with Decimal in the application, not SQL.
    Reject excess scale or magnitude instead of silently rounding money.
    """

    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int = 30, scale: int = 18) -> None:
        """Declare the same precision and scale as the source schema."""
        super().__init__(precision=precision, scale=scale)
        self.precision = precision
        self.scale = scale

    @override
    def load_dialect_impl(
        self,
        dialect: Dialect,
    ) -> TypeEngine[str] | TypeEngine[Decimal]:
        """Choose a storage type that cannot lose decimal digits."""
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(self.precision + 2))
        return dialect.type_descriptor(Numeric(self.precision, self.scale))

    @override
    def process_bind_param(
        self,
        value: object,
        dialect: Dialect,
    ) -> Decimal | str | None:
        """Validate finite, representable Decimal inputs before storage."""
        if value is None:
            return None
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError("Financial values must be finite Decimal values")
        with localcontext() as context:
            context.prec = self.precision + 1
            try:
                fixed = value.quantize(Decimal(1).scaleb(-self.scale))
            except InvalidOperation as error:
                raise ValueError("Decimal exceeds column precision") from error
            if fixed != value or abs(fixed) >= Decimal(10) ** (
                self.precision - self.scale
            ):
                raise ValueError("Decimal exceeds column precision or scale")
        if not fixed:
            fixed = fixed.copy_abs()
        return format(fixed, "f") if dialect.name == "sqlite" else fixed

    @override
    def process_result_value(
        self,
        value: Decimal | str | None,
        dialect: Dialect,
    ) -> Decimal | None:
        """Restore exact decimal values on both database backends."""
        return Decimal(value) if value is not None else None
