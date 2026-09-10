"""Public market boundary shared by APIs, metadata imports and ATR."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from tradefog.market.calculations import calculate_market_context
from tradefog.market.contracts import (
    CandlePage,
    InstrumentPage,
    InstrumentSpec,
    MarketFailure,
    MarketProduct,
    OrderBook,
    Timeframe,
    VenueCapabilities,
)
from tradefog.market.types import ATRContext, DailyCandle

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]


class PublicProvider(Protocol):
    """Minimal provider interface; future caches can wrap these operations."""

    async def candles(
        self,
        symbol: str,
        product: MarketProduct,
        timeframe: Timeframe,
        limit: int = 500,
        before: int | None = None,
    ) -> CandlePage:
        """Return normalized candle history."""
        ...

    async def book(
        self,
        symbol: str,
        product: MarketProduct,
        limit: int = 50,
    ) -> OrderBook:
        """Return one normalized depth snapshot."""
        ...

    async def instruments(
        self,
        product: MarketProduct,
        symbol: str | None = None,
        cursor: str | None = None,
    ) -> InstrumentPage:
        """Return instrument specifications without importing them."""
        ...


class PublicMarketService:
    """Resolve integration capabilities without coupling manual to Bybit."""

    def __init__(self, providers: dict[str, PublicProvider]) -> None:
        """Accept explicitly installed providers for testability."""
        self.providers = providers

    def provider(self, code: str) -> PublicProvider:
        """Fail closed for unsupported sources instead of falling back."""
        provider = self.providers.get(code)
        if provider is None:
            raise MarketFailure(
                "market_unsupported",
                "Venue has no public market adapter",
                422 if code == "manual" else 404,
            )
        return provider

    async def instrument(
        self,
        code: str,
        symbol: str,
        product: MarketProduct,
    ) -> InstrumentSpec:
        """Find the exact supported symbol in the specified product."""
        page = await self.provider(code).instruments(product, symbol)
        for item in page.items:
            if item.symbol == symbol and item.product == product:
                return item
        raise MarketFailure(
            "instrument_unavailable",
            "Supported instrument not found",
            404,
        )

    async def atr(
        self,
        code: str,
        symbol: str,
        product: MarketProduct,
        trade_date: date,
    ) -> ATRContext:
        """Calculate the existing ATR rule from closed daily market bars."""
        end = datetime.combine(trade_date + timedelta(days=1), time(), UTC)
        page = await self.provider(code).candles(
            symbol,
            product,
            "1d",
            40,
            int(end.timestamp() * 1000),
        )
        candles = [
            DailyCandle(
                date=datetime.fromtimestamp(bar.timestamp / 1000, UTC).date(),
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
            )
            for bar in page.bars
        ]
        closed = [bar for bar in candles if bar.date < trade_date]
        if len(closed) < 14:
            raise MarketFailure(
                "atr_insufficient_history",
                "ATR requires 14 closed days",
                422,
            )
        session = next(
            (bar for bar in candles if bar.date == trade_date), None
        )
        return calculate_market_context(closed, session)


def capabilities() -> list[VenueCapabilities]:
    """Describe v1 integrations without initializing any network client."""
    return [
        VenueCapabilities(
            code="bybit",
            name="Bybit",
            instruments=True,
            candles=True,
            orderbook=True,
            automatic_atr=True,
            products=["spot", "perpetual_future"],
            timeframes=TIMEFRAMES,
        ),
        VenueCapabilities(
            code="manual",
            name="Manual",
            instruments=False,
            candles=False,
            orderbook=False,
            automatic_atr=False,
            products=["spot", "perpetual_future", "cash_equity"],
            timeframes=[],
        ),
    ]
