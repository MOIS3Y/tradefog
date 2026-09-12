"""Profile context must constrain both journal writes and private files."""

from base64 import b64decode

from fastapi import FastAPI
from httpx import AsyncClient

from tests.test_trade_flow import draft, post, setup_market


async def test_nested_trades_and_attachments_reject_wrong_context(
    profile_client: AsyncClient,
) -> None:
    """Sibling profiles and sibling trades cannot address each other's data."""
    client = profile_client
    first = await setup_market(client)
    second = await setup_market(client)
    trade = await draft(client, first)
    sibling = await draft(client, first)
    root = f"/api/v1{first['root']}/trades/{trade['id']}"
    wrong = f"/api/v1{second['root']}/trades/{trade['id']}"
    for method, suffix, body in (
        ("GET", "", None),
        ("PATCH", "", {"description_markdown": "wrong profile"}),
        ("DELETE", "", None),
        ("POST", "/submit", {"status": "open"}),
        ("POST", "/open", None),
        ("POST", "/cancel", None),
        ("POST", "/close", {"actual_exit_price": "100", "realized_pnl": "0"}),
        ("PUT", "/plan", {"planned_entry": "100"}),
        ("GET", "/attachments", None),
    ):
        response = await client.request(method, wrong + suffix, json=body)
        assert response.status_code == 404, response.text

    payload = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lE"
        + "QVR42mP8/x8AAwMCAO+aK1cAAAAASUVORK5CYII="
    )
    files = {"upload": ("chart.png", payload, "image/png")}
    assert (
        await client.post(wrong + "/attachments", files=files)
    ).status_code == 404
    response = await client.post(root + "/attachments", files=files)
    assert response.status_code == 201, response.text
    item = response.json()
    content = item["content_url"]
    assert content.startswith(root + "/attachments/")
    for invalid in (
        content.replace(first["root"], second["root"]),
        content.replace(
            f"/trades/{trade['id']}/", f"/trades/{sibling['id']}/"
        ),
    ):
        assert (await client.get(invalid)).status_code == 404
        assert (
            await client.delete(invalid.removesuffix("/content"))
        ).status_code == 404
    assert (await client.get(content)).status_code == 200
    assert (await client.get(root)).json()["status"] == "draft"
    login = await client.post(
        "/api/v1/auth/token", data={"username": "bob", "password": "secret"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get(root, headers=headers)).status_code == 404
    assert (
        await client.patch(
            root, headers=headers, json={"description_markdown": "not mine"}
        )
    ).status_code == 404


async def test_scoped_and_overview_queries_agree(
    profile_client: AsyncClient,
) -> None:
    """Read-only aggregation reuses profile queries and exact analytics."""
    client = profile_client
    first = await setup_market(client)
    second = await setup_market(client)
    trade = await draft(client, first, "long")
    await draft(client, second)
    root = f"{first['root']}/trades/{trade['id']}"
    await post(client, root + "/submit", {"status": "open"})
    await post(
        client,
        root + "/close",
        {"actual_exit_price": "115", "realized_pnl": "15"},
    )
    for resource in ("trades", "analytics"):
        scoped = await client.get(f"/api/v1{first['root']}/{resource}")
        overview = await client.get(
            f"/api/v1/{resource}",
            params={"profile_id": first["profile"]["id"]},
        )
        assert scoped.status_code == overview.status_code == 200
        assert scoped.json() == overview.json()
    analytics = (await client.get("/api/v1/analytics")).json()
    assert analytics["trajectory"][0]["profile_id"] == trade["profile_id"]
    assert (await client.get("/api/v1/trades")).json()["total"] == 2
    for resource in ("trades", "analytics"):
        assert (
            await client.get(f"/api/v1/profiles/999999/{resource}")
        ).status_code == 404


def test_openapi_has_one_canonical_profile_hierarchy(
    profile_app: FastAPI,
) -> None:
    """The published contract removes ambiguous writes and groups resources."""
    schema = profile_app.openapi()
    paths = schema["paths"]
    assert set(paths["/api/v1/trades"]) == {"get"}
    assert not any(path.startswith("/api/v1/attachments") for path in paths)
    assert not any(path.startswith("/api/v1/trades/") for path in paths)
    properties = schema["components"]["schemas"]["TradeCreate"]["properties"]
    assert "profile_id" not in properties
    for path, operations in paths.items():
        for operation in operations.values():
            assert len(operation["tags"]) == 1
            if path.startswith("/api/v1/profiles"):
                assert operation["tags"][0].startswith("Profiles")
    for resource in ("trades", "analytics"):
        parameters = paths[f"/api/v1/profiles/{{profile_id}}/{resource}"][
            "get"
        ]["parameters"]
        assert not any(
            parameter["name"] == "profile_id" and parameter["in"] == "query"
            for parameter in parameters
        )
