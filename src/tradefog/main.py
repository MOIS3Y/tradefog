"""FastAPI application factory and instance."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from tradefog import __version__
from tradefog.api import api_router
from tradefog.api.documentation import API_DESCRIPTION
from tradefog.config import Settings, get_settings
from tradefog.db.session import Database
from tradefog.logging import setup_logging
from tradefog.market.contracts import MarketFailure
from tradefog.market.providers.bybit_public import BybitPublic
from tradefog.market.public_service import PublicMarketService
from tradefog.market.transport import MarketTransport


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application startup and shutdown lifespan management."""
    settings: Settings = app.state.settings
    setup_logging(settings.logging)
    database = Database(settings.database)
    app.state.database = database
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5, pool=1),
            limits=httpx.Limits(
                max_connections=8, max_keepalive_connections=8
            ),
            follow_redirects=False,
        ) as market_client:
            app.state.market = PublicMarketService(
                {
                    "bybit": BybitPublic(MarketTransport(market_client)),
                }
            )
            yield
    finally:
        await database.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a new FastAPI application instance."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.application.app_name,
        version=__version__,
        description=API_DESCRIPTION,
        debug=app_settings.application.debug,
        lifespan=lifespan,
    )
    app.state.settings = app_settings

    @app.exception_handler(MarketFailure)
    async def market_failure_handler(
        _request: object,
        error: MarketFailure,
    ) -> JSONResponse:
        """Expose a safe market error and propagate the upstream cooldown."""
        return JSONResponse(
            status_code=error.status,
            content={"detail": {"code": error.code, "message": str(error)}},
            headers={"Retry-After": str(error.retry_after)}
            if error.retry_after
            else None,
        )

    # Configure CORS
    if app_settings.application.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.application.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Mount API router
    app.include_router(api_router, prefix="/api")

    configure_frontend(app, app_settings.frontend.path)

    return app


def configure_frontend(app: FastAPI, path: Path | None) -> None:
    """Safely expose a compiled SPA without changing headless API behavior."""
    if path is None:
        return

    root = path.resolve()
    index = root / "index.html"
    if not root.is_dir() or not index.is_file():
        logger.warning(
            "Configured frontend path is unavailable: {}",
            root,
        )
        return

    assets = root / "assets"
    if assets.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets),
            name="frontend-assets",
        )

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def serve_frontend(frontend_path: str) -> FileResponse:
        """Serve SPA navigation while leaving missing static files as 404."""
        if (
            frontend_path == "api"
            or frontend_path.startswith("api/")
            or Path(frontend_path).suffix
        ):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
