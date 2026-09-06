"""Pure calculations for True Range, Wilder ATR(14), and market context."""

from decimal import Decimal, localcontext

from tradefog.market.types import ATRContext, DailyCandle

ATR_PERIOD = 14


def true_range(
    high: Decimal,
    low: Decimal,
    prev_close: Decimal | None = None,
) -> Decimal:
    """Calculate the True Range of one candle."""
    with localcontext() as context:
        context.prec = 28
        hl = high - low
        if prev_close is None:
            return hl
        hc = abs(high - prev_close)
        lc = abs(low - prev_close)
        return max(hl, hc, lc)


def calculate_atr_14(candles: list[DailyCandle]) -> Decimal:
    """Calculate Wilder's 14-period ATR from chronologically sorted candles.

    Requires at least 14 closed daily candles. Computes the initial 14-day
    simple mean of True Ranges, followed by Wilder smoothing for any
    subsequent candles.
    """
    if len(candles) < ATR_PERIOD:
        raise ValueError(
            f"At least {ATR_PERIOD} closed daily candles are required to "
            + f"calculate ATR({ATR_PERIOD}), got {len(candles)}."
        )

    with localcontext() as context:
        context.prec = 28
        tr_values: list[Decimal] = []
        for index, candle in enumerate(candles):
            prev_close = candles[index - 1].close if index > 0 else None
            tr_values.append(true_range(candle.high, candle.low, prev_close))

        period = Decimal(ATR_PERIOD)
        atr = sum(tr_values[:ATR_PERIOD]) / period

        for tr in tr_values[ATR_PERIOD:]:
            atr = (atr * Decimal(ATR_PERIOD - 1) + tr) / period

        return atr


def calculate_market_context(
    closed_candles: list[DailyCandle],
    session_candle: DailyCandle | None = None,
    *,
    source: str = "auto",
    is_stale: bool = False,
) -> ATRContext:
    """Build an ATRContext from closed candles and an optional session candle.

    The closed candles must be strictly prior to the selected trade date.
    The last 14 closed candles are retained for display.
    """
    if len(closed_candles) < ATR_PERIOD:
        raise ValueError(
            f"At least {ATR_PERIOD} closed candles required, "
            + f"got {len(closed_candles)}."
        )

    atr_value = calculate_atr_14(closed_candles)
    chart_candles = closed_candles[-ATR_PERIOD:]
    contributing_date = chart_candles[-1].date

    observed_session_range: Decimal | None = None
    session_range_percent: Decimal | None = None

    if session_candle is not None:
        with localcontext() as context:
            context.prec = 28
            observed_session_range = session_candle.high - session_candle.low
            if atr_value > 0:
                session_range_percent = (
                    observed_session_range / atr_value * Decimal(100)
                )

    return ATRContext(
        atr_value=atr_value,
        contributing_date=contributing_date,
        candles=chart_candles,
        observed_session_range=observed_session_range,
        session_range_percent=session_range_percent,
        source=source,
        is_stale=is_stale,
    )
