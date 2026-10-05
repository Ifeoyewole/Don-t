"""Camera profile and calibration schemas for lens distortion rectification and spatial scaling."""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class CameraProfile(BaseModel):
    """Camera intrinsic parameters and lens distortion model."""
    camera_id: str = Field(..., description="Unique identifier for the camera or sensor rig (e.g. 'CCTV-01-WIDE')")
    resolution: Tuple[int, int] = Field(..., description="Image resolution (width, height) in pixels")
    focal_length: Tuple[float, float] = Field(..., description="(fx, fy) focal lengths in pixels")
    principal_point: Tuple[float, float] = Field(..., description="(cx, cy) optical center in pixels")
    distortion_coeffs: List[float] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0],
        description="Radial and tangential distortion coefficients [k1, k2, p1, p2, k3]",
    )
    tilt_angle_deg: Optional[float] = Field(
        default=0.0,
        description="Estimated or measured off-axis camera pitch/tilt angle in degrees",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional human-readable description of camera hardware and optics",
    )


class CalibrationRequest(BaseModel):
    """Request payload to test or update camera calibration."""
    profile: CameraProfile
    test_diameter_mm: Optional[float] = Field(None, description="Known calibration target diameter in mm")
