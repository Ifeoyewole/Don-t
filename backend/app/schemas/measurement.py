"""Measurement data contracts and computer vision response schemas."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.calibration import CalibrationProfile
from backend.app.schemas.domain import (
    CalibrationSource,
    DomainStatus,
    JointConditionClass,
    JointType,
    MeasurementResultStatus,
    ToleranceStatus,
)


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
    gap_mm: Optional[float] = Field(None, description="Calibrated gap length in millimeters.")
    status: Optional[ToleranceStatus] = Field(None, description="Pass/fail/warning evaluation for this ray.")


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
    gap_mm: Optional[float] = Field(None, description="Calibrated gap width in millimeters.")
    status: Optional[ToleranceStatus] = Field(None, description="Tolerance evaluation for this cross-section.")


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
    pixels_per_mm: Optional[float] = Field(None, description="Spatial scale factor in pixels per millimeter.")
    inner_radius_px: Optional[float] = Field(None, description="Inner wall radius in pixels.")
    outer_radius_px: Optional[float] = Field(None, description="Outer wall radius in pixels.")
    num_samples: int = Field(..., description="Number of valid measurement vectors extracted.")
    raw_min_gap_mm: Optional[float] = Field(None, description="Unfiltered minimum gap measurement in mm.")
    raw_max_gap_mm: Optional[float] = Field(None, description="Unfiltered maximum gap measurement in mm.")
    raw_mean_gap_mm: Optional[float] = Field(None, description="Unfiltered mean gap measurement in mm.")
    std_gap_mm: Optional[float] = Field(None, description="Standard deviation of gap distribution across samples in mm.")
    processing_time_ms: float = Field(..., description="Total CV algorithm execution time in milliseconds.")
    debug_image_base64: Optional[str] = Field(None, description="Annotated visualization overlay encoded as JPEG base64.")
    total_ray_count: Optional[int] = Field(None, description="Total radial rays attempted.")
    valid_ray_count: Optional[int] = Field(None, description="Rays with independently detected inner and outer edges.")
    valid_ray_fraction: Optional[float] = Field(None, description="Fraction of attempted rays that supplied valid evidence.")
    angular_coverage: Optional[float] = Field(None, description="Fraction of angular sectors containing valid evidence.")
    coverage_sector_count: Optional[int] = Field(None, description="Number of occupied angular sectors.")
    coverage_status: Optional[str] = Field(None, description="FULL, PARTIAL, or INSUFFICIENT.")
    invalid_reason_counts: Optional[dict[str, int]] = Field(None, description="Counts of rejected rays by reason.")
    geometry_tier: Optional[str] = Field(None, description="Geometry evidence tier: ACCEPTABLE_GEOMETRY, PARTIAL_REVIEW_GEOMETRY, or REJECTED_UNRELIABLE.")

class ConfidenceBreakdown(BaseModel):
    """Detailed multi-component confidence metrics and calibrated decision gating."""
    quality_score: float = Field(..., description="Image quality & clarity score (0.0 to 1.0)")
    segmentation_score: float = Field(..., description="AI joint boundary segmentation score (0.0 to 1.0)")
    condition_score: float = Field(..., description="Joint condition classifier confidence (0.0 to 1.0)")
    geometry_score: float = Field(..., description="OpenCV edge gradient & circle fit score (0.0 to 1.0)")
    temporal_score: Optional[float] = Field(None, description="Multi-frame temporal consistency score (0.0 to 1.0)")
    measurement_confidence: float = Field(..., description="Measurement-only confidence score (quality, localization, geometry, temporal)")
    classification_confidence: Optional[float] = Field(None, description="Defect classification confidence score (WRc)")
    overall_confidence: float = Field(..., description="Measurement confidence score governing acceptance gating")
    decision: MeasurementResultStatus = Field(
        ...,
        description="Calibrated gating decision: ACCEPTED_MEASUREMENT, REVIEW_REQUIRED, or REJECTED_UNRELIABLE",
    )


class ExternalClassTopK(BaseModel):
    """Single top-k class prediction from external classifier."""
    index: int = Field(..., description="Class index in model output")
    raw_class_name: str = Field(..., description="Raw class name from external model")
    raw_class_code: Optional[str] = Field(None, description="External standard defect code (e.g. JD, DE, B)")
    score: float = Field(..., description="Model confidence score for this class (0.0 to 1.0)")
    jointinspect_mapping: Optional[str] = Field(None, description="Mapped JointInspect condition concept or None")


class ExternalClassifierResult(BaseModel):
    """External sewer defect baseline classifier result contract (Advisory Baseline)."""
    model_id: str = Field(default="wrc-inceptionresnetv2-baseline-v1", description="External model identity")
    source: str = Field(default="WRc", description="Training dataset origin")
    raw_class_code: Optional[str] = Field(None, description="Top-1 WRc defect code")
    raw_class_name: str = Field(..., description="Top-1 raw WRc class name")
    confidence: float = Field(..., description="Model probability score for top-1 class (MODEL_SCORE)")
    top_k: List[ExternalClassTopK] = Field(default_factory=list, description="Top-K predicted classes")
    jointinspect_mapping: Optional[str] = Field(None, description="Conservative JointInspect condition category")
    mapping_status: str = Field(..., description="Mapping outcome: DIRECT, GROUPED, UNMAPPED, or AMBIGUOUS")
    advisory_only: bool = Field(default=True, description="Strictly advisory; no measurement or tolerance authority")
    status: str = Field(default="SUCCESS", description="SUCCESS, LOW_CONFIDENCE_CLASSIFICATION, or EXTERNAL_CLASSIFIER_UNAVAILABLE")


class ClassifierEvidence(BaseModel):
    """Evidence and top-k distributions from the primary condition classifier (WRc InceptionResNetV2)."""
    classifier: str = Field(default="WRc InceptionResNetV2", description="Active live classifier name")
    model_id: str = Field(default="wrc-inceptionresnetv2-baseline-v1", description="Model architecture identifier")
    raw_prediction: str = Field(..., description="Top-1 raw predicted defect name")
    raw_code: Optional[str] = Field(None, description="Top-1 standard defect code (e.g. JD, CK, DE)")
    confidence: float = Field(..., description="Classifier confidence score")
    mapped_condition: Optional[str] = Field(None, description="Mapped JointInspect condition concept or None")
    mapping_status: str = Field(..., description="Outcome: DIRECT, GROUPED, UNMAPPED, or AMBIGUOUS")
    top_k: List[ExternalClassTopK] = Field(default_factory=list, description="Top-k distribution")
    classification_status: str = Field(default="SUCCESS", description="SUCCESS, LOW_CONFIDENCE_CLASSIFICATION, or EXTERNAL_CLASSIFIER_UNAVAILABLE")


class ModelComparisonResult(BaseModel):
    """Comparison and disagreement tracking across visual assessment systems for beta evaluation."""
    wrc_baseline_prediction: Optional[str] = Field(None, description="WRc external classifier prediction")
    wrc_baseline_score: Optional[float] = Field(None, description="WRc model score")
    native_model_b_prediction: Optional[str] = Field(None, description="JointInspect native Model B prediction")
    native_model_b_score: Optional[float] = Field(None, description="JointInspect native Model B score")
    vertex_observation: Optional[str] = Field(None, description="Vertex AI semantic observation")
    wrc_vs_native_agreement: str = Field(..., description="AGREE, DISAGREE, NOT_COMPARABLE, or UNMAPPED")
    wrc_vs_vertex_agreement: str = Field(..., description="AGREE, DISAGREE, NOT_COMPARABLE, or UNMAPPED")
    native_vs_vertex_agreement: str = Field(..., description="AGREE, DISAGREE, NOT_COMPARABLE, or UNMAPPED")
    human_review_required: bool = Field(default=False, description="Flagged for manual review on strong disagreement")
    availability: Optional[dict[str, str]] = Field(None, description="Explicit system execution status (e.g. {'vertex': 'LIVE', 'model_a': 'AVAILABLE', ...})")
    run_mode: Optional[str] = Field(None, description="FULL_MULTI_MODEL if all systems executed, else PARTIAL_MULTI_MODEL")


class VertexSemanticGateResult(BaseModel):
    """Semantic domain evaluation and multi-modal context understanding."""
    domain_status: DomainStatus = Field(..., description="Semantic domain status")
    pipe_visible: bool = Field(..., description="Whether a pipe interior is clearly visible")
    joint_visible: bool = Field(..., description="Whether a pipe joint is visible")
    quality: str = Field(..., description="Visual quality assessment (OK, BLURRY, UNDEREXPOSED, OVEREXPOSED, DEGRADED)")
    prompt_image_conflict: bool = Field(default=False, description="Whether operator context conflicts with visual evidence")
    conflict_reason: Optional[str] = Field(None, description="Structured prompt conflict category e.g. ENGINEERING_STATUS_OVERRIDE_ATTEMPT, PHYSICAL_MEASUREMENT_OVERRIDE_ATTEMPT, CALIBRATION_OVERRIDE_ATTEMPT, DOMAIN_CONTRADICTION")
    processing_allowed: bool = Field(..., description="Whether joint geometry processing is permitted")
    user_message: str = Field(..., description="Operator guidance message")
    observation: str = Field(..., description="Detailed semantic visual observation")
    model: str = Field(default="gemini-2.5-flash", description="Underlying multimodal model ID")
    confidence: float = Field(default=1.0, description="Semantic confidence score")


class MeasurementResponse(BaseModel):
    """Top-level structured response payload returned by measurement API."""
    joint_type: JointType = Field(..., description="Classified or requested joint type.")
    mean_gap_px: Optional[float] = Field(None, description="Average measured gap clearance across all sample locations in pixels.")
    min_gap_px: Optional[float] = Field(None, description="Minimum recorded gap clearance in pixels.")
    max_gap_px: Optional[float] = Field(None, description="Maximum recorded gap clearance in pixels.")
    pipe_diameter_mm: Optional[float] = Field(None, description="Nominal reference pipe diameter in millimeters.")
    pixels_per_mm: Optional[float] = Field(None, description="Calibrated scale factor.")
    mean_gap_mm: Optional[float] = Field(None, description="Average measured gap clearance across all sample locations in mm.")
    min_gap_mm: Optional[float] = Field(None, description="Minimum recorded gap clearance in mm.")
    max_gap_mm: Optional[float] = Field(None, description="Maximum recorded gap clearance in mm.")
    candidate_gap_mm: Optional[float] = Field(None, description="Non-authoritative raw calibrated gap mm for diagnostics when geometry is rejected.")
    overall_status: ToleranceStatus = Field(..., description="Comprehensive QA classification.")
    result_status: MeasurementResultStatus = Field(
        default=MeasurementResultStatus.ACCEPTED_MEASUREMENT,
        description="Statistically calibrated production acceptance gating.",
    )
    condition: Optional[JointConditionClass] = Field(
        default=None,
        description="Classified joint structural condition (e.g. normal, displaced, open, damaged).",
    )
    confidence_breakdown: Optional[ConfidenceBreakdown] = Field(
        default=None,
        description="Component-level confidence metrics and gating justification.",
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Explanation when measurement is rejected or requires review.",
    )
    overlay_hints: OverlayHints = Field(..., description="Frontend overlay graphics coordinates.")
    debug_info: Optional[CvMeasurementDebug] = Field(None, description="Optional diagnostic measurements.")
    external_classifier: Optional[ExternalClassifierResult] = Field(
        default=None,
        description="External sewer baseline classifier result (WRc InceptionResNetV2).",
    )
    classifier_evidence: Optional[ClassifierEvidence] = Field(
        default=None,
        description="Primary live defect condition classifier evidence (WRc InceptionResNetV2).",
    )
    model_comparison: Optional[ModelComparisonResult] = Field(
        default=None,
        description="Beta-testing model comparison and disagreement telemetry (None in normal beta).",
    )
    semantic_gate: Optional[VertexSemanticGateResult] = Field(
        default=None,
        description="Vertex AI semantic domain gate and multi-modal context understanding.",
    )
    calibration_source: Optional[CalibrationSource] = Field(
        default=None,
        description="Provenance of calibration data.",
    )
    calibration_profile: Optional[CalibrationProfile] = Field(
        default=None,
        description="Structured reusable project calibration profile applied to measurement.",
    )
    geometry_tier: Optional[str] = Field(
        default=None,
        description="Zero-guessing geometry tier: ACCEPTABLE_GEOMETRY, PARTIAL_REVIEW_GEOMETRY, or REJECTED_UNRELIABLE.",
    )
    physical_measurement_available: bool = Field(
        default=False,
        description="True ONLY when verified calibration is present and valid geometry was resolved.",
    )
    authoritative_gap_mm: Optional[float] = Field(
        default=None,
        description="Authoritative gap in millimeters ONLY if physical_measurement_available is True.",
    )
    engineering_result: ToleranceStatus = Field(
        default=ToleranceStatus.FAIL,
        description="Authoritative PASS/FAIL/REVIEW governed solely by engineering rules.",
    )
    authoritative_reason: str = Field(
        default="Default initial evaluation pending pipeline execution.",
        description="Engineering determination rationale.",
    )
    ai_explanation: Optional[str] = Field(
        default=None,
        description="Vertex AI explanation of inspection results.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the measurement.",
    )


