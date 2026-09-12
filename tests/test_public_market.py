"""Deterministic public market normalization and shared cooldown tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from tradefog.config.database import DatabaseSettings, SQLiteSettings
from tradefog.config.root import Settings
from tradefog.main import create_app
from tradefog.market.contracts import (
    InstrumentPage,
    InstrumentSpec,
    MarketFailure,
    MarketProduct,
)
from tradefog.market.providers.bybit_public import (
    BybitPublic,
    normalize_instrument,
)
from tradefog.market.public_service import PublicMarketService
from tradefog.market.transport import MarketTransport, retry_after


async def test_candles_are_exact_sorted_and_exclusive() -> None:
    """Remove duplicates and out-of-bound bars without reducing precision."""

    def respond(request: httpx.Request) -> httpx.Response:
        """Verify provider translation and provide descending records."""
        assert request.url.params["interval"] == "15"
        assert request.url.params["end"] == "2999"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {
                    "list": [
                        ["3000", "2", "3", "1", "2", "10", "20"],
                        [
                            "2000",
                            "2",
                            "3",
                            "1",
                            "2.123456789123456789",
                            "10",
                            "20",
                        ],
                        ["1000", "2", "3", "1", "2", "10", "20"],
                        ["1000", "2", "3", "1", "2", "10", "20"],
                    ]
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as client:
        provider = BybitPublic(MarketTransport(client))
        page = await provider.candles("BTCUSDT", "spot", "15m", 4, 3000)
    assert [bar.timestamp for bar in page.bars] == [1000, 2000]
    assert page.bars[1].close == Decimal("2.123456789123456789")
    assert (
        page.model_dump(mode="json")["bars"][1]["close"]
        == "2.123456789123456789"
    )
    assert page.has_more


async def test_book_keeps_base_quantity_and_sorts_each_side() -> None:
    """Preserve raw depth quantities instead of baking in UI cumulative sums."""

    def respond(_request: httpx.Request) -> httpx.Response:
        """Return intentionally unsorted provider levels."""
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {
                    "ts": 1000,
                    "b": [["90", "0.02"], ["95", "0.01"]],
                    "a": [["110", "0.03"], ["105", "0.04"]],
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as client:
        book = await BybitPublic(MarketTransport(client)).book(
            "BTCUSDT", "spot", 1
        )
    assert book.bids[0].price == 95
    assert book.asks[0].price == 105
    assert book.asks[0].size == Decimal("0.04")


@pytest.mark.parametrize("status,expected", [(403, 600), (429, 60)])
async def test_cooldown_is_shared_across_features(
    status: int, expected: int
) -> None:
    """After an upstream limit, ATR and metadata do not send more requests."""
    requests = 0

    def respond(_request: httpx.Request) -> httpx.Response:
        """Count outbound attempts before rejecting the first one."""
        nonlocal requests
        requests += 1
        return httpx.Response(status)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as client:
        provider = BybitPublic(MarketTransport(client))
        service = PublicMarketService({"bybit": provider})
        with pytest.raises(MarketFailure) as first:
            await provider.book("BTCUSDT", "spot")
        assert first.value.retry_after == expected
        with pytest.raises(MarketFailure):
            await service.atr("bybit", "BTCUSDT", "spot", date(2026, 1, 1))
        with pytest.raises(MarketFailure):
            await service.instrument("bybit", "BTCUSDT", "spot")
    assert requests == 1


async def test_atr_uses_closed_days_before_requested_date() -> None:
    """Historical ATR requests share the candle service and exclusive bounds."""
    trade_date = date(2026, 1, 20)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def respond(request: httpx.Request) -> httpx.Response:
        """Return a stable range with one large current-session candle."""
        assert request.url.params["interval"] == "D"
        assert (
            int(request.url.params["end"])
            == int(
                datetime(2026, 1, 21, tzinfo=UTC).timestamp() * 1000,
            )
            - 1
        )
        rows = [
            [
                int((start + timedelta(days=i)).timestamp() * 1000),
                "100",
                "110" if i < 19 else "200",
                "90",
                "100",
                "1",
                "100",
            ]
            for i in range(20)
        ]
        return httpx.Response(
            200, json={"retCode": 0, "result": {"list": rows}}
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as client:
        service = PublicMarketService(
            {"bybit": BybitPublic(MarketTransport(client))}
        )
        context = await service.atr("bybit", "BTCUSDT", "spot", trade_date)
    assert context.atr_value == 20
    assert context.contributing_date == date(2026, 1, 19)
    assert context.observed_session_range == 110


async def test_manual_needs_no_provider() -> None:
    """Manual capability failure is local even with an empty registry."""
    with pytest.raises(MarketFailure) as error:
        PublicMarketService({}).provider("manual")
    assert error.value.code == "market_unsupported"


async def test_public_routes_still_require_tradefog_auth(
    tmp_path: Path,
) -> None:
    """Public means no exchange key, not an unauthenticated application API."""
    settings = Settings(
        database=DatabaseSettings(
            sqlite=SQLiteSettings(path=tmp_path / "auth.db"),
        )
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        response = await client.get("/api/v1/venues")
    assert response.status_code == 401


def test_retry_after_invalid_and_seconds() -> None:
    """Ignore malformed headers and preserve valid server delays."""
    assert retry_after("120") == 120
    assert retry_after("invalid") == 0
    assert retry_after("nan") == 0
    assert retry_after(None) == 0


@pytest.mark.parametrize("product", ["spot", "perpetual_future"])
def test_instrument_maps_distinct_quantity_filters(product: str) -> None:
    """Normalize market rules while excluding futures and inverse products."""
    from typing import cast

    from tradefog.market.contracts import MarketProduct

    row = {
        "symbol": "BTCUSDT",
        "baseCoin": "BTC",
        "quoteCoin": "USDT",
        "settleCoin": "USDT",
        "contractType": "LinearPerpetual",
        "status": "Trading",
        "priceFilter": {"tickSize": "0.1"},
        "lotSizeFilter": {
            "basePrecision": "0.000001",
            "qtyStep": "0.001",
            "minOrderQty": "0.001",
            "minOrderAmt": "5",
            "minNotionalValue": "5",
        },
    }
    spec = normalize_instrument(row, cast(MarketProduct, product))
    assert spec is not None
    assert spec.qty_step == Decimal(
        "0.000001" if product == "spot" else "0.001"
    )
    assert spec.min_notional == 5
    if product == "perpetual_future":
        row["contractType"] = "LinearFutures"
        assert normalize_instrument(row, "perpetual_future") is None
        row["contractType"] = "LinearPerpetual"
        row["settleCoin"] = "BTC"
        assert normalize_instrument(row, "perpetual_future") is None


async def test_timeout_and_malformed_candle_are_safe_errors() -> None:
    """Do not leak raw transport failures or silently skip invalid OHLC."""

    def timeout(request: httpx.Request) -> httpx.Response:
        """Simulate a provider transport timeout."""
        raise httpx.ReadTimeout("internal details", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(timeout)
    ) as client:
        with pytest.raises(MarketFailure) as error:
            await BybitPublic(MarketTransport(client)).book("BTCUSDT", "spot")
        assert error.value.status == 504
        assert "internal details" not in str(error.value)

    def malformed(_request: httpx.Request) -> httpx.Response:
        """Return inverted OHLC limits."""
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {
                    "list": [
                        [1000, "5", "1", "10", "5", "1", "5"],
                    ]
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(malformed)
    ) as client:
        with pytest.raises(MarketFailure) as error:
            await BybitPublic(MarketTransport(client)).candles(
                "BTCUSDT", "spot", "1m"
            )
        assert error.value.code == "market_invalid_response"


async def test_instrument_search_reaches_later_provider_pages() -> None:
    """A partial symbol search must not stop on the first provider page."""
    from tradefog.api.v1.endpoints.venues import instruments

    class PagedBybit(BybitPublic):
        """Return deterministic metadata pages without network calls."""

        async def instruments(
            self,
            product: MarketProduct,
            symbol: str | None = None,
            cursor: str | None = None,
        ) -> InstrumentPage:
            """Place the match after a nonmatching metadata page."""
            base = "BTC" if cursor else "ETH"
            return InstrumentPage(
                items=[
                    InstrumentSpec(
                        symbol=base + "USDT",
                        product=product,
                        base=base,
                        quote="USDT",
                        settlement="USDT",
                        price_step=Decimal("0.01"),
                        qty_step=Decimal("0.001"),
                        is_active=True,
                    )
                ],
                next_cursor=None if cursor else "second",
            )

    async with httpx.AsyncClient() as source:
        service = PublicMarketService(
            {
                "bybit": PagedBybit(MarketTransport(source)),
            }
        )
        result = await instruments(
            "bybit",
            "perpetual_future",
            service,
            q="btc",
        )
    assert [item.symbol for item in result.items] == ["BTCUSDT"]
    assert result.next_cursor is None
