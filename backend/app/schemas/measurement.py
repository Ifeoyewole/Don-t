"""Measurement data contracts and computer vision response schemas."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.domain import JointType, ToleranceStatus


class Point2D(BaseModel):
    """2D pixel coordinate representation."""
    x: float = Field(..., description="X coordinate in image pixels")
    y: float = Field(..., description="Y coordinate in image pixels")


class ToleranceSpec(BaseModel):
    """Tolerance specification parameters for pass/fail classification."""
    nominal_gap_mm: float = Field(
        default=10.0,
        description="Target/nominal gap distance in millimeters.",
    )
    min_gap_mm: float = Field(
        default=3.0,
        description="Minimum acceptable gap in millimeters.",
    )
    max_gap_mm: float = Field(
        default=15.0,
        description="Maximum acceptable gap in millimeters.",
    )
    warning_margin_mm: float = Field(
        default=2.0,
        description="Safety buffer margin adjacent to tolerance boundaries.",
    )


class RaySample(BaseModel):
    """Radial ray measurement sample for circular joints."""
    angle_deg: float = Field(..., description="Angle of the radial ray in degrees [0, 360).")
    inner_point: Point2D = Field(..., description="Detected inner pipe edge coordinate.")
    outer_point: Point2D = Field(..., description="Detected outer collar edge coordinate.")
    gap_px: float = Field(..., description="Measured annular gap length in pixels.")
    gap_mm: float = Field(..., description="Calibrated gap length in millimeters.")
    status: ToleranceStatus = Field(..., description="Pass/fail/warning evaluation for this ray.")


class DetectedCircle(BaseModel):
    """Detected circle parameters from Hough transform / sub-pixel contour fitting."""
    center_x: float = Field(..., description="Circle center X coordinate in pixels.")
    center_y: float = Field(..., description="Circle center Y coordinate in pixels.")
    radius_px: float = Field(..., description="Circle radius in pixels.")
    radius_mm: Optional[float] = Field(None, description="Calibrated radius in millimeters.")
    confidence: float = Field(default=1.0, description="Detection confidence score (0.0 to 1.0).")


class GapLine(BaseModel):
    """Linear cross-seam distance sample for horizontal/vertical welds and joints."""
    start: Point2D = Field(..., description="Edge point on left/top boundary.")
    end: Point2D = Field(..., description="Corresponding edge point on right/bottom boundary.")
    gap_px: float = Field(..., description="Gap width in pixels.")
    gap_mm: float = Field(..., description="Calibrated gap width in millimeters.")
    status: ToleranceStatus = Field(..., description="Tolerance evaluation for this cross-section.")


class OverlayHints(BaseModel):
    """Geometric coordinates and contours for high-performance frontend canvas rendering."""
    inner_circle: Optional[DetectedCircle] = Field(None, description="Fitted inner circumference.")
    outer_circle: Optional[DetectedCircle] = Field(None, description="Fitted outer circumference.")
    center: Optional[Point2D] = Field(None, description="Calculated joint center point.")
    ray_samples: List[RaySample] = Field(default_factory=list, description="All radial ray measurement samples.")
    gap_lines: List[GapLine] = Field(default_factory=list, description="All seam cross-section samples.")
    seam_left_edge: Optional[List[Point2D]] = Field(None, description="Contour polyline for left/top edge.")
    seam_right_edge: Optional[List[Point2D]] = Field(None, description="Contour polyline for right/bottom edge.")
    bounding_box: Optional[List[float]] = Field(None, description="[x, y, w, h] ROI bounding box.")


class CvMeasurementDebug(BaseModel):
    """Detailed algorithmic diagnostics and sub-pixel metrics."""
    pixels_per_mm: float = Field(..., description="Spatial scale factor in pixels per millimeter.")
    inner_radius_px: Optional[float] = Field(None, description="Inner wall radius in pixels.")
    outer_radius_px: Optional[float] = Field(None, description="Outer wall radius in pixels.")
    num_samples: int = Field(..., description="Number of valid measurement vectors extracted.")
    raw_min_gap_mm: float = Field(..., description="Unfiltered minimum gap measurement in mm.")
    raw_max_gap_mm: float = Field(..., description="Unfiltered maximum gap measurement in mm.")
    raw_mean_gap_mm: float = Field(..., description="Unfiltered mean gap measurement in mm.")
    std_gap_mm: float = Field(..., description="Standard deviation of gap distribution across samples in mm.")
    processing_time_ms: float = Field(..., description="Total CV algorithm execution time in milliseconds.")
    debug_image_base64: Optional[str] = Field(None, description="Annotated visualization overlay encoded as JPEG base64.")


class MeasurementResponse(BaseModel):
    """Top-level structured response payload returned by measurement API."""
    joint_type: JointType = Field(..., description="Classified or requested joint type.")
    pipe_diameter_mm: float = Field(..., description="Nominal reference pipe diameter in millimeters.")
    pixels_per_mm: float = Field(..., description="Calibrated scale factor.")
    mean_gap_mm: float = Field(..., description="Average measured gap clearance across all sample locations.")
    min_gap_mm: float = Field(..., description="Minimum recorded gap clearance in mm.")
    max_gap_mm: float = Field(..., description="Maximum recorded gap clearance in mm.")
    overall_status: ToleranceStatus = Field(..., description="Comprehensive QA classification.")
    overlay_hints: OverlayHints = Field(..., description="Frontend overlay graphics coordinates.")
    debug_info: Optional[CvMeasurementDebug] = Field(None, description="Optional diagnostic measurements.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the measurement.",
    )
