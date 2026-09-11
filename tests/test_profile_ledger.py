"""Profile-wide ledger filters and selected-market restrictions."""

from httpx import AsyncClient

from tests.test_trade_flow import post, setup_market


async def test_profile_operations(profile_client: AsyncClient) -> None:
    """Filter before paging and keep denominations outside the asset page."""
    client = profile_client
    market = await setup_market(client)
    root = market["root"]
    quote = market["quote"]["id"]
    await post(
        client,
        root + f"/assets/{quote}/operations",
        {
            "kind": "deposit",
            "amount": "3",
            "note": "Extra",
        },
    )
    url = "/api/v1" + root + "/operations"
    response = await client.get(url, params={"page_size": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["items"][0]["asset_symbol"] == "USDT"
    assert data["items"][0]["note"] == "Extra"
    response = await client.get(url, params={"asset_id": quote})
    assert response.json()["total"] == 2
    response = await client.get(url, params={"kind": "withdrawal"})
    assert response.json()["total"] == 0
    first = (await client.get(url, params={"order": "asc"})).json()
    assert first["items"][0]["note"] is None
    day = data["items"][0]["created_at"][:10]
    response = await client.get(url, params={"date_from": day, "date_to": day})
    assert response.json()["total"] == 3
    response = await client.get(url, params={"date_to": "2000-01-01"})
    assert response.json()["total"] == 0
    for params in (
        {"date_from": "2026-12-01", "date_to": "2026-01-01"},
        {"sort": "amount"},
        {"kind": "unknown"},
    ):
        assert (await client.get(url, params=params)).status_code == 422
    token = await client.post(
        "/api/v1/auth/token",
        data={
            "username": "bob",
            "password": "secret",
        },
    )
    response = await client.get(
        url,
        headers={
            "Authorization": f"Bearer {token.json()['access_token']}",
        },
    )
    assert response.status_code == 404


async def test_market_filter_and_bybit_asset_input(
    profile_client: AsyncClient,
) -> None:
    """Manual remains free-form; Bybit identities must come from imports."""
    client = profile_client
    market = await setup_market(client)
    root = "/api/v1" + market["root"] + "/instruments"
    response = await client.get(root, params={"product": "spot"})
    assert response.json()["total"] == 1
    response = await client.get(root, params={"product": "perpetual_future"})
    assert response.json()["total"] == 0
    assert (
        await client.get(root, params={"product": "invalid"})
    ).status_code == 422
    profile = await post(
        client, "/profiles", {"name": "Bybit", "venue_type": "bybit"}
    )
    response = await client.post(
        f"/api/v1/profiles/{profile['id']}/assets",
        json={
            "symbol": "TYPO",
            "asset_type": "crypto",
        },
    )
    assert response.status_code == 409


async def test_asset_types_and_filter(profile_client: AsyncClient) -> None:
    """Derive ordered types and filter assets before counting and paging."""
    client = profile_client
    profile = await post(
        client, "/profiles", {"name": "Types", "venue_type": "manual"}
    )
    root = f"/profiles/{profile['id']}"
    body = {
        "mode": "manual",
        "product": "spot",
        "base": {"symbol": "BTC", "asset_type": "crypto"},
        "quote": {"symbol": "USD", "asset_type": "fiat"},
        "price_step": "0.01",
        "qty_step": "0.001",
    }
    first = await post(client, root + "/instruments", body)
    body["base"] = {"symbol": "AAPL", "asset_type": "equity"}
    second = await post(client, root + "/instruments", body)
    assert first["base_asset_type"] == "crypto"
    assert first["quote_asset_type"] == "fiat"
    assert second["base_asset_type"] == "equity"
    assert second["quote_asset_id"] == first["quote_asset_id"]
    url = "/api/v1" + root
    for item in (first, second):
        path = url + f"/instruments/{item['id']}"
        detail = (await client.get(path)).json()
        assert detail["base_asset_type"] == item["base_asset_type"]
        assert detail["quote_asset_type"] == item["quote_asset_type"]
        updated = await client.patch(path, json={"price_step": "0.1"})
        assert updated.json()["base_asset_type"] == item["base_asset_type"]
    page = (await client.get(url + "/instruments")).json()
    assert [i["base_asset_type"] for i in page["items"]] == [
        "equity",
        "crypto",
    ]
    assets = url + "/assets"
    params = {"asset_type": "fiat", "page_size": 1}
    page = (await client.get(assets, params=params)).json()
    assert page["total"] == 1
    assert page["items"][0]["symbol"] == "USD"
    assert (
        await client.get(assets, params={**params, "hide_empty": True})
    ).json()["total"] == 0
    await post(
        client,
        root + f"/assets/{first['quote_asset_id']}/operations",
        {"kind": "deposit", "amount": "10"},
    )
    assert (
        await client.get(
            assets, params={**params, "hide_empty": True, "q": "US"}
        )
    ).json()["total"] == 1
    assert (await client.get(assets, params={**params, "q": "BTC"})).json()[
        "total"
    ] == 0
    assert (
        await client.get(assets, params={"asset_type": "unknown"})
    ).status_code == 422


async def test_operation_kind_sort(profile_client: AsyncClient) -> None:
    """Group operation kinds before pagination in both directions."""
    client = profile_client
    market = await setup_market(client)
    root = market["root"]
    asset = market["base"]["id"]
    await post(
        client,
        root + f"/assets/{asset}/operations",
        {"kind": "withdrawal", "amount": "0.1"},
    )
    url = "/api/v1" + root + "/operations"
    for order, kind in (("asc", "deposit"), ("desc", "withdrawal")):
        result = await client.get(
            url,
            params={
                "asset_id": asset,
                "sort": "kind",
                "order": order,
                "page_size": 1,
            },
        )
        assert result.status_code == 200
        data = result.json()
        assert data["total"] == 2
        assert data["items"][0]["kind"] == kind
