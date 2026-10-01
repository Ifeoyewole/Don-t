"""Multi-frame video sequence measurement endpoint."""

from typing import List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.core.cv.circular_detector import measure_circular_gap
from backend.app.core.cv.confidence import confidence_engine
from backend.app.core.cv.fusion import MultiFrameFusion, MultiFrameFusionResult
from backend.app.schemas.domain import (
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
    pipe_diameter_mm: float
    num_frames_received: int
    num_frames_accepted: int
    median_gap_mm: float
    min_gap_mm: float
    max_gap_mm: float
    mad_mm: float = Field(..., description="Median Absolute Deviation in mm")
    temporal_consistency_score: float = Field(..., description="Temporal stability score (0.0 to 1.0)")
    outlier_frame_indices: List[int]
    result_status: MeasurementResultStatus
    condition: Optional[JointConditionClass] = None
    overall_confidence: float


@router.post(
    "/measure/multi-frame",
    response_model=MultiFrameMeasurementResponse,
    summary="Compute Multi-Frame Fused Gap Measurements with MAD Outlier Rejection",
)
async def measure_multi_frame_burst(
    files: List[UploadFile] = File(..., description="List of consecutive CCTV video frames (2 to 30 frames)."),
    pipe_diameter_mm: float = Form(100.0, gt=0.0, le=5000.0),
    max_gap_mm: Optional[float] = Form(15.0, gt=0.0, le=500.0),
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

    measured_gaps: List[float] = []
    total_payload_bytes = 0
    max_total_bytes = 30 * 1024 * 1024  # 30 MB

    for file in files:
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
            res = measure_circular_gap(
                image_bgr=image_bgr,
                pipe_diameter_mm=pipe_diameter_mm,
                num_rays=48,
                return_debug_image=False,
            )
            measured_gaps.append(res.mean_gap_mm)
        except Exception:
            # Skip unresolvable frames in burst
            continue

    if not measured_gaps:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="joint_geometry_not_reliable: No frames in sequence could resolve pipe joint boundaries.",
        )

    fusion_res = MultiFrameFusion.fuse_frame_measurements(measured_gaps)

    # Condition determination: tolerance-primary
    if max_gap_mm and fusion_res.fused_mean_gap_mm > max_gap_mm:
        condition = JointConditionClass.OPEN_JOINT
    else:
        condition = JointConditionClass.NORMAL_JOINT

    # Confidence gating
    overall_conf = round(float(fusion_res.temporal_consistency_score * 0.95), 3)
    if overall_conf >= 0.90:
        result_status = MeasurementResultStatus.ACCEPTED_MEASUREMENT
    elif overall_conf >= 0.70:
        result_status = MeasurementResultStatus.REVIEW_REQUIRED
    else:
        result_status = MeasurementResultStatus.REJECTED_UNRELIABLE

    return MultiFrameMeasurementResponse(
        joint_type=JointType.CIRCULAR_OPENING,
        pipe_diameter_mm=pipe_diameter_mm,
        num_frames_received=len(files),
        num_frames_accepted=fusion_res.num_accepted_frames,
        median_gap_mm=fusion_res.fused_mean_gap_mm,
        min_gap_mm=fusion_res.fused_min_gap_mm,
        max_gap_mm=fusion_res.fused_max_gap_mm,
        mad_mm=fusion_res.mad_mm,
        temporal_consistency_score=fusion_res.temporal_consistency_score,
        outlier_frame_indices=fusion_res.outlier_frame_indices,
        result_status=result_status,
        condition=condition,
        overall_confidence=overall_conf,
    )
