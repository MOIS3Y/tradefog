"""FastAPI application factory and instance."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tradefog import __version__
from tradefog.api import api_router
from tradefog.config import Settings, get_settings
from tradefog.logging import setup_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Application startup and shutdown lifespan management."""
    settings = get_settings()
    setup_logging(settings.logging)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a new FastAPI application instance."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.application.app_name,
        version=__version__,
        debug=app_settings.application.debug,
        lifespan=lifespan,
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

    return app


app = create_app()
