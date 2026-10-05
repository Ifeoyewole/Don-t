"""Automated computer vision measurement API endpoints with integrated AI/CV fusion."""

import logging
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

from backend.app.core.cv.ai.image_quality import validate_image_quality
from backend.app.core.cv.ai.joint_classifier import JointClassifier
from backend.app.core.cv.ai.joint_segmenter import JointSegmenter
from backend.app.core.cv.ai.vertex_semantic_gate import get_vertex_semantic_gate
from backend.app.core.cv.ai.wrc_inception_classifier import (
    compare_models,
    get_wrc_classifier,
)
from backend.app.core.cv.calibration import camera_calibrator
from backend.app.core.cv.circular_detector import measure_circular_gap
from backend.app.core.cv.confidence import confidence_engine
from backend.app.core.cv.seam_detector import measure_seam_gap
from backend.app.schemas.domain import (
    CalibrationSource,
    DomainStatus,
    JointConditionClass,
    JointType,
    MeasurementResultStatus,
    ToleranceStatus,
)
from backend.app.schemas.measurement import (
    MeasurementResponse,
    OverlayHints,
    ToleranceSpec,
)
from backend.app.utils.image_io import decode_image_bytes

router = APIRouter()


@router.post(
    "/measure",
    response_model=MeasurementResponse,
    summary="Compute Calibrated AI/CV Sub-Pixel Gap Measurements",
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
        le=5000.0,
    ),
    camera_id: Optional[str] = Form(
        None,
        description="Optional camera profile ID (e.g. 'CCTV-STANDARD-01', 'GOPRO-MAX-REFRAMED') for lens un-distortion.",
    ),
    operator_context: Optional[str] = Form(
        None,
        description="Optional operator context, notes, or prompt for semantic focus.",
    ),
    calibration_source: Optional[CalibrationSource] = Form(
        None,
        description="Provenance of calibration diameter (PROJECT_METADATA, MANHOLE_METADATA, PHYSICAL_REFERENCE, CAMERA_CALIBRATION, TEST_RIG).",
    ),
    calibration_verified: bool = Form(
        False,
        description="Whether the calibration source has been verified by engineering protocol.",
    ),
    nominal_gap_mm: Optional[float] = Form(
        None,
        description="Target nominal gap width in millimeters.",
        gt=0.0,
        le=500.0,
    ),
    min_gap_mm: Optional[float] = Form(
        None,
        description="Minimum acceptable gap in millimeters.",
        gt=0.0,
        le=500.0,
    ),
    max_gap_mm: Optional[float] = Form(
        None,
        description="Maximum acceptable gap in millimeters.",
        gt=0.0,
        le=500.0,
    ),
    warning_margin_mm: Optional[float] = Form(
        None,
        description="Warning tolerance margin buffer in millimeters.",
        ge=0.0,
        le=100.0,
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
    min_segmentation_confidence: Optional[float] = Form(
        0.40,
        description="Configurable baseline confidence threshold for AI joint segmenter.",
        ge=0.20,
        le=0.95,
    ),
) -> MeasurementResponse:
    """Execute end-to-end AI/CV pipe joint measurement pipeline with strict authority boundaries:

    0. Vertex AI Semantic Domain Gate & Operator Context Isolation.
    1. Pre-measurement Image Quality Gate (OpenCV sharpness/exposure/glare).
    2. Camera Calibration & Lens Distortion Rectification.
    3. AI Joint Segmenter (Model A) -> Locate joint ROI and binary mask.
    4. OpenCV Geometry Engine (Zero Guessing) -> Radial ray / seam trace.
    5. Calibration Authority Check -> Disallow unverified mm claims.
    6. AI Condition Classifier (Model B) -> Tolerance-primary structural diagnosis.
    7. External WRc InceptionResNetV2 Baseline Classifier (Advisory Only).
    8. Multi-System Disagreement Tracking.
    9. Authoritative Engineering Rules aggregation.
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

        # Step 0: Vertex AI Semantic Domain Gate & Multi-Modal Context Understanding
        vertex_gate = get_vertex_semantic_gate()
        semantic_res = vertex_gate.evaluate(image_bgr, operator_context=operator_context)

        # Domain gating: block unrelated scenes, non-joint pipe interiors, or degraded images
        if semantic_res.domain_status == DomainStatus.UNRELATED_IMAGE:
            confidence_bd = confidence_engine.fuse_confidence(
                quality_score=0.0,
                segmentation_score=0.0,
                condition_score=0.0,
                geometry_score=0.0,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=pipe_diameter_mm,
                pixels_per_mm=1.0,
                mean_gap_mm=0.0,
                min_gap_mm=0.0,
                max_gap_mm=0.0,
                overall_status=ToleranceStatus.FAIL,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason="UNRELATED_IMAGE: Image is not a pipe interior or sewer scene. Physical measurement stopped.",
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.FAIL,
                authoritative_reason="Unrelated image rejected by semantic gatekeeper.",
            )

        if semantic_res.domain_status == DomainStatus.PIPE_INTERIOR_NO_JOINT:
            confidence_bd = confidence_engine.fuse_confidence(
                quality_score=0.70,
                segmentation_score=0.0,
                condition_score=0.0,
                geometry_score=0.0,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=pipe_diameter_mm,
                pixels_per_mm=1.0,
                mean_gap_mm=0.0,
                min_gap_mm=0.0,
                max_gap_mm=0.0,
                overall_status=ToleranceStatus.REVIEW,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason="PIPE_INTERIOR_NO_JOINT: Pipe interior detected but no pipe joint is visible for measurement.",
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.REVIEW,
                authoritative_reason="Pipe interior section without joint; joint measurement skipped.",
            )

        if semantic_res.domain_status == DomainStatus.LOW_QUALITY_IMAGE:
            confidence_bd = confidence_engine.fuse_confidence(
                quality_score=0.20,
                segmentation_score=0.0,
                condition_score=0.0,
                geometry_score=0.0,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=pipe_diameter_mm,
                pixels_per_mm=1.0,
                mean_gap_mm=0.0,
                min_gap_mm=0.0,
                max_gap_mm=0.0,
                overall_status=ToleranceStatus.REVIEW,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason="LOW_QUALITY_IMAGE: Image quality degraded by blur, lighting, or water obstruction; retake required.",
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.REVIEW,
                authoritative_reason="Low quality image requires manual inspector review or re-capture.",
            )

        # Step 1: Pre-measurement Image Quality Gate (OpenCV local)
        quality_res = validate_image_quality(image_bgr)
        if not quality_res.usable:
            confidence_bd = confidence_engine.fuse_confidence(
                quality_score=quality_res.quality_score,
                segmentation_score=0.0,
                condition_score=0.0,
                geometry_score=0.0,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=pipe_diameter_mm,
                pixels_per_mm=1.0,
                mean_gap_mm=0.0,
                min_gap_mm=0.0,
                max_gap_mm=0.0,
                overall_status=ToleranceStatus.FAIL,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason=quality_res.rejection_reason or "Image quality unsuitable for measurement.",
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.FAIL,
                authoritative_reason="Image failed local OpenCV optical quality validation.",
            )

        # Step 2: Camera Calibration & Lens Distortion Rectification
        rectified_bgr = camera_calibrator.undistort_image(image_bgr, camera_id)

        # Step 3: AI Joint Segmentation (Model A)
        segmenter = JointSegmenter(min_confidence=min_segmentation_confidence or 0.40)
        seg_res = segmenter.segment_joint(rectified_bgr)

        # Step 4: Build custom ToleranceSpec if bounds provided
        tolerance_spec: Optional[ToleranceSpec] = None
        if min_gap_mm is not None or max_gap_mm is not None or nominal_gap_mm is not None:
            tolerance_spec = ToleranceSpec(
                nominal_gap_mm=nominal_gap_mm if nominal_gap_mm is not None else 10.0,
                min_gap_mm=min_gap_mm if min_gap_mm is not None else 3.0,
                max_gap_mm=max_gap_mm if max_gap_mm is not None else 15.0,
                warning_margin_mm=warning_margin_mm if warning_margin_mm is not None else 2.0,
            )

        # Step 5: Mask-Constrained OpenCV Geometry Engine (Zero Guessing)
        try:
            if joint_type == JointType.CIRCULAR_OPENING:
                rays = num_samples if num_samples is not None else 72
                response = measure_circular_gap(
                    image_bgr=rectified_bgr,
                    pipe_diameter_mm=pipe_diameter_mm,
                    tolerance_spec=tolerance_spec,
                    num_rays=rays,
                    return_debug_image=return_debug_image,
                    joint_mask=seg_res.mask if seg_res.detected else None,
                    roi_bbox=seg_res.bbox if seg_res.detected else None,
                )
            else:
                scanlines = num_samples if num_samples is not None else 40
                response = measure_seam_gap(
                    image_bgr=rectified_bgr,
                    joint_type=joint_type,
                    pipe_diameter_mm=pipe_diameter_mm,
                    tolerance_spec=tolerance_spec,
                    num_scanlines=scanlines,
                    return_debug_image=return_debug_image,
                    joint_mask=seg_res.mask if seg_res.detected else None,
                    roi_bbox=seg_res.bbox if seg_res.detected else None,
                )
            geometry_success = True
            geometry_confidence = 0.92 if response.overall_status != ToleranceStatus.FAIL else 0.70
        except ValueError as val_err:
            geometry_success = False
            geometry_confidence = 0.20
            confidence_bd = confidence_engine.fuse_confidence(
                quality_score=quality_res.quality_score,
                segmentation_score=seg_res.confidence if seg_res.detected else 0.30,
                condition_score=0.50,
                geometry_score=geometry_confidence,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=pipe_diameter_mm,
                pixels_per_mm=1.0,
                mean_gap_mm=0.0,
                min_gap_mm=0.0,
                max_gap_mm=0.0,
                overall_status=ToleranceStatus.FAIL,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason=f"joint_geometry_not_reliable: {str(val_err)}",
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.FAIL,
                authoritative_reason=f"Zero-guessing geometry rejection: {str(val_err)}",
            )

        # Step 6: Calibration Authority Validation
        # Client parameter pipe_diameter_mm does NOT automatically become verified calibration.
        # Calibration must retain provenance from an approved verified source:
        # PROJECT_METADATA, MANHOLE_METADATA, PHYSICAL_REFERENCE, CAMERA_CALIBRATION, TEST_RIG.
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
        )

        if is_calibrated:
            physical_measurement_available = True
            authoritative_gap_mm = response.mean_gap_mm
            eng_result = response.overall_status
            eng_reason = f"Verified physical calibration ({calibration_source.value}): measured gap {response.mean_gap_mm:.2f}mm matches tolerance criteria."
        else:
            physical_measurement_available = False
            authoritative_gap_mm = None
            eng_result = ToleranceStatus.REVIEW
            eng_reason = "CALIBRATION_REQUIRED: Calibration is unverified or absent; authoritative millimeters withheld."
            response.rejection_reason = "CALIBRATION_REQUIRED: Unverified diameter cannot produce authoritative millimeters."

        # Step 7: AI Joint Condition Classifier (Model B) with Tolerance-Primary Rule
        classifier = JointClassifier()
        max_tol = tolerance_spec.max_gap_mm if tolerance_spec else 15.0
        cond_res = classifier.classify_joint(
            image_bgr=rectified_bgr,
            roi_bbox=seg_res.bbox if seg_res.detected else None,
            measured_gap_mm=response.mean_gap_mm,
            max_allowable_gap_mm=max_tol,
        )

        # Step 8: External WRc InceptionResNetV2 Sewer Baseline Classifier (Advisory Baseline)
        wrc_classifier = get_wrc_classifier()
        wrc_res = wrc_classifier.classify(image_bgr=rectified_bgr)
        response.external_classifier = wrc_res

        # Step 9: Beta Multi-System Disagreement Tracking
        response.model_comparison = compare_models(
            wrc_result=wrc_res,
            native_result=cond_res,
            vertex_observation=semantic_res.observation,
        )

        # Step 10: Calibrated Multi-Component Confidence Fusion
        seg_score = seg_res.confidence if seg_res.detected else 0.50
        breakdown = confidence_engine.fuse_confidence(
            quality_score=quality_res.quality_score,
            segmentation_score=seg_score,
            condition_score=cond_res.confidence,
            geometry_score=geometry_confidence,
        )

        response.condition = cond_res.condition
        response.confidence_breakdown = breakdown
        response.result_status = breakdown.decision if is_calibrated else MeasurementResultStatus.REVIEW_REQUIRED
        if not is_calibrated and not response.rejection_reason:
            response.rejection_reason = "CALIBRATION_REQUIRED: Verification needed for authoritative millimeters."
        elif breakdown.decision != MeasurementResultStatus.ACCEPTED_MEASUREMENT and not response.rejection_reason:
            response.rejection_reason = f"Measurement gated for inspector review (confidence {breakdown.overall_confidence:.2f})."

        # Attach semantic and calibration authority metadata
        response.semantic_gate = semantic_res
        response.calibration_source = calibration_source
        response.physical_measurement_available = physical_measurement_available
        response.authoritative_gap_mm = authoritative_gap_mm
        response.engineering_result = eng_result
        response.authoritative_reason = eng_reason

        return response

    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Internal measurement pipeline failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Computer vision measurement processing encountered an internal error. Please check image and retry.",
        )
