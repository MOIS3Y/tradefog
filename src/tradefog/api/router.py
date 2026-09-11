"""Root API router registration."""

from fastapi import APIRouter

from tradefog.api.v1.endpoints import (
    analytics,
    attachments,
    auth,
    health,
    instruments,
    operations,
    profiles,
    trades,
    venues,
)

api_router = APIRouter()

# Include version 1 endpoints
api_router.include_router(health.router, prefix="/v1")
api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(instruments.router, prefix="/v1")
api_router.include_router(profiles.router, prefix="/v1")
api_router.include_router(operations.router, prefix="/v1")
api_router.include_router(trades.router, prefix="/v1")
api_router.include_router(analytics.router, prefix="/v1")
api_router.include_router(attachments.router, prefix="/v1")
api_router.include_router(venues.router, prefix="/v1")
