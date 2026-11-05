"""Photo quality validation endpoint."""

import asyncio
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from backend.app.core.cv.preprocessor import validate_photo_quality
from backend.app.core.cv.ai.vertex_semantic_gate import get_vertex_semantic_gate
from backend.app.schemas.validation import AdvisoryCalibrationMetadata, PhotoQualityResult, InspectionContextSuggestions
from backend.app.utils.image_io import decode_image_bytes
from backend.app.schemas.domain import CalibrationSource, DomainStatus

router = APIRouter()


@router.post(
    "/validate-photo",
    response_model=PhotoQualityResult,
    summary="Validate Image Quality for CV Measurement",
)
async def validate_photo(
    file: UploadFile = File(..., description="Uploaded inspection photo file (JPEG/PNG/WebP)"),
    blur_threshold: float = Query(
        100.0,
        description="Minimum acceptable sharpness score via Laplacian variance.",
        ge=10.0,
        le=1000.0,
    ),
    min_brightness: float = Query(
        45.0,
        description="Minimum average luminance threshold (0-255).",
        ge=0.0,
        le=255.0,
    ),
    max_brightness: float = Query(
        215.0,
        description="Maximum average luminance threshold (0-255).",
        ge=0.0,
        le=255.0,
    ),
) -> PhotoQualityResult:
    """Pre-flight check assessing image sharpness, exposure conditions, and specular reflections before processing.

    Returns quality metrics and real-time capture recommendations for the inspector.
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file payload is empty.",
            )

        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded image payload exceeds 15 MB limit.",
            )

        image_bgr = decode_image_bytes(content)
        result = validate_photo_quality(
            image_bgr,
            blur_threshold=blur_threshold,
            min_brightness=min_brightness,
            max_brightness=max_brightness,
        )
        return result

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error evaluating photo quality due to internal processing error.",
        )


@router.post(
    "/context-suggestions",
    response_model=InspectionContextSuggestions,
    summary="Generate optional editable inspection context from a photo",
)
async def suggest_inspection_context(
    file: UploadFile = File(..., description="Inspection image (JPEG/PNG/WebP)."),
    metadata_pipe_diameter_mm: Optional[float] = Form(default=None, gt=0.0, le=5000.0),
    metadata_source: Optional[CalibrationSource] = Form(default=None),
) -> InspectionContextSuggestions:
    """Reuse the production Gemini semantic gate without assuming calibration.

    The image itself is the only contextual input; no prior user photos, customer
    histories, or fabricated dimensions are supplied to Gemini. Supplied
    manhole metadata is copied only as unverified form hints and is NEVER fed
    into the image model. Rejected semantic validation yields empty suggestions.
    """
    try:
        if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPEG, PNG, and WEBP inspection photos are accepted.",
            )
        content = await file.read(15 * 1024 * 1024 + 1)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file payload is empty.",
            )
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded image exceeds 15 MB.",
            )

        image_bgr = decode_image_bytes(content)
        semantic = await asyncio.to_thread(get_vertex_semantic_gate().evaluate, image_bgr)
        allowed = (
            semantic.processing_allowed
            and semantic.domain_status == DomainStatus.PIPE_JOINT_INSPECTION
        )
        return InspectionContextSuggestions(
            calibration=AdvisoryCalibrationMetadata(
                pipe_diameter_mm=metadata_pipe_diameter_mm,
                source=metadata_source,
                verified=False,
                calibration_reference_id=None,
            ),
            model=semantic.model,
            domain_status=semantic.domain_status,
            processing_allowed=allowed,
            suggested_joint_type=semantic.suggested_joint_type if allowed else None,
            suggested_inspection_context=semantic.suggested_inspection_context if allowed else None,
            possible_gap_visible=semantic.possible_gap_visible if allowed else None,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image context suggestions are temporarily unavailable; manual inspection remains available.",
        )
