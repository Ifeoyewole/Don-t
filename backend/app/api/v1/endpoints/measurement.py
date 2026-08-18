"""Automated computer vision measurement API endpoints."""

from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from backend.app.core.cv.circular_detector import measure_circular_gap
from backend.app.core.cv.seam_detector import measure_seam_gap
from backend.app.schemas.domain import JointType
from backend.app.schemas.measurement import MeasurementResponse, ToleranceSpec
from backend.app.utils.image_io import decode_image_bytes

router = APIRouter()


@router.post(
    "/measure",
    response_model=MeasurementResponse,
    summary="Compute Sub-Pixel Gap Measurements",
)
async def measure_joint_gap(
    file: UploadFile = File(..., description="Uploaded inspection photo file (JPEG/PNG/WebP)."),
    joint_type: JointType = Form(
        JointType.CIRCULAR_OPENING,
        description="Joint geometry type: CIRCULAR_OPENING, HORIZONTAL_SEAM, or VERTICAL_SEAM.",
    ),
    pipe_diameter_mm: float = Form(
        100.0,
        description="Known reference pipe diameter in millimeters for pixel scaling.",
        gt=0.0,
    ),
    nominal_gap_mm: Optional[float] = Form(
        None,
        description="Target nominal gap width in millimeters.",
        gt=0.0,
    ),
    min_gap_mm: Optional[float] = Form(
        None,
        description="Minimum acceptable gap in millimeters.",
        gt=0.0,
    ),
    max_gap_mm: Optional[float] = Form(
        None,
        description="Maximum acceptable gap in millimeters.",
        gt=0.0,
    ),
    warning_margin_mm: Optional[float] = Form(
        None,
        description="Warning tolerance margin buffer in millimeters.",
        ge=0.0,
    ),
    return_debug_image: bool = Form(
        True,
        description="Whether to generate and return base64-encoded annotated visualization.",
    ),
    num_samples: Optional[int] = Form(
        None,
        description="Number of radial rays or seam scanlines to profile.",
        ge=8,
        le=360,
    ),
) -> MeasurementResponse:
    """Execute high-precision sub-pixel edge detection and radial/scanline gap measurement.

    Supports:
    - CIRCULAR_OPENING: Vectorized polar unwrap & radial ray profiling.
    - HORIZONTAL_SEAM / VERTICAL_SEAM: Directional Sobel filtering & scanline edge peak profiling.
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file payload is empty.",
            )

        image_bgr = decode_image_bytes(content)

        # Build custom ToleranceSpec if user provided bounds
        tolerance_spec: Optional[ToleranceSpec] = None
        if min_gap_mm is not None or max_gap_mm is not None or nominal_gap_mm is not None:
            tolerance_spec = ToleranceSpec(
                nominal_gap_mm=nominal_gap_mm if nominal_gap_mm is not None else 10.0,
                min_gap_mm=min_gap_mm if min_gap_mm is not None else 3.0,
                max_gap_mm=max_gap_mm if max_gap_mm is not None else 15.0,
                warning_margin_mm=warning_margin_mm if warning_margin_mm is not None else 2.0,
            )

        if joint_type == JointType.CIRCULAR_OPENING:
            rays = num_samples if num_samples is not None else 72
            response = measure_circular_gap(
                image_bgr=image_bgr,
                pipe_diameter_mm=pipe_diameter_mm,
                tolerance_spec=tolerance_spec,
                num_rays=rays,
                return_debug_image=return_debug_image,
            )
        else:
            scanlines = num_samples if num_samples is not None else 40
            response = measure_seam_gap(
                image_bgr=image_bgr,
                joint_type=joint_type,
                pipe_diameter_mm=pipe_diameter_mm,
                tolerance_spec=tolerance_spec,
                num_scanlines=scanlines,
                return_debug_image=return_debug_image,
            )

        return response

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Computer vision measurement failed: {str(exc)}",
        )
