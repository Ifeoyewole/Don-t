"""Aggregated API router for v1 endpoints."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import health, measurement, validation

api_router = APIRouter()

# Register endpoints under /cv prefix
api_router.include_router(health.router, prefix="/cv", tags=["Health"])
api_router.include_router(validation.router, prefix="/cv", tags=["Validation"])
api_router.include_router(measurement.router, prefix="/cv", tags=["Measurement"])

# Also mount health directly at root for standard load balancer probes
api_router.include_router(health.router, tags=["Health"])
