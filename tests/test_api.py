"""Authentication and profile-local identity isolation regressions."""

from base64 import b64decode
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.test_trade_flow import draft, post, setup_market
from tradefog.market.providers.bybit_public import BybitPublic
from tradefog.market.public_service import PublicMarketService
from tradefog.market.transport import MarketTransport


async def test_contact_fields_do_not_allow_privilege_changes(
    profile_client: AsyncClient,
) -> None:
    """Contact editing cannot change login identity or staff status."""
    response = await profile_client.patch(
        "/api/v1/auth/me",
        json={
            "first_name": " Alice ",
            "last_name": "",
            "email": "alice@example.com",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["first_name"] == "Alice"
    assert response.json()["last_name"] is None
    assert response.json()["username"] == "alice"
    assert (
        await profile_client.patch("/api/v1/auth/me", json={"is_staff": True})
    ).status_code == 422
    assert (
        await profile_client.patch(
            "/api/v1/auth/me", json={"email": "invalid"}
        )
    ).status_code == 422


async def test_profile_child_lists_keep_pagination_and_scope(
    profile_client: AsyncClient,
) -> None:
    """Nested pages count only their profile and paginate wallet assets."""
    market = await setup_market(profile_client)
    await setup_market(profile_client)
    root = "/api/v1" + market["root"]
    for suffix, total in (
        ("/assets", 2),
        (f"/assets/{market['quote']['id']}/operations", 1),
        ("/strategies", 1),
        (f"/strategies/{market['strategy']['id']}/allocations", 1),
    ):
        response = await profile_client.get(root + suffix)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == total
    response = await profile_client.get(root + "/assets?page_size=1&page=2")
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 2


async def test_trade_attachments_remain_private_after_profile_refactor(
    profile_client: AsyncClient,
) -> None:
    """A second owner cannot read or delete a journal image."""
    client = profile_client
    trade = await draft(client, await setup_market(client))
    payload = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lE"
        + "QVR42mP8/x8AAwMCAO+aK1cAAAAASUVORK5CYII="
    )
    response = await client.post(
        f"/api/v1/trades/{trade['id']}/attachments",
        files={"upload": ("chart.png", payload, "image/png")},
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert (await client.get(item["content_url"])).status_code == 200
    login = await client.post(
        "/api/v1/auth/token", data={"username": "bob", "password": "secret"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (
        await client.get(item["content_url"], headers=headers)
    ).status_code == 404
    path = f"/api/v1/attachments/{item['id']}"
    assert (await client.delete(path, headers=headers)).status_code == 404
    assert (await client.delete(path)).status_code == 204
    assert (await client.get(item["content_url"])).status_code == 404


async def test_profiles_isolate_assets_wallets_and_strategies(
    profile_client: AsyncClient,
) -> None:
    """Even the same owner cannot cross-wire profile identifiers."""
    client = profile_client
    first = await setup_market(client)
    second = await setup_market(client)
    response = await client.get(
        "/api/v1" + first["root"] + f"/assets/{second['base']['id']}",
    )
    assert response.status_code == 404
    response = await client.get(
        "/api/v1"
        + first["root"]
        + f"/instruments/{second['instrument']['id']}"
    )
    assert response.status_code == 404
    response = await client.post(
        "/api/v1/trades",
        json={
            "profile_id": first["profile"]["id"],
            "strategy_id": second["strategy"]["id"],
            "instrument_id": first["instrument"]["id"],
            "trade_date": "2026-09-10",
            "direction": "long",
        },
    )
    assert response.status_code == 422
    response = await client.patch(
        "/api/v1" + first["root"] + f"/assets/{second['wallets'][0]['id']}",
        json={"risk_stop_capital": "10"},
    )
    assert response.status_code == 404
    login = await client.post(
        "/api/v1/auth/token", data={"username": "bob", "password": "secret"}
    )
    token = login.json()["access_token"]
    assert (
        await client.get(
            "/api/v1" + first["root"],
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 404
    response = await client.get(
        "/api/v1/profiles", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.json()["total"] == 0


async def test_manual_profile_needs_no_staff_catalog(
    profile_client: AsyncClient,
) -> None:
    """Ordinary users can bootstrap manual markets without staff."""
    market = await setup_market(profile_client)
    response = await profile_client.get(
        "/api/v1" + market["root"] + "/assets?q=BTC"
    )
    assert response.status_code == 200 and response.json()["total"] == 1
    assert (
        await profile_client.get("/api/v1/catalog/assets")
    ).status_code == 404
    profile = await post(
        profile_client,
        "/profiles",
        {"name": "Automatic", "venue_type": "bybit"},
    )
    response = await profile_client.post(
        f"/api/v1/profiles/{profile['id']}/assets",
        json={"symbol": "BTC", "asset_type": "crypto"},
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("high_step", "expected_atr"),
    [(0, "20"), (1, "30.869194600532394787")],
)
async def test_bybit_import_and_atr_share_provider_without_funding(
    profile_client: AsyncClient,
    profile_app: FastAPI,
    high_step: int,
    expected_atr: str,
) -> None:
    """Import metadata once, refresh archives safely and reuse ATR transport."""
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        """Supply controlled public metadata and daily prices."""
        requests.append(request.url.path)
        if request.url.path.endswith("instruments-info"):
            result = {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "baseCoin": "BTC",
                        "quoteCoin": "USDT",
                        "status": "Trading",
                        "priceFilter": {"tickSize": "0.01"},
                        "lotSizeFilter": {
                            "basePrecision": "0.001",
                            "minOrderAmt": "5",
                        },
                    }
                ]
            }
        else:
            start = datetime(2026, 8, 20, tzinfo=UTC)
            result = {
                "list": [
                    [
                        int((start + timedelta(days=i)).timestamp() * 1000),
                        "100",
                        str(110 + i * high_step),
                        "90",
                        "100",
                        "1",
                        "100",
                    ]
                    for i in range(22)
                ]
            }
        return httpx.Response(200, json={"retCode": 0, "result": result})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as source:
        profile_app.state.market = PublicMarketService(
            {"bybit": BybitPublic(MarketTransport(source))}
        )
        profile = await post(
            profile_client,
            "/profiles",
            {"name": "Bybit", "venue_type": "bybit"},
        )
        root = f"/profiles/{profile['id']}"
        instrument = await post(
            profile_client,
            root + "/instruments",
            {"mode": "bybit", "exec_symbol": "BTCUSDT", "product": "spot"},
        )
        wallet = (
            await profile_client.get(
                "/api/v1" + root + "/assets?hide_empty=true"
            )
        ).json()
        assert wallet["items"] == []
        metadata = await profile_client.get("/api/v1" + root + "/assets")
        assert metadata.json()["total"] == 2
        archived = await profile_client.patch(
            "/api/v1" + root + f"/instruments/{instrument['id']}",
            json={"is_archived": True},
        )
        assert archived.status_code == 200
        refreshed = await post(
            profile_client,
            root + f"/instruments/{instrument['id']}/refresh",
            {},
        )
        assert instrument["base_asset_type"] == "crypto"
        assert instrument["quote_asset_type"] == "crypto"
        assert refreshed["base_asset_type"] == "crypto"
        assert refreshed["quote_asset_type"] == "crypto"
        assert refreshed["is_archived"]
        await profile_client.patch(
            "/api/v1" + root + f"/instruments/{instrument['id']}",
            json={"is_archived": False},
        )
        quote = {"id": instrument["settlement_asset_id"]}
        await post(
            profile_client,
            root + f"/assets/{quote['id']}/operations",
            {
                "kind": "deposit",
                "amount": "1000",
            },
        )
        strategy = await post(
            profile_client,
            root + "/strategies",
            {"name": "One", "risk_percent": "1", "reward_multiple": 3},
        )
        await post(
            profile_client,
            root + f"/strategies/{strategy['id']}/allocations",
            {"asset_id": quote["id"], "capital": "1000"},
        )
        trade = await post(
            profile_client,
            "/trades",
            {
                "profile_id": profile["id"],
                "strategy_id": strategy["id"],
                "instrument_id": instrument["id"],
                "trade_date": "2026-09-10",
                "direction": "long",
            },
        )
        atr = await post(profile_client, f"/trades/{trade['id']}/atr", {})
        assert Decimal(atr["value"]) == Decimal(expected_atr)
        loaded = (
            await profile_client.get(f"/api/v1/trades/{trade['id']}")
        ).json()
        assert loaded["preparation"]["atr_source"] == "auto"
        assert loaded["preparation"]["atr_value"] == atr["value"]
        assert loaded["atr"]["value"] == atr["value"]
        assert len(atr["candles"]) == 14
    assert requests.count("/v5/market/kline") == 1
