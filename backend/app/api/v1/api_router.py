"""Aggregated API router for v1 endpoints."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    calibration,
    context_suggestions,
    health,
    measurement,
    multi_frame,
    validation,
)

api_router = APIRouter()

# Register endpoints under /cv prefix
api_router.include_router(health.router, prefix="/cv", tags=["Health"])
api_router.include_router(validation.router, prefix="/cv", tags=["Validation"])
api_router.include_router(context_suggestions.router, prefix="/cv", tags=["Inspection Context"])
api_router.include_router(measurement.router, prefix="/cv", tags=["Measurement"])
api_router.include_router(multi_frame.router, prefix="/cv", tags=["Multi-Frame Measurement"])
api_router.include_router(calibration.router, prefix="/cv", tags=["Calibration"])
