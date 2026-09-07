"""Integration checks for optional compiled frontend serving."""

from pathlib import Path

from httpx import ASGITransport, AsyncClient

from tradefog.config.frontend import FrontendSettings
from tradefog.config.root import Settings
from tradefog.main import create_app


async def test_compiled_frontend_serves_navigation_without_hiding_api(
    tmp_path: Path,
) -> None:
    """Serve SPA routes and assets while preserving API and missing-file 404s."""
    index = tmp_path / "index.html"
    assets = tmp_path / "assets"
    assets.mkdir()
    index.write_text("<main>Tradefog</main>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ready')", encoding="utf-8")

    app = create_app(Settings(frontend=FrontendSettings(path=tmp_path)))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        root = await client.get("/")
        dashboard = await client.get("/dashboard")
        asset = await client.get("/assets/app.js")
        missing_asset = await client.get("/assets/missing.js")
        health = await client.get("/api/v1/health")

    assert root.text == dashboard.text == "<main>Tradefog</main>"
    assert asset.text == "console.log('ready')"
    assert missing_asset.status_code == 404
    assert health.status_code == 200


async def test_invalid_frontend_path_leaves_headless_api_available(
    tmp_path: Path,
) -> None:
    """A missing compiled frontend must not prevent API-only operation."""
    app = create_app(
        Settings(frontend=FrontendSettings(path=tmp_path / "missing")),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        root = await client.get("/")
        health = await client.get("/api/v1/health")

    assert root.status_code == 404
    assert health.status_code == 200
