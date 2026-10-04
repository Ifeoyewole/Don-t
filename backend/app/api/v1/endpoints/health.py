"""Health check endpoint providing runtime operational status, OpenCV metadata, and model diagnostics."""

from datetime import datetime, timezone
from typing import Dict, Optional
import cv2
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.core.cv.ai.wrc_inception_classifier import get_wrc_classifier

router = APIRouter()


class ExternalModelHealth(BaseModel):
    """External baseline model health descriptor."""
    enabled: bool = Field(..., description="Whether model integration is enabled in config")
    loaded: bool = Field(..., description="Whether model weights are loaded and ready")
    model_id: str = Field(..., description="Registered model identifier")


class HealthResponse(BaseModel):
    """Health check status payload."""
    status: str = Field(default="ok", description="Service health status.")
    version: str = Field(default="1.0.0", description="Backend service version.")
    opencv_version: str = Field(..., description="Active OpenCV runtime version.")
    external_models: Optional[Dict[str, ExternalModelHealth]] = Field(
        default=None,
        description="Diagnostics for external baseline models.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of health check.",
    )


@router.get("/health", response_model=HealthResponse, summary="Service Health & Diagnostics")
async def get_health() -> HealthResponse:
    """Return backend operational status, OpenCV version, and external baseline health."""
    wrc = get_wrc_classifier()
    external_models = {
        "wrc_inceptionresnetv2": ExternalModelHealth(
            enabled=wrc.enabled,
            loaded=wrc.is_available,
            model_id=wrc.model_id,
        )
    }

    return HealthResponse(
        status="ok",
        version="1.0.0",
        opencv_version=cv2.__version__,
        external_models=external_models,
    )
