"""Camera calibration profile management endpoints."""

from typing import Dict, List
from fastapi import APIRouter, HTTPException, status

from backend.app.core.cv.calibration import camera_calibrator
from backend.app.schemas.calibration import CameraProfile

router = APIRouter()


@router.get(
    "/calibration/profiles",
    response_model=List[CameraProfile],
    summary="List All Active Camera Calibration Profiles",
)
async def list_camera_profiles() -> List[CameraProfile]:
    """Retrieve all pre-configured camera intrinsic and distortion profiles."""
    return list(camera_calibrator._profiles.values())


@router.get(
    "/calibration/profiles/{camera_id}",
    response_model=CameraProfile,
    summary="Get Specific Camera Profile",
)
async def get_camera_profile(camera_id: str) -> CameraProfile:
    """Fetch intrinsic calibration parameters by camera identifier."""
    profile = camera_calibrator.get_profile(camera_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera profile '{camera_id}' not found.",
        )
    return profile


try:
    from backend.app.config import settings
except ImportError:
    from app.config import settings


@router.post(
    "/calibration/profiles",
    response_model=CameraProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Register or Update a Camera Profile",
)
async def register_camera_profile(profile: CameraProfile) -> CameraProfile:
    """Register custom camera intrinsic matrix and lens distortion coefficients."""
    if not settings.CALIBRATION_MUTATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration profile modification is restricted in production pending administrative role delegation.",
        )
    camera_calibrator.register_profile(profile)
    return profile
