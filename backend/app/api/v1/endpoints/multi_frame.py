"""Multi-frame video sequence measurement endpoint."""

from typing import List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.core.cv.circular_detector import measure_circular_gap
from backend.app.core.cv.confidence import confidence_engine
from backend.app.core.cv.fusion import MultiFrameFusion, MultiFrameFusionResult
from backend.app.schemas.domain import (
    CalibrationSource,
    JointConditionClass,
    JointType,
    MeasurementResultStatus,
    ToleranceStatus,
)
from backend.app.schemas.measurement import ToleranceSpec
from backend.app.utils.image_io import decode_image_bytes

router = APIRouter()


class MultiFrameMeasurementResponse(BaseModel):
    """Aggregated temporal measurement results across a burst of video frames."""
    joint_type: JointType
    pipe_diameter_mm: Optional[float] = None
    calibration_source: Optional[CalibrationSource] = None
    calibration_verified: bool = False
    physical_measurement_available: bool = False
    num_frames_received: int
    num_frames_accepted: int
    median_gap_px: float = Field(..., description="Robust median gap across accepted frames in pixels")
    min_gap_px: float = Field(..., description="Minimum gap across accepted frames in pixels")
    max_gap_px: float = Field(..., description="Maximum gap across accepted frames in pixels")
    mad_px: float = Field(..., description="Median Absolute Deviation of gap across temporal sequence in pixels")
    median_gap_mm: Optional[float] = Field(None, description="Robust median gap in mm if verified calibration present")
    min_gap_mm: Optional[float] = Field(None, description="Minimum gap in mm if verified calibration present")
    max_gap_mm: Optional[float] = Field(None, description="Maximum gap in mm if verified calibration present")
    mad_mm: Optional[float] = Field(None, description="Median Absolute Deviation in mm if verified calibration present")
    temporal_consistency_score: float = Field(..., description="Temporal stability score (0.0 to 1.0)")
    outlier_frame_indices: List[int]
    result_status: MeasurementResultStatus
    condition: Optional[JointConditionClass] = None
    overall_confidence: float
    rejection_reason: Optional[str] = None


@router.post(
    "/measure/multi-frame",
    response_model=MultiFrameMeasurementResponse,
    summary="Compute Multi-Frame Fused Gap Measurements with MAD Outlier Rejection",
)
async def measure_multi_frame_burst(
    files: List[UploadFile] = File(..., description="List of consecutive CCTV video frames (2 to 30 frames)."),
    pipe_diameter_mm: Optional[float] = Form(None, gt=0.0, le=5000.0),
    calibration_source: Optional[CalibrationSource] = Form(None),
    calibration_verified: bool = Form(False),
    max_gap_mm: Optional[float] = Form(None, gt=0.0, le=500.0),
) -> MultiFrameMeasurementResponse:
    """Analyze consecutive CCTV frames, reject transient outlier spikes, and emit robust median measurement."""
    if len(files) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multi-frame measurement requires at least 2 consecutive frames.",
        )
    if len(files) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multi-frame measurement exceeds maximum burst sequence limit of 30 frames.",
        )

    verified_sources = {
        CalibrationSource.PROJECT_METADATA,
        CalibrationSource.MANHOLE_METADATA,
        CalibrationSource.PHYSICAL_REFERENCE,
        CalibrationSource.CAMERA_CALIBRATION,
        CalibrationSource.TEST_RIG,
    }
    is_calibrated = (
        calibration_source in verified_sources
        and calibration_verified is True
        and pipe_diameter_mm is not None
        and pipe_diameter_mm > 0.0
    )

    measured_gaps_px: List[float] = []
    measured_gaps_mm: List[float] = []
    total_payload_bytes = 0
    max_total_bytes = 30 * 1024 * 1024  # 30 MB

    from backend.app.core.cv.ai.vertex_semantic_gate import get_vertex_semantic_gate
    from backend.app.core.cv.ai.image_quality import validate_image_quality
    vertex_gate = get_vertex_semantic_gate()
    representative_validated = False

    for idx, file in enumerate(files):
        content = await file.read()
        if not content:
            continue
        total_payload_bytes += len(content)
        if total_payload_bytes > max_total_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total multi-frame payload exceeds {max_total_bytes} bytes limit.",
            )
        try:
            image_bgr = decode_image_bytes(content)

            # Representative frame semantic domain validation for multi-frame burst
            if not representative_validated:
                sem_res = vertex_gate.evaluate(image_bgr)
                if not sem_res.processing_allowed:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=sem_res.user_message or "Semantic gatekeeper blocked multi-frame burst (fail-closed).",
                    )
                representative_validated = True
            else:
                # Deterministic local optical quality checks on remaining frames
                q_res = validate_image_quality(image_bgr)
                if not q_res.usable:
                    continue

            res = measure_circular_gap(
                image_bgr=image_bgr,
                pipe_diameter_mm=pipe_diameter_mm if is_calibrated else None,
                num_rays=48,
                return_debug_image=False,
            )
            gap_px = res.mean_gap_px if res.mean_gap_px is not None else (res.debug_info.mean_gap_px if res.debug_info else None)
            if gap_px is not None and gap_px > 0.0:
                measured_gaps_px.append(gap_px)
                if is_calibrated and res.mean_gap_mm is not None:
                    measured_gaps_mm.append(res.mean_gap_mm)
        except HTTPException:
            raise
        except Exception:
            # Skip unresolvable or rejected frames in burst
            continue

    if not measured_gaps_px:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="joint_geometry_not_reliable: No frames in sequence could resolve pipe joint boundaries.",
        )

    # Fuse pixel measurements
    fusion_px = MultiFrameFusion.fuse_frame_measurements(measured_gaps_px)
    overall_conf = round(float(fusion_px.temporal_consistency_score * 0.95), 3)

    if is_calibrated and measured_gaps_mm:
        fusion_mm = MultiFrameFusion.fuse_frame_measurements(measured_gaps_mm)
        fused_median_mm = fusion_mm.fused_mean_gap_mm
        fused_min_mm = fusion_mm.fused_min_gap_mm
        fused_max_mm = fusion_mm.fused_max_gap_mm
        mad_mm = fusion_mm.mad_mm
        physical_avail = True
        
        # Tolerance evaluation
        if max_gap_mm is not None and fused_median_mm > max_gap_mm:
            condition = JointConditionClass.OPEN_JOINT
        else:
            condition = JointConditionClass.NORMAL_JOINT

        if overall_conf >= 0.90:
            result_status = MeasurementResultStatus.ACCEPTED_MEASUREMENT
        elif overall_conf >= 0.70:
            result_status = MeasurementResultStatus.REVIEW_REQUIRED
        else:
            result_status = MeasurementResultStatus.REJECTED_UNRELIABLE
        rejection_reason = None
    else:
        fused_median_mm = None
        fused_min_mm = None
        fused_max_mm = None
        mad_mm = None
        physical_avail = False
        condition = None  # Do not guess condition without calibration
        result_status = MeasurementResultStatus.REVIEW_REQUIRED
        rejection_reason = "CALIBRATION_REQUIRED: Multi-frame sequence lacks verified calibration. Millimeters withheld."

    return MultiFrameMeasurementResponse(
        joint_type=JointType.CIRCULAR_OPENING,
        pipe_diameter_mm=pipe_diameter_mm if is_calibrated else None,
        calibration_source=calibration_source,
        calibration_verified=calibration_verified,
        physical_measurement_available=physical_avail,
        num_frames_received=len(files),
        num_frames_accepted=fusion_px.num_accepted_frames,
        median_gap_px=fusion_px.fused_mean_gap_mm,  # values passed were px
        min_gap_px=fusion_px.fused_min_gap_mm,
        max_gap_px=fusion_px.fused_max_gap_mm,
        mad_px=fusion_px.mad_mm,
        median_gap_mm=fused_median_mm,
        min_gap_mm=fused_min_mm,
        max_gap_mm=fused_max_mm,
        mad_mm=mad_mm,
        temporal_consistency_score=fusion_px.temporal_consistency_score,
        outlier_frame_indices=fusion_px.outlier_frame_indices,
        result_status=result_status,
        condition=condition,
        overall_confidence=overall_conf,
        rejection_reason=rejection_reason,
    )
