"""Root API router registration."""

from fastapi import APIRouter

from tradefog.api.v1.endpoints import health

api_router = APIRouter()

# Include version 1 endpoints
api_router.include_router(health.router, prefix="/v1")
