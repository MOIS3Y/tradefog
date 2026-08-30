"""Public Bybit V5 daily-candle client."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast

import httpx

from tradefog.journal.market_data.types import CandleValue, ProviderDailyData
from tradefog.journal.models import ProfileTradingPair, TradingProfile

BYBIT_BASE_URL = "https://api.bybit.com"
BYBIT_KLINE_PATH = "/v5/market/kline"
BYBIT_CANDLE_LIMIT = 200
BYBIT_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


class MarketDataProviderError(Exception):
    """Report a recoverable public-provider or response-format failure."""


def _category(trading_pair: ProfileTradingPair) -> str:
    """Map the profile market to the supported Bybit V5 category."""
    if (
        trading_pair.profile.market_type
        == TradingProfile.MarketType.SPOT.value
    ):
        return "spot"
    return "linear"


def _request_params(
    trading_pair: ProfileTradingPair,
    context_date: date,
) -> dict[str, str | int]:
    """Build one bounded daily-kline request around the context date."""
    params: dict[str, str | int] = {
        "category": _category(trading_pair),
        "symbol": (
            f"{trading_pair.base_symbol}{trading_pair.quote_symbol}".upper()
        ),
        "interval": "D",
        "limit": BYBIT_CANDLE_LIMIT,
    }
    utc_today = datetime.now(UTC).date()
    if context_date < utc_today:
        session_end = datetime.combine(
            context_date + timedelta(days=1),
            datetime.min.time(),
            tzinfo=UTC,
        )
        params["end"] = int(session_end.timestamp() * 1000) - 1
    return params


def _response_rows(payload: object) -> tuple[Sequence[object], int]:
    """Validate the small portion of the Bybit response contract we use."""
    if not isinstance(payload, dict):
        raise MarketDataProviderError("Bybit returned an invalid response.")
    response_payload = cast(dict[str, object], payload)
    if response_payload.get("retCode") != 0:
        raise MarketDataProviderError("Bybit rejected the candle request.")
    result = response_payload.get("result")
    server_time = response_payload.get("time")
    if not isinstance(result, dict) or not isinstance(server_time, int):
        raise MarketDataProviderError("Bybit returned an invalid response.")
    response_result = cast(dict[str, object], result)
    rows = response_result.get("list")
    if not isinstance(rows, list):
        raise MarketDataProviderError("Bybit returned an invalid response.")
    return cast(list[object], rows), server_time


def _parse_candle(row: object) -> tuple[CandleValue, int]:
    """Parse one positional V5 kline without losing decimal precision."""
    if not isinstance(row, list):
        raise MarketDataProviderError("Bybit returned an invalid candle.")
    values = cast(list[object], row)
    if len(values) < 5:
        raise MarketDataProviderError("Bybit returned an invalid candle.")
    try:
        start_ms = int(str(values[0]))
        open_price = Decimal(str(values[1]))
        high_price = Decimal(str(values[2]))
        low_price = Decimal(str(values[3]))
        close_price = Decimal(str(values[4]))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise MarketDataProviderError(
            "Bybit returned an invalid candle."
        ) from error
    trading_date = datetime.fromtimestamp(start_ms / 1000, UTC).date()
    if (
        min(open_price, high_price, low_price, close_price) <= 0
        or low_price > high_price
        or not low_price <= open_price <= high_price
        or not low_price <= close_price <= high_price
    ):
        raise MarketDataProviderError("Bybit returned an invalid candle.")
    return (
        CandleValue(
            trading_date=trading_date,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            source=ProfileTradingPair.MarketDataProvider.BYBIT.value,
        ),
        start_ms,
    )


def fetch_daily_data(
    trading_pair: ProfileTradingPair,
    context_date: date,
    *,
    client: httpx.Client | None = None,
) -> ProviderDailyData:
    """Fetch closed candles and retain any still-forming UTC day separately."""
    owned_client = client is None
    http_client = client or httpx.Client(
        base_url=BYBIT_BASE_URL,
        timeout=BYBIT_TIMEOUT,
        headers={"User-Agent": "Tradefog/0.1"},
    )
    try:
        response = http_client.get(
            BYBIT_KLINE_PATH,
            params=_request_params(trading_pair, context_date),
        )
        _ = response.raise_for_status()
        payload = cast(object, response.json())
        rows, server_time = _response_rows(payload)
    except (httpx.HTTPError, ValueError) as error:
        raise MarketDataProviderError(
            "Bybit market data is temporarily unavailable."
        ) from error
    finally:
        if owned_client:
            http_client.close()

    closed: list[CandleValue] = []
    current: CandleValue | None = None
    one_day_ms = 86_400_000
    for row in rows:
        candle, start_ms = _parse_candle(row)
        if start_ms + one_day_ms <= server_time:
            closed.append(candle)
        elif candle.trading_date == context_date:
            current = candle
    closed.sort(key=lambda candle: candle.trading_date)
    return ProviderDailyData(
        closed_candles=tuple(closed),
        current_session=current,
        observed_at=datetime.fromtimestamp(server_time / 1000, UTC),
    )
