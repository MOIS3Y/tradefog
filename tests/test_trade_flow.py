"""Profile-owned journal flows including inventory buyback."""

import asyncio
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select

from tradefog.db.models import Trade, TradePreparation, TradeReservation


async def post(
    client: AsyncClient, path: str, body: dict[str, Any]
) -> dict[str, Any]:
    """Create through the API and expose failures clearly."""
    response = await client.post("/api/v1" + path, json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


async def setup_market(
    client: AsyncClient, product: str = "spot", inventory: str = "2"
) -> dict[str, Any]:
    """Set up virtual capital without market requests."""
    profile = await post(
        client, "/profiles", {"name": "Manual", "venue_type": "manual"}
    )
    root = f"/profiles/{profile['id']}"
    base = await post(
        client, root + "/assets", {"symbol": "BTC", "asset_type": "crypto"}
    )
    quote = await post(
        client, root + "/assets", {"symbol": "USDT", "asset_type": "crypto"}
    )
    instrument = await post(
        client,
        root + "/instruments",
        {
            "mode": "manual",
            "product": product,
            "base": {"symbol": "BTC"},
            "quote": {"symbol": "USDT"},
            "price_step": "0.01",
            "qty_step": "0.001",
        },
    )
    wallets = []
    for asset, balance in [(quote, "1000"), (base, inventory)]:
        wallet = asset
        if Decimal(balance) > 0:
            await post(
                client,
                root + f"/assets/{asset['id']}/operations",
                {
                    "kind": "deposit",
                    "amount": balance,
                },
            )
        wallets.append(wallet)
    strategy = await post(
        client,
        root + "/strategies",
        {"name": "Fixed risk", "risk_percent": "1", "reward_multiple": 3},
    )
    allocation = await post(
        client,
        root + f"/strategies/{strategy['id']}/allocations",
        {"asset_id": wallets[0]["id"], "capital": "1000"},
    )
    return {
        "profile": profile,
        "root": root,
        "base": base,
        "quote": quote,
        "instrument": instrument,
        "wallets": wallets,
        "strategy": strategy,
        "allocation": allocation,
    }


async def draft(
    client: AsyncClient, market: dict[str, Any], direction: str = "short"
) -> dict[str, Any]:
    """Create and persist typed price anchors."""
    trade = await post(
        client,
        "/trades",
        {
            "profile_id": market["profile"]["id"],
            "strategy_id": market["strategy"]["id"],
            "instrument_id": market["instrument"]["id"],
            "trade_date": "2026-09-10",
            "direction": direction,
        },
    )
    response = await client.put(
        f"/api/v1/trades/{trade['id']}/plan",
        json={
            "planned_entry": "100",
            "planned_stop": "110" if direction == "short" else "90",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_trade_sorting_by_id_and_date(
    profile_client: AsyncClient,
) -> None:
    """Default to newest IDs and keep backdated trades in date order."""
    client = profile_client
    market = await setup_market(client)
    identifiers = []
    for trade_date in ("2026-09-10", "2026-09-10", "2026-09-09"):
        trade = await post(
            client,
            "/trades",
            {
                "profile_id": market["profile"]["id"],
                "strategy_id": market["strategy"]["id"],
                "instrument_id": market["instrument"]["id"],
                "trade_date": trade_date,
                "direction": "long",
            },
        )
        identifiers.append(trade["id"])
    first, second, backdated = identifiers
    for params, expected in (
        ({}, [backdated, second, first]),
        ({"sort": "id", "order": "desc"}, [backdated, second, first]),
        ({"sort": "id", "order": "asc"}, [first, second, backdated]),
        ({"sort": "trade_date", "order": "desc"}, [second, first, backdated]),
        ({"sort": "trade_date", "order": "asc"}, [backdated, first, second]),
    ):
        response = await client.get("/api/v1/trades", params=params)
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()["items"]] == expected


async def test_draft_without_allocation_can_recover(
    profile_client: AsyncClient,
) -> None:
    """Missing funding setup is identifiable and never destroys a draft."""
    client = profile_client
    market = await setup_market(client)
    allocation_path = (
        f"/api/v1{market['root']}/strategies/"
        f"{market['strategy']['id']}/allocations/{market['allocation']['id']}"
    )
    response = await client.patch(allocation_path, json={"is_archived": True})
    assert response.status_code == 200, response.text
    trade = await post(
        client,
        "/trades",
        {
            "profile_id": market["profile"]["id"],
            "strategy_id": market["strategy"]["id"],
            "instrument_id": market["instrument"]["id"],
            "trade_date": "2026-09-10",
            "direction": "long",
        },
    )
    path = f"/api/v1/trades/{trade['id']}"
    response = await client.get(path + "/planning-context")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "settlement_allocation_required"
    )
    response = await client.post(path + "/submit", json={"status": "open"})
    assert response.status_code == 422
    assert (await client.get(path)).json()["status"] == "draft"
    response = await client.patch(allocation_path, json={"is_archived": False})
    assert response.status_code == 200, response.text
    response = await client.get(path + "/planning-context")
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["target_risk_amount"]) == 10


@pytest.mark.parametrize(
    "product,direction,reserved,inventory",
    [
        ("spot", "long", "100", "0"),
        ("spot", "short", "10", "1"),
        ("cash_equity", "short", "10", "1"),
        ("perpetual_future", "short", "100", "0"),
    ],
)
async def test_full_close_preserves_inventory_and_counts_net_pnl_once(
    profile_client: AsyncClient,
    product: str,
    direction: str,
    reserved: str,
    inventory: str,
) -> None:
    """Freeze denominations, forbid cancellation, release exactly once."""
    client = profile_client
    market = await setup_market(client, product)
    trade = await draft(client, market, direction)
    identifier = trade["id"]
    submitted = await post(
        client, f"/trades/{identifier}/submit", {"status": "open"}
    )
    assert Decimal(submitted["snapshot"]["quantity"]) == 1
    wallet = (await client.get("/api/v1" + market["root"] + "/assets")).json()
    by_asset = {row["id"]: row for row in wallet["items"]}
    assert Decimal(by_asset[market["quote"]["id"]]["reserved"]) == Decimal(
        reserved
    )
    assert Decimal(by_asset[market["base"]["id"]]["reserved"]) == Decimal(
        inventory
    )
    assert (
        await client.post(f"/api/v1/trades/{identifier}/cancel")
    ).status_code == 409
    closed = await post(
        client,
        f"/trades/{identifier}/close",
        {
            "actual_exit_price": "115",
            "realized_pnl": "-15",
            "total_commission": "1",
        },
    )
    assert closed["status"] == "closed"
    assert (
        await client.post(
            f"/api/v1/trades/{identifier}/close",
            json={"actual_exit_price": "115", "realized_pnl": "-15"},
        )
    ).status_code == 409
    wallet = (await client.get("/api/v1" + market["root"] + "/assets")).json()
    by_asset = {row["id"]: row for row in wallet["items"]}
    assert Decimal(by_asset[market["quote"]["id"]]["balance"]) == 985
    assert Decimal(by_asset[market["base"]["id"]]["balance"]) == 2
    assert all(Decimal(row["reserved"]) == 0 for row in wallet["items"])
    assert (await client.get("/api/v1/trades")).status_code == 200
    assert (await client.get("/api/v1/analytics")).status_code == 200


async def test_buyback_requires_inventory_and_clears_stale_atr(
    profile_client: AsyncClient,
) -> None:
    """Missing inventory is visible in preview and blocks submission."""
    client = profile_client
    market = await setup_market(client, inventory="0")
    trade = await draft(client, market)
    identifier = trade["id"]
    preview = await post(
        client,
        f"/trades/{identifier}/plan/preview",
        {"planned_entry": "100", "planned_stop": "110"},
    )
    assert not preview["capital_sufficient"]
    assert len(preview["reservations"]) == 2
    assert (
        await client.post(
            f"/api/v1/trades/{identifier}/submit", json={"status": "open"}
        )
    ).status_code == 409
    await post(
        client,
        f"/trades/{identifier}/atr",
        {"value": "20", "observed_session_range": "10"},
    )
    changed = await client.patch(
        f"/api/v1/trades/{identifier}", json={"trade_date": "2026-09-09"}
    )
    assert changed.status_code == 200
    assert changed.json()["atr"] is None
    assert (
        await client.post(f"/api/v1/trades/{identifier}/atr", json={})
    ).status_code == 422
    assert (await post(client, f"/trades/{identifier}/cancel", {}))[
        "status"
    ] == "cancelled"


async def test_competing_buybacks_cannot_double_reserve(
    profile_client: AsyncClient,
) -> None:
    """Concurrent submissions serialize the shared inventory check."""
    client = profile_client
    market = await setup_market(client, inventory="1")
    first = await draft(client, market)
    second = await draft(client, market)
    responses = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/trades/{item['id']}/submit", json={"status": "open"}
            )
            for item in (first, second)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 409]


async def test_typed_preparation_and_reservations_persist(
    profile_client: AsyncClient, profile_app: FastAPI
) -> None:
    """Preparation contains inputs, not JSON or derived target."""
    market = await setup_market(profile_client)
    trade = await draft(profile_client, market)
    await post(
        profile_client,
        f"/trades/{trade['id']}/submit",
        {"status": "pending_entry"},
    )
    async with profile_app.state.database.session() as session:
        preparation = await session.get(TradePreparation, trade["id"])
        assert preparation is not None and preparation.planned_entry == 100
        assert not hasattr(Trade, "draft_context")
        assert (
            len((await session.scalars(select(TradeReservation))).all()) == 2
        )
    assert (
        await profile_client.put(
            f"/api/v1/trades/{trade['id']}/checklist",
            json={"market_sentiment": "POSITIVE"},
        )
    ).status_code == 409


async def test_partial_plan_and_loss_beyond_virtual_balance(
    profile_client: AsyncClient,
) -> None:
    """Persist incomplete inputs and record a real loss beyond planned risk."""
    market = await setup_market(profile_client)
    trade = await draft(profile_client, market)
    path = f"/api/v1/trades/{trade['id']}"
    response = await profile_client.put(
        path + "/plan", json={"planned_entry": "100"}
    )
    assert response.status_code == 200
    assert response.json()["preparation"]["planned_stop"] is None
    assert (
        await profile_client.post(path + "/submit", json={"status": "open"})
    ).status_code == 422
    await profile_client.put(
        path + "/plan", json={"planned_entry": "100", "planned_stop": "110"}
    )
    assert (
        await profile_client.post(path + "/submit", json={"status": "open"})
    ).status_code == 200
    assert (
        await profile_client.post(
            path + "/close",
            json={"actual_exit_price": "1200", "realized_pnl": "-1100"},
        )
    ).status_code == 200
    wallet = (
        await profile_client.get("/api/v1" + market["root"] + "/assets")
    ).json()
    quote = next(
        row for row in wallet["items"] if row["id"] == market["quote"]["id"]
    )
    assert Decimal(quote["balance"]) == -100


async def test_inventory_withdrawal_cannot_spend_reserved_units(
    profile_client: AsyncClient,
) -> None:
    """Reserve owned units through pending, then release on cancellation."""
    market = await setup_market(profile_client, inventory="1")
    trade = await draft(profile_client, market)
    await post(
        profile_client,
        f"/trades/{trade['id']}/submit",
        {"status": "pending_entry"},
    )
    withdrawal = {
        "kind": "withdrawal",
        "amount": "1",
    }
    assert (
        await profile_client.post(
            "/api/v1"
            + market["root"]
            + f"/assets/{market['base']['id']}/operations",
            json=withdrawal,
        )
    ).status_code == 409
    await post(profile_client, f"/trades/{trade['id']}/cancel", {})
    assert (
        await profile_client.post(
            "/api/v1"
            + market["root"]
            + f"/assets/{market['base']['id']}/operations",
            json=withdrawal,
        )
    ).status_code == 201
