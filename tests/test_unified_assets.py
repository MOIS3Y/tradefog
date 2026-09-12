"""Unified identities, atomic instrument setup and account visibility."""

import asyncio
from decimal import Decimal

from httpx import AsyncClient

from tests.test_trade_flow import draft, post, setup_market


async def test_pair_creates_assets_atomically_and_reuses_symbols(
    profile_client: AsyncClient,
) -> None:
    """Normalize once, preserve names, never create money or partial assets."""
    client = profile_client
    profile = await post(
        client, "/profiles", {"name": "Manual", "venue_type": "manual"}
    )
    root = f"/profiles/{profile['id']}"
    body = {
        "mode": "manual",
        "product": "spot",
        "base": {"symbol": " btc ", "asset_type": "crypto"},
        "quote": {"symbol": "usdt", "asset_type": "crypto"},
        "price_step": "0.01",
        "qty_step": "0.001",
    }
    instrument = await post(client, root + "/instruments", body)
    rows = (await client.get("/api/v1" + root + "/assets")).json()
    assert rows["total"] == 2
    assert all(Decimal(item["balance"]) == 0 for item in rows["items"])
    assert (
        await client.get("/api/v1" + root + "/assets?hide_empty=true")
    ).json()["total"] == 0
    await client.patch(
        "/api/v1" + root + f"/assets/{instrument['base_asset_id']}",
        json={"name": "Bitcoin"},
    )
    body["product"] = "perpetual_future"
    body["base"] = {"symbol": "BTC", "asset_type": "equity"}
    second = await post(client, root + "/instruments", body)
    assert second["base_asset_id"] == instrument["base_asset_id"]
    assert second["base_asset_type"] == "crypto"
    base = (
        await client.get(
            "/api/v1" + root + f"/assets/{second['base_asset_id']}"
        )
    ).json()
    assert base["name"] == "Bitcoin"
    assert (
        await client.post("/api/v1" + root + "/instruments", json=body)
    ).status_code == 409
    body["base"] = {"symbol": "NEW", "asset_type": "crypto"}
    body["quote"] = {"symbol": "MISSING"}
    assert (
        await client.post("/api/v1" + root + "/instruments", json=body)
    ).status_code == 422
    assert (await client.get("/api/v1" + root + "/assets")).json()[
        "total"
    ] == 2


async def test_empty_filter_keeps_ledger_history_and_archive_guards(
    profile_client: AsyncClient,
) -> None:
    """Zero historical balances stay visible; referenced assets cannot archive."""
    client = profile_client
    market = await setup_market(client)
    root = market["root"]
    asset = await post(
        client, root + "/assets", {"symbol": "RUB", "asset_type": "fiat"}
    )
    path = root + f"/assets/{asset['id']}"
    for kind in ("deposit", "withdrawal"):
        await post(client, path + "/operations", {"kind": kind, "amount": "1"})
    page = (
        await client.get(
            "/api/v1" + root + "/assets?hide_empty=true&q=RUB&page_size=1"
        )
    ).json()
    assert page["total"] == 1
    assert Decimal(page["items"][0]["balance"]) == 0
    assert (
        await client.patch("/api/v1" + path, json={"is_archived": True})
    ).status_code == 200
    assert (await client.delete("/api/v1" + path)).status_code == 409
    assert (
        await client.patch(
            "/api/v1" + root + f"/assets/{market['base']['id']}",
            json={"is_archived": True},
        )
    ).status_code == 409


async def test_buyback_inventory_cannot_fund_another_pair(
    profile_client: AsyncClient,
) -> None:
    """BTC reserved for buyback cannot finance an ETC/BTC purchase."""
    client = profile_client
    market = await setup_market(client, inventory="1")
    trade = await draft(client, market)
    await post(
        client,
        f"/profiles/{trade['profile_id']}/trades/{trade['id']}/submit",
        {"status": "open"},
    )
    root = market["root"]
    instrument = await post(
        client,
        root + "/instruments",
        {
            "mode": "manual",
            "product": "spot",
            "base": {"symbol": "ETC", "asset_type": "crypto"},
            "quote": {"symbol": "BTC"},
            "price_step": "0.00001",
            "qty_step": "0.001",
        },
    )
    await post(
        client,
        root + f"/strategies/{market['strategy']['id']}/allocations",
        {
            "asset_id": market["base"]["id"],
            "capital": "1",
        },
    )
    market["instrument"] = instrument
    second = await draft(client, market, "long")
    assert (
        await client.post(
            f"/api/v1/profiles/{second['profile_id']}/trades/{second['id']}/submit",
            json={"status": "open"},
        )
    ).status_code == 409


async def test_concurrent_pair_creation_keeps_one_identity(
    profile_client: AsyncClient,
) -> None:
    """Concurrent saves produce one pair and exactly two asset identities."""
    client = profile_client
    profile = await post(
        client,
        "/profiles",
        {
            "name": "Concurrent",
            "venue_type": "manual",
        },
    )
    root = f"/api/v1/profiles/{profile['id']}"
    body = {
        "mode": "manual",
        "product": "spot",
        "base": {"symbol": "BTC", "asset_type": "crypto"},
        "quote": {"symbol": "USDT", "asset_type": "crypto"},
        "price_step": "0.01",
        "qty_step": "0.001",
    }
    responses = await asyncio.gather(
        client.post(root + "/instruments", json=body),
        client.post(root + "/instruments", json=body),
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert (await client.get(root + "/assets")).json()["total"] == 2
    assert (await client.get(root + "/instruments")).json()["total"] == 1
