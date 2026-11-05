"""Photo validation and image quality assessment schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.domain import CalibrationSource, DomainStatus, ExposureStatus, JointType


class PhotoQualityResult(BaseModel):
    """Quality metrics and feedback on input inspection photo."""

    blur_score: float = Field(
        ...,
        description="Laplacian variance score measuring image sharpness. Higher is sharper.",
    )
    is_blurry: bool = Field(
        ...,
        description="Flag indicating if blur score is below the acceptable threshold.",
    )
    mean_brightness: float = Field(
        ...,
        description="Average luminance of the image (0-255).",
    )
    exposure_status: ExposureStatus = Field(
        ...,
        description="Exposure condition classification ('OK', 'UNDEREXPOSED', 'OVEREXPOSED').",
    )
    glare_percentage: float = Field(
        ...,
        description="Percentage of pixels in over-saturated glare region (0-100%).",
    )
    glare_detected: bool = Field(
        ...,
        description="Flag indicating significant specular glare in the inspection area.",
    )
    is_acceptable: bool = Field(
        default=True,
        description="Overall boolean indicating whether photo quality is sufficient for CV measurement.",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable user tips if photo quality issues are detected.",
    )


class AdvisoryCalibrationMetadata(BaseModel):
    """Unverified, editable diameter and source copied from submitted metadata, never from AI."""

    pipe_diameter_mm: Optional[float] = Field(default=None, gt=0.0, le=5000.0)
    source: Optional[CalibrationSource] = None
    verified: bool = False
    calibration_reference_id: Optional[str] = None


class InspectionContextSuggestions(BaseModel):
    """Untrusted, editable image-derived hints; never calibration or defect authority."""

    model: str = Field(..., description="Actual image-assessment model used by the semantic gate.")
    domain_status: DomainStatus
    processing_allowed: bool
    review_required: bool = True
    calibration: AdvisoryCalibrationMetadata = Field(default_factory=AdvisoryCalibrationMetadata)
    source: str = Field(default="IMAGE_ADVISORY", description="No private inspection history or customer data is used.")
    suggested_joint_type: Optional[JointType] = None
    suggested_inspection_context: Optional[str] = Field(default=None, max_length=400)
    possible_gap_visible: Optional[bool] = None
    calibration_verified: bool = Field(default=False, description="Never infer calibration verification from pixels.")
    calibration_reference_id: Optional[str] = Field(default=None, description="AI must not invent calibration references.")
    pipe_diameter_mm: Optional[float] = Field(default=None, description="AI must not infer pipe diameter from image.")
    guidance: str = Field(
        default="Review and edit suggestions before inspection. Source diameter from trusted project records; the server alone verifies calibration.",
    )
