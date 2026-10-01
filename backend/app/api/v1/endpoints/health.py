"""Health check endpoint providing runtime operational status and OpenCV build metadata."""

from datetime import datetime, timezone
import cv2
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check status payload."""
    status: str = Field(default="ok", description="Service health status.")
    version: str = Field(default="1.0.0", description="Backend service version.")
    opencv_version: str = Field(..., description="Active OpenCV runtime version.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of health check.",
    )


@router.get("/health", response_model=HealthResponse, summary="Service Health & Diagnostics")
async def get_health() -> HealthResponse:
    """Return backend operational status and OpenCV library version."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        opencv_version=cv2.__version__,
    )
