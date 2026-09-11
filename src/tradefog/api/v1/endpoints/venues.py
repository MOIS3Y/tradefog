"""Authorized provider-neutral public market endpoints."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Query, Request

from tradefog.api.dependencies import get_current_user
from tradefog.api.errors import not_found
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
from tradefog.market.public_service import PublicMarketService, capabilities

router = APIRouter(
    prefix="/venues",
    tags=["Venues"],
    dependencies=[Depends(get_current_user)],
)
Symbol = Annotated[
    str, Query(min_length=1, max_length=64, pattern=r"^[A-Z0-9]+$")
]


def get_market(request: Request) -> PublicMarketService:
    """Resolve the lifespan-owned public service for any business caller."""
    return cast(PublicMarketService, request.app.state.market)


MarketDependency = Annotated[PublicMarketService, Depends(get_market)]


@router.get("", response_model=list[VenueCapabilities])
async def list_venues() -> list[VenueCapabilities]:
    """List built-in integration choices, not user-owned catalog rows."""
    return capabilities()


@router.get("/{venue_type}", response_model=VenueCapabilities)
async def venue_capabilities(venue_type: str) -> VenueCapabilities:
    """Describe optional functionality for one integration."""
    for item in capabilities():
        if item.code == venue_type:
            return item
    not_found("Venue type")


@router.get("/{venue_type}/public/instruments", response_model=InstrumentPage)
async def instruments(
    venue_type: str,
    product: MarketProduct,
    market: MarketDependency,
    symbol: Annotated[
        str | None,
        Query(max_length=64, pattern=r"^[A-Z0-9]+$"),
    ] = None,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    q: Annotated[str, Query(max_length=64)] = "",
) -> InstrumentPage:
    """Browse supported upstream instruments without database writes."""
    page = await market.provider(venue_type).instruments(
        product, symbol, cursor
    )
    query = q.strip().upper()
    while True:
        matches = [
            item
            for item in page.items
            if query in item.symbol or query in item.base
        ]
        if matches or not page.next_cursor or not query:
            return InstrumentPage(items=matches, next_cursor=page.next_cursor)
        cursor = page.next_cursor
        page = await market.provider(venue_type).instruments(
            product, symbol, cursor
        )
        if page.next_cursor == cursor:
            raise MarketFailure(
                "invalid_cursor", "Provider cursor did not advance"
            )


@router.get(
    "/{venue_type}/public/instruments/{symbol}",
    response_model=InstrumentSpec,
)
async def instrument(
    venue_type: str,
    symbol: Annotated[
        str, Path(min_length=1, max_length=64, pattern=r"^[A-Z0-9]+$")
    ],
    product: MarketProduct,
    market: MarketDependency,
) -> InstrumentSpec:
    """Resolve exact metadata for one selected executable instrument."""
    return await market.instrument(venue_type, symbol, product)


@router.get("/{venue_type}/public/klines", response_model=CandlePage)
async def klines(
    venue_type: str,
    symbol: Symbol,
    product: MarketProduct,
    timeframe: Timeframe,
    market: MarketDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> CandlePage:
    """Fetch chronological OHLCV; before is an exclusive UTC-ms boundary."""
    return await market.provider(venue_type).candles(
        symbol,
        product,
        timeframe,
        limit,
        before,
    )


@router.get("/{venue_type}/public/orderbook", response_model=OrderBook)
async def orderbook(
    venue_type: str,
    symbol: Symbol,
    product: MarketProduct,
    market: MarketDependency,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> OrderBook:
    """Fetch a current depth snapshot independently of trade state."""
    return await market.provider(venue_type).book(symbol, product, limit)
