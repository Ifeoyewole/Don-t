"""Advisory preflight image-context suggestions; cannot issue engineering authority."""

import asyncio
import logging
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.core.cv.ai.image_quality import validate_image_quality
from backend.app.core.cv.ai.vertex_semantic_gate import get_vertex_semantic_gate
from backend.app.schemas.domain import DomainStatus, JointType
from backend.app.utils.image_io import decode_image_bytes

logger = logging.getLogger(__name__)
router = APIRouter()


class CalibrationSuggestion(BaseModel):
    """Only project/manhole metadata may prefill nominal diameter; never image inference."""

    pipe_diameter_mm: Optional[float] = None
    source: Optional[str] = None
    calibration_reference_id: None = None
    verified: bool = False
    authority: str = "UNVERIFIED_METADATA"


class ContextSuggestionsResponse(BaseModel):
    domain_status: DomainStatus
    processing_allowed: bool
    model: str
    image_quality_usable: bool
    suggested_joint_type: Optional[JointType] = None
    suggested_inspection_context: Optional[str] = None
    possible_gap_visible: Optional[bool] = None
    calibration: CalibrationSuggestion = Field(default_factory=CalibrationSuggestion)
    review_required: bool = True
    reason: str


@router.post(
    "/context-suggestions",
    response_model=ContextSuggestionsResponse,
    summary="Suggest visual inspection context without claiming calibration or defect confirmation",
)
async def suggest_inspection_context(
    file: UploadFile = File(...),
    metadata_pipe_diameter_mm: Optional[float] = Form(None, gt=0.0, le=5000.0),
    metadata_source: Literal["PROJECT_METADATA", "MANHOLE_METADATA"] = Form("PROJECT_METADATA"),
) -> ContextSuggestionsResponse:
    """Return inspector-reviewable image hints and independently sourced project metadata.

    This endpoint must NOT create a verified calibration reference, approve a
    defect, produce physical measurements or change an engineering result.
    """
    calibration = CalibrationSuggestion(
        pipe_diameter_mm=metadata_pipe_diameter_mm,
        source=metadata_source if metadata_pipe_diameter_mm is not None else None,
    )

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image payload.")
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image exceeds 15 MB limit.")

        image_bgr = decode_image_bytes(content)
        quality = validate_image_quality(image_bgr)
        if not quality.usable:
            return ContextSuggestionsResponse(
                domain_status=DomainStatus.LOW_QUALITY_IMAGE,
                processing_allowed=False,
                model="not_called",
                image_quality_usable=False,
                calibration=calibration,
                reason=quality.rejection_reason or "Image quality insufficient for suggestions.",
            )

        semantic = await asyncio.to_thread(get_vertex_semantic_gate().evaluate, image_bgr)
        allowed = semantic.processing_allowed and semantic.domain_status == DomainStatus.PIPE_JOINT_INSPECTION
        return ContextSuggestionsResponse(
            domain_status=semantic.domain_status,
            processing_allowed=allowed,
            model=semantic.model,
            image_quality_usable=True,
            suggested_joint_type=semantic.suggested_joint_type if allowed else None,
            suggested_inspection_context=semantic.suggested_inspection_context if allowed else None,
            possible_gap_visible=semantic.possible_gap_visible if allowed else None,
            calibration=calibration,
            reason=(
                "AI suggestions are advisory. An inspector must confirm geometry; "
                "only server-verified calibration can authorize millimetres."
                if allowed
                else semantic.user_message
            ),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        logger.exception("Inspection context suggestions failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inspection context suggestions unavailable; continue with manual inspection inputs.",
        )
