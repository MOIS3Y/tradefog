"""FastAPI application factory and instance."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from tradefog import __version__
from tradefog.api import api_router
from tradefog.config import Settings, get_settings
from tradefog.db.session import Database
from tradefog.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application startup and shutdown lifespan management."""
    settings: Settings = app.state.settings
    setup_logging(settings.logging)
    database = Database(settings.database)
    app.state.database = database
    try:
        yield
    finally:
        await database.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a new FastAPI application instance."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.application.app_name,
        version=__version__,
        debug=app_settings.application.debug,
        lifespan=lifespan,
    )
    app.state.settings = app_settings

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
        if Path(frontend_path).suffix:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
