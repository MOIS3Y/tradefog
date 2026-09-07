"""Root API router registration."""

from fastapi import APIRouter

from tradefog.api.v1.endpoints import auth, catalog, health, profiles, trades

api_router = APIRouter()

# Include version 1 endpoints
api_router.include_router(health.router, prefix="/v1")
api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(catalog.router, prefix="/v1")
api_router.include_router(profiles.router, prefix="/v1")
api_router.include_router(trades.router, prefix="/v1")
