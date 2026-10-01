"""Photo quality validation endpoint."""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from backend.app.core.cv.preprocessor import validate_photo_quality
from backend.app.schemas.validation import PhotoQualityResult
from backend.app.utils.image_io import decode_image_bytes

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
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluating photo quality: {str(exc)}",
        )
