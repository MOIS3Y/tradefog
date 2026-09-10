"""Bybit public normalization, independent of journal and ORM models."""

import time
from typing import Any

from pydantic import ValidationError

from tradefog.market.contracts import (
    BookLevel,
    Candle,
    CandlePage,
    InstrumentPage,
    InstrumentSpec,
    MarketFailure,
    MarketProduct,
    OrderBook,
    Timeframe,
)
from tradefog.market.transport import MarketTransport

INTERVALS: dict[str, str] = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
    "1d": "D",
    "1w": "W",
    "1M": "M",
}
BASE_URL = "https://api.bybit.com/v5/market/"


def now_ms() -> int:
    """Return UTC receipt time in milliseconds."""
    return time.time_ns() // 1_000_000


def category(product: MarketProduct) -> str:
    """Map supported Tradefog product to the provider category."""
    return "spot" if product == "spot" else "linear"


def invalid_response() -> MarketFailure:
    """Build a sanitized malformed-response error."""
    return MarketFailure("market_invalid_response", "Invalid market response")


class BybitPublic:
    """Fetch supported metadata, candles and books using one transport."""

    def __init__(self, transport: MarketTransport) -> None:
        """Share upstream concurrency and cooldown across all features."""
        self.transport = transport

    async def request(
        self,
        resource: str,
        params: dict[str, str | int],
    ) -> dict[str, Any]:
        """Request a fixed resource; caller input never determines the host."""
        return await self.transport.get("bybit", BASE_URL + resource, params)

    async def candles(
        self,
        symbol: str,
        product: MarketProduct,
        timeframe: Timeframe,
        limit: int = 500,
        before: int | None = None,
    ) -> CandlePage:
        """Normalize descending history into unique ascending candle bars."""
        params: dict[str, str | int] = {
            "symbol": symbol,
            "category": category(product),
            "interval": INTERVALS[timeframe],
            "limit": limit,
        }
        if before is not None:
            params["end"] = before - 1
        result = await self.request("kline", params)
        try:
            rows = result["list"]
            if not isinstance(rows, list):
                raise TypeError("Expected candle array")
            bars: dict[int, Candle] = {}
            for row in rows:
                bar = Candle(
                    timestamp=row[0],
                    open=row[1],
                    high=row[2],
                    low=row[3],
                    close=row[4],
                    volume=row[5],
                    turnover=row[6],
                )
                if (
                    not bar.low
                    <= min(bar.open, bar.close)
                    <= max(
                        bar.open,
                        bar.close,
                    )
                    <= bar.high
                ):
                    raise ValueError("Invalid OHLC")
                if before is None or bar.timestamp < before:
                    bars[bar.timestamp] = bar
            return CandlePage(
                bars=sorted(bars.values(), key=lambda bar: bar.timestamp),
                has_more=len(rows) == limit and bool(bars),
                received_at=now_ms(),
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise invalid_response() from error

    async def book(
        self,
        symbol: str,
        product: MarketProduct,
        limit: int = 50,
    ) -> OrderBook:
        """Keep both sides in best-price-first order without display totals."""
        result = await self.request(
            "orderbook",
            {
                "symbol": symbol,
                "category": category(product),
                "limit": limit,
            },
        )
        try:
            sides: dict[str, list[BookLevel]] = {}
            for side in ("b", "a"):
                if not isinstance(result[side], list):
                    raise TypeError("Expected depth array")
                levels = [
                    BookLevel(price=row[0], size=row[1])
                    for row in result[side]
                ]
                sides[side] = sorted(
                    levels,
                    key=lambda level: level.price,
                    reverse=side == "b",
                )[:limit]
            timestamp = int(result["ts"])
            if timestamp <= 0:
                raise ValueError("Invalid timestamp")
            return OrderBook(
                timestamp=timestamp,
                received_at=now_ms(),
                bids=sides["b"],
                asks=sides["a"],
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise invalid_response() from error

    async def instruments(
        self,
        product: MarketProduct,
        symbol: str | None = None,
        cursor: str | None = None,
    ) -> InstrumentPage:
        """Return a supported metadata page, excluding pre-market products."""
        params: dict[str, str | int] = {"category": category(product)}
        if symbol:
            params["symbol"] = symbol
        if product != "spot":
            params["limit"] = 500
            if cursor:
                params["cursor"] = cursor
        elif cursor:
            raise MarketFailure(
                "invalid_cursor",
                "Spot metadata has no cursor",
                422,
            )
        result = await self.request("instruments-info", params)
        try:
            rows = result["list"]
            if not isinstance(rows, list):
                raise TypeError("Expected instrument array")
            items = []
            for row in rows:
                spec = normalize_instrument(row, product)
                if spec is not None:
                    items.append(spec)
            return InstrumentPage(
                items=items,
                next_cursor=result.get("nextPageCursor") or None,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise invalid_response() from error


def normalize_instrument(
    row: object,
    product: MarketProduct,
) -> InstrumentSpec | None:
    """Map distinct spot/linear filters, rejecting unsupported contracts."""
    if not isinstance(row, dict):
        raise invalid_response()
    if row.get("isPreListing") or row.get("status") not in (
        "Trading",
        "Settling",
        "Closed",
        "Delivering",
    ):
        return None
    if product == "perpetual_future" and (
        row.get("contractType") != "LinearPerpetual"
        or row.get("settleCoin") not in ("USDT", "USDC")
        or row.get("settleCoin") != row.get("quoteCoin")
    ):
        return None
    # Tokenized equities and non-crypto contract units are outside v1.
    if row.get("symbolType") == "xstocks" or row.get("underlyingTicker"):
        return None
    lot = row["lotSizeFilter"]
    spot = product == "spot"
    try:
        return InstrumentSpec(
            symbol=row["symbol"],
            product=product,
            base=row["baseCoin"],
            quote=row["quoteCoin"],
            settlement=row["quoteCoin"] if spot else row["settleCoin"],
            price_step=row["priceFilter"]["tickSize"],
            qty_step=lot["basePrecision"] if spot else lot["qtyStep"],
            min_qty=None if spot else lot["minOrderQty"],
            min_notional=lot["minOrderAmt" if spot else "minNotionalValue"],
            is_active=row["status"] == "Trading",
        )
    except ValidationError as error:
        raise invalid_response() from error
