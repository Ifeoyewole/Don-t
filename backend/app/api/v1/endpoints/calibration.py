"""Camera calibration profile management endpoints."""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.core.cv.calibration import camera_calibrator
from backend.app.core.cv.calibration_authority import get_verified_calibration
from backend.app.schemas.domain import CalibrationSource
from backend.app.schemas.calibration import CameraProfile

router = APIRouter()


@router.get(
    "/calibration/profiles",
    response_model=List[CameraProfile],
    summary="List All Active Camera Calibration Profiles",
)
async def list_camera_profiles() -> List[CameraProfile]:
    """Retrieve all pre-configured camera intrinsic and distortion profiles."""
    return camera_calibrator.list_profiles()


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


class CalibrationReferenceCheck(BaseModel):
    """Untrusted browser metadata. The server registry is the only authority."""

    reference_id: str = Field(..., min_length=1, max_length=160)
    project_id: str = Field(..., min_length=1, max_length=160)
    source: CalibrationSource
    pipe_diameter_mm: float = Field(..., gt=0.0, le=5000.0)
    camera_id: Optional[str] = Field(default=None, max_length=160)


class CalibrationReferenceStatus(BaseModel):
    reference_verified: bool
    status: str
    guidance: str


@router.post(
    "/calibration/check-reference",
    response_model=CalibrationReferenceStatus,
    summary="Check whether a calibration reference matches a server-owned record",
)
async def check_calibration_reference(
    request: CalibrationReferenceCheck,
) -> CalibrationReferenceStatus:
    """Read-only preflight; recognition does not replace geometry confidence checks."""
    verified = get_verified_calibration(
        reference_id=request.reference_id.strip(),
        project_id=request.project_id,
        source=request.source,
        pipe_diameter_mm=request.pipe_diameter_mm,
        camera_id=request.camera_id or None,
    )
    if verified is None:
        return CalibrationReferenceStatus(
            reference_verified=False,
            status="CALIBRATION_REQUIRED",
            guidance=(
                "No matching server-verified reference for this project, camera and diameter. "
                "Physical millimetres remain unavailable; pixel geometry and review can continue."
            ),
        )
    return CalibrationReferenceStatus(
        reference_verified=True,
        status="REFERENCE_MATCHED",
        guidance=(
            "A server-owned calibration reference matches these fields. "
            "Each photo still needs reliable geometry and its own perspective/scale validation; "
            "a matching record does not guarantee acceptance."
        ),
    )
