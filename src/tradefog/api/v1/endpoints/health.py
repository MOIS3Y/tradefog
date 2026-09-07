"""Health check and system status endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from tradefog import __version__
from tradefog.config import get_settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str
    app: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return application health status and version."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.application.app_name,
        version=__version__,
    )
