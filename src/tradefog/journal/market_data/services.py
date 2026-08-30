"""Persistence and fallback behavior for date-aware market context."""

import logging
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

import httpx
from django.db import transaction
from django.utils import timezone

from tradefog.journal.market_data.calculations import calculate_wilder_atr
from tradefog.journal.market_data.providers.bybit import (
    MarketDataProviderError,
    fetch_daily_data,
)
from tradefog.journal.market_data.types import CandleValue, MarketContext
from tradefog.journal.models import (
    DailyCandle,
    MarketDataState,
    ProfileTradingPair,
)

logger = logging.getLogger(__name__)
PERCENT_QUANTUM = Decimal("0.0001")


def _candle_value(candle: DailyCandle) -> CandleValue:
    """Project one persisted candle into the calculation boundary."""
    return CandleValue(
        trading_date=candle.trading_date,
        open_price=candle.open_price,
        high_price=candle.high_price,
        low_price=candle.low_price,
        close_price=candle.close_price,
        source=candle.source,
    )


def _atr_source(candles: list[CandleValue]) -> str:
    """Describe whether the contributing history has one or mixed sources."""
    sources = {candle.source for candle in candles}
    if not sources:
        return ""
    if len(sources) == 1:
        return sources.pop()
    return "MIXED"


def get_market_context(
    trading_pair: ProfileTradingPair,
    context_date: date,
) -> MarketContext:
    """Calculate ATR from candles closed before the selected trade date."""
    stored_candles = list(
        trading_pair.daily_candles.filter(
            trading_date__lt=context_date
        ).order_by("trading_date", "id")
    )
    candles = [_candle_value(candle) for candle in stored_candles]
    atr_value = calculate_wilder_atr(candles)
    atr_as_of_date = candles[-1].trading_date if atr_value else None
    try:
        state = trading_pair.market_data_state
    except MarketDataState.DoesNotExist:
        state = None

    uses_live_provider = (
        trading_pair.market_data_provider
        == ProfileTradingPair.MarketDataProvider.BYBIT.value
    )
    session_range: Decimal | None = None
    session_observed_at = None
    if (
        uses_live_provider
        and state is not None
        and state.current_session_date == context_date
        and state.current_high is not None
        and state.current_low is not None
    ):
        session_range = state.current_high - state.current_low
        session_observed_at = state.current_observed_at

    session_percent: Decimal | None = None
    seventy_five_percent_atr: Decimal | None = None
    if atr_value is not None:
        with localcontext() as decimal_context:
            decimal_context.prec = 96
            seventy_five_percent_atr = atr_value * Decimal("0.75")
            if session_range is not None and atr_value > 0:
                session_percent = (
                    session_range / atr_value * Decimal(100)
                ).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_EVEN)

    return MarketContext(
        context_date=context_date,
        chart_candles=tuple(candles[-14:]),
        atr_value=atr_value,
        atr_as_of_date=atr_as_of_date,
        atr_source=_atr_source(candles) if atr_value else "",
        seventy_five_percent_atr=seventy_five_percent_atr,
        session_range=session_range,
        session_range_percent=session_percent,
        session_observed_at=session_observed_at,
        refreshed_at=state.last_success_at if state else None,
        is_stale=state.is_stale if state and uses_live_provider else False,
        provider_error=(
            state.last_error if state and uses_live_provider else ""
        ),
    )


@transaction.atomic
def _store_bybit_data(
    trading_pair: ProfileTradingPair,
    data_observed_at: datetime,
    closed_candles: tuple[CandleValue, ...],
    current_session: CandleValue | None,
) -> None:
    """Upsert provider candles without overwriting manual corrections."""
    observed_at = data_observed_at
    for candle in closed_candles:
        existing = DailyCandle.objects.filter(
            trading_pair=trading_pair,
            trading_date=candle.trading_date,
        ).first()
        if (
            existing is not None
            and existing.source
            == ProfileTradingPair.MarketDataProvider.MANUAL.value
        ):
            continue
        if existing is None:
            existing = DailyCandle(
                trading_pair=trading_pair,
                trading_date=candle.trading_date,
            )
        existing.open_price = candle.open_price
        existing.high_price = candle.high_price
        existing.low_price = candle.low_price
        existing.close_price = candle.close_price
        existing.source = ProfileTradingPair.MarketDataProvider.BYBIT.value
        existing.fetched_at = observed_at
        existing.full_clean()
        existing.save()

    state, _created = (
        MarketDataState.objects.select_for_update().get_or_create(
            trading_pair=trading_pair
        )
    )
    state.last_attempt_at = observed_at
    state.last_success_at = observed_at
    state.last_error = ""
    if current_session is not None:
        state.current_session_date = current_session.trading_date
        state.current_high = current_session.high_price
        state.current_low = current_session.low_price
        state.current_observed_at = observed_at
    elif state.current_session_date in {
        candle.trading_date for candle in closed_candles
    }:
        state.current_session_date = None
        state.current_high = None
        state.current_low = None
        state.current_observed_at = None
    state.full_clean()
    state.save()


def _record_provider_failure(
    trading_pair: ProfileTradingPair,
    error: MarketDataProviderError,
) -> None:
    """Preserve cached values while marking the latest refresh as stale."""
    attempted_at = timezone.now()
    state, _created = MarketDataState.objects.get_or_create(
        trading_pair=trading_pair
    )
    state.last_attempt_at = attempted_at
    state.last_error = str(error)[:300]
    state.save(update_fields=["last_attempt_at", "last_error"])
    logger.warning(
        "Market-data refresh failed for trading pair %s: %s",
        trading_pair.id,
        error,
    )


def refresh_market_context(
    trading_pair: ProfileTradingPair,
    context_date: date,
    *,
    client: httpx.Client | None = None,
) -> MarketContext:
    """Refresh a configured public source and fall back to stored candles."""
    if (
        trading_pair.market_data_provider
        != ProfileTradingPair.MarketDataProvider.BYBIT.value
    ):
        return get_market_context(trading_pair, context_date)
    try:
        data = fetch_daily_data(
            trading_pair,
            context_date,
            client=client,
        )
    except MarketDataProviderError as error:
        _record_provider_failure(trading_pair, error)
    else:
        _store_bybit_data(
            trading_pair,
            data.observed_at,
            data.closed_candles,
            data.current_session,
        )
    return get_market_context(trading_pair, context_date)
