"""Photo validation and image quality assessment schemas."""

from typing import List
from pydantic import BaseModel, Field
from backend.app.schemas.domain import ExposureStatus


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
