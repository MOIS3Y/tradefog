"""Provider-neutral public market contracts, independent of persistence."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

type MarketProduct = Literal["spot", "perpetual_future"]
type Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]


class MarketFailure(Exception):
    """Safe failure with an HTTP mapping and optional retry delay."""

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 502,
        retry_after: int = 0,
    ) -> None:
        """Retain only provider-independent information safe for clients."""
        super().__init__(message)
        self.code = code
        self.status = status
        self.retry_after = retry_after


class Candle(BaseModel):
    """One candle identified by its UTC opening time in milliseconds."""

    timestamp: int = Field(gt=0)
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    turnover: Decimal | None = Field(default=None, ge=0)


class CandlePage(BaseModel):
    """Ascending candle history with an exclusive backward cursor."""

    bars: list[Candle]
    has_more: bool
    received_at: int


class BookLevel(BaseModel):
    """Resting quantity in base units at an exact price."""

    price: Decimal = Field(gt=0)
    size: Decimal = Field(ge=0)


class OrderBook(BaseModel):
    """Independent book snapshot, not an atomic pair with candles."""

    timestamp: int
    received_at: int
    bids: list[BookLevel]
    asks: list[BookLevel]


class InstrumentSpec(BaseModel):
    """Supported executable instrument metadata suitable for import."""

    symbol: str
    product: MarketProduct
    base: str
    quote: str
    settlement: str
    price_step: Decimal = Field(gt=0)
    qty_step: Decimal = Field(gt=0)
    min_qty: Decimal | None = Field(default=None, gt=0)
    min_notional: Decimal | None = Field(default=None, gt=0)
    is_active: bool


class InstrumentPage(BaseModel):
    """Provider page of supported instruments; never imports implicitly."""

    items: list[InstrumentSpec]
    next_cursor: str | None = None


class VenueCapabilities(BaseModel):
    """Declarative functionality; manual does not require a provider."""

    code: str
    name: str
    instruments: bool
    candles: bool
    orderbook: bool
    automatic_atr: bool
    products: list[str]
    timeframes: list[str]
    refresh_ms: int = 1000
