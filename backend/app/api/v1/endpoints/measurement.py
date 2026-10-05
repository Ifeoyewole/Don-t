from datetime import datetime, timezone
import logging
import time
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

from backend.app.config import get_settings
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
from backend.app.schemas.calibration import CalibrationProfile
from backend.app.schemas.domain import (
    CalibrationSource,
    DomainStatus,
    JointConditionClass,
    JointType,
    MeasurementResultStatus,
    ToleranceStatus,
)
from backend.app.schemas.measurement import (
    ClassifierEvidence,
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
    pipe_diameter_mm: Optional[float] = Form(
        None,
        description="Known reference pipe diameter in millimeters for pixel scaling. If null, physical mm measurements are withheld.",
        gt=0.0,
        le=5000.0,
    ),
    calibration_reference_id: Optional[str] = Form(
        None,
        description="Unique ID for project calibration profile reference.",
    ),
    project_id: Optional[str] = Form(
        None,
        description="Project identifier for reusable calibration.",
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
    include_model_comparison: bool = Form(
        False,
        description="Whether to run offline native Model B for experimental research/comparison (defaults to False for beta).",
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
        settings = get_settings()

        # Build reusable project calibration profile if any parameters provided
        cal_profile: Optional[CalibrationProfile] = None
        if calibration_reference_id or calibration_source or pipe_diameter_mm is not None:
            cal_profile = CalibrationProfile(
                calibration_reference_id=calibration_reference_id or f"CAL-{int(time.time())}",
                project_id=project_id or "default-project",
                source=calibration_source or CalibrationSource.PROJECT_METADATA,
                pipe_diameter_mm=pipe_diameter_mm,
                camera_id=camera_id,
                verified=calibration_verified,
                verified_at=datetime.now(timezone.utc).isoformat() if calibration_verified else None,
                notes=None,
            )

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

        # Domain gating: block unrelated scenes, non-joint pipe interiors, degraded images, or when Vertex is unavailable
        if not semantic_res.processing_allowed:
            if semantic_res.domain_status == DomainStatus.UNRELATED_IMAGE:
                q_score = 0.0
                reason = "UNRELATED_IMAGE: Image is not a pipe interior or sewer scene. Physical measurement stopped."
                auth_reason = "Unrelated image rejected by semantic gatekeeper."
            elif semantic_res.domain_status == DomainStatus.PIPE_INTERIOR_NO_JOINT:
                q_score = 0.70
                reason = "PIPE_INTERIOR_NO_JOINT: Pipe interior detected but no pipe joint is visible for measurement."
                auth_reason = "Pipe interior section without joint; joint measurement skipped."
            elif semantic_res.domain_status == DomainStatus.LOW_QUALITY_IMAGE:
                q_score = 0.20
                reason = "LOW_QUALITY_IMAGE: Image quality degraded by blur, lighting, or water obstruction; retake required."
                auth_reason = "Low quality image requires manual inspector review or re-capture."
            elif semantic_res.domain_status == DomainStatus.DOMAIN_VALIDATION_UNAVAILABLE:
                q_score = 0.0
                reason = semantic_res.user_message or "AI image validation is temporarily unavailable. Retry validation."
                auth_reason = "AI image validation unavailable; fail-closed enforcement active."
            else:
                q_score = 0.0
                reason = semantic_res.user_message or f"Semantic gate blocked processing: {semantic_res.domain_status.value}"
                auth_reason = "Semantic domain gatekeeper prevented measurement execution."

            confidence_bd = confidence_engine.fuse_measurement_confidence(
                quality_score=q_score,
                segmentation_score=0.0,
                geometry_score=0.0,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=None,
                pixels_per_mm=None,
                mean_gap_mm=None,
                min_gap_mm=None,
                max_gap_mm=None,
                mean_gap_px=None,
                min_gap_px=None,
                max_gap_px=None,
                candidate_gap_mm=None,
                overall_status=ToleranceStatus.REVIEW,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason=reason,
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                calibration_profile=cal_profile,
                geometry_tier="REJECTED_UNRELIABLE",
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.REVIEW,
                authoritative_reason=auth_reason,
            )

        # Step 1: Pre-measurement Image Quality Gate (OpenCV local)
        quality_res = validate_image_quality(image_bgr)
        if not quality_res.usable:
            confidence_bd = confidence_engine.fuse_measurement_confidence(
                quality_score=quality_res.quality_score,
                segmentation_score=0.0,
                geometry_score=0.0,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=None,
                pixels_per_mm=None,
                mean_gap_mm=None,
                min_gap_mm=None,
                max_gap_mm=None,
                mean_gap_px=None,
                min_gap_px=None,
                max_gap_px=None,
                candidate_gap_mm=None,
                overall_status=ToleranceStatus.REVIEW,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason=quality_res.rejection_reason or "Image quality unsuitable for measurement.",
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                calibration_profile=cal_profile,
                geometry_tier="REJECTED_UNRELIABLE",
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.REVIEW,
                authoritative_reason="Image failed local OpenCV optical quality validation.",
            )

        # Step 2: Camera Calibration & Lens Distortion Rectification
        rectified_bgr = camera_calibrator.undistort_image(image_bgr, camera_id)

        # Step 3: AI Joint Segmentation (Model A) - strictly an experimental localization helper
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

        # Step 5: Mask-Constrained OpenCV Geometry Engine (Zero Guessing with Evidence Tiers)
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
            confidence_bd = confidence_engine.fuse_measurement_confidence(
                quality_score=quality_res.quality_score,
                segmentation_score=seg_res.confidence if seg_res.detected else 0.30,
                geometry_score=geometry_confidence,
            )
            return MeasurementResponse(
                joint_type=joint_type,
                pipe_diameter_mm=None,
                pixels_per_mm=None,
                mean_gap_mm=None,
                min_gap_mm=None,
                max_gap_mm=None,
                mean_gap_px=None,
                min_gap_px=None,
                max_gap_px=None,
                candidate_gap_mm=None,
                overall_status=ToleranceStatus.REVIEW,
                result_status=MeasurementResultStatus.REJECTED_UNRELIABLE,
                condition=None,
                confidence_breakdown=confidence_bd,
                rejection_reason=f"joint_geometry_not_reliable: {str(val_err)}",
                overlay_hints=OverlayHints(),
                debug_info=None,
                semantic_gate=semantic_res,
                calibration_source=calibration_source,
                calibration_profile=cal_profile,
                geometry_tier="REJECTED_UNRELIABLE",
                physical_measurement_available=False,
                authoritative_gap_mm=None,
                engineering_result=ToleranceStatus.REVIEW,
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
            and pipe_diameter_mm is not None
            and pipe_diameter_mm > 0.0
        )

        if not is_calibrated:
            # When uncalibrated: physical_measurement_available = False, authoritative_gap_mm = None.
            # Physical mm values MUST NOT be emitted.
            if response.mean_gap_mm is not None:
                response.candidate_gap_mm = response.mean_gap_mm
            response.mean_gap_mm = None
            response.min_gap_mm = None
            response.max_gap_mm = None
            response.pixels_per_mm = None
            response.pipe_diameter_mm = None
            response.physical_measurement_available = False
            response.authoritative_gap_mm = None
            response.overall_status = ToleranceStatus.CALIBRATION_REQUIRED
            response.engineering_result = ToleranceStatus.REVIEW
            response.authoritative_reason = (
                "CALIBRATION_REQUIRED: Calibration is unverified or absent; authoritative millimeters withheld."
            )
            response.rejection_reason = (
                "CALIBRATION_REQUIRED: Unverified diameter cannot produce authoritative millimeters."
            )
        else:
            # Calibrated. Enforce evidence tiers and acceptance:
            if response.geometry_tier == "PARTIAL_REVIEW_GEOMETRY":
                if response.mean_gap_mm is not None:
                    response.candidate_gap_mm = response.mean_gap_mm
                response.mean_gap_mm = None
                response.min_gap_mm = None
                response.max_gap_mm = None
                response.physical_measurement_available = False
                response.authoritative_gap_mm = None
                response.overall_status = ToleranceStatus.REVIEW
                response.engineering_result = ToleranceStatus.REVIEW
                response.authoritative_reason = (
                    "PARTIAL_REVIEW_GEOMETRY: Geometry meets partial review threshold but requires inspector review; authoritative millimeters withheld."
                )
            elif response.result_status == MeasurementResultStatus.REJECTED_UNRELIABLE:
                if response.mean_gap_mm is not None:
                    response.candidate_gap_mm = response.mean_gap_mm
                response.mean_gap_mm = None
                response.min_gap_mm = None
                response.max_gap_mm = None
                response.physical_measurement_available = False
                response.authoritative_gap_mm = None
                response.engineering_result = ToleranceStatus.REVIEW
                response.authoritative_reason = (
                    "GEOMETRY_REJECTED: Measurement geometry rejected as unreliable; authoritative millimeters withheld."
                )
            else:
                response.physical_measurement_available = True
                response.authoritative_gap_mm = response.mean_gap_mm
                response.engineering_result = response.overall_status
                response.authoritative_reason = (
                    f"Verified physical calibration ({calibration_source.value}): "
                    f"measured gap {response.mean_gap_mm:.2f}mm matches tolerance criteria."
                )

        # Step 7: Primary Defect Condition Classification (WRc InceptionResNetV2)
        # WRc is the ONE live defect/condition classifier for beta.
        # Native Model B (JointClassifier) is NOT executed during normal live inference.
        primary_classifier = getattr(settings, "PRIMARY_CONDITION_CLASSIFIER", "wrc")

        if primary_classifier == "wrc":
            wrc_classifier = get_wrc_classifier()
            wrc_res = wrc_classifier.classify(image_bgr=rectified_bgr)
            response.external_classifier = wrc_res

            condition = JointConditionClass.CLASSIFICATION_UNAVAILABLE
            mapping_status = "UNAVAILABLE"
            classification_status = "CLASSIFICATION_UNAVAILABLE"

            low_conf_threshold = getattr(settings, "WRC_LOW_CONFIDENCE_THRESHOLD", 0.40)

            if wrc_res.status == "SUCCESS":
                conf = float(wrc_res.confidence or 0.0)
                if conf >= low_conf_threshold:
                    raw_mapping = wrc_res.jointinspect_mapping
                    if raw_mapping == "DISPLACED_JOINT":
                        condition = JointConditionClass.DISPLACED_JOINT
                        mapping_status = "MAPPED"
                        classification_status = "SUCCESS"
                    elif raw_mapping == "DAMAGED_JOINT":
                        condition = JointConditionClass.DAMAGED_JOINT
                        mapping_status = "MAPPED"
                        classification_status = "SUCCESS"
                    elif raw_mapping == "DEPOSITS_OBSTACLES":
                        condition = JointConditionClass.DEPOSITS_OBSTACLES
                        mapping_status = "MAPPED"
                        classification_status = "SUCCESS"
                    elif raw_mapping in ("NORMAL_JOINT", "INTACT_JOINT"):
                        condition = JointConditionClass.NORMAL_JOINT
                        mapping_status = "MAPPED"
                        classification_status = "SUCCESS"
                    else:
                        # Ambiguous / unmapped WRc class (Connection, Junction, Line of Sewer, Water)
                        condition = JointConditionClass.CLASSIFICATION_UNAVAILABLE
                        mapping_status = "UNMAPPED_OR_AMBIGUOUS"
                        classification_status = "REVIEW_REQUIRED"
                else:
                    condition = JointConditionClass.CLASSIFICATION_UNAVAILABLE
                    mapping_status = "LOW_CONFIDENCE"
                    classification_status = "LOW_CONFIDENCE_CLASSIFICATION"
            else:
                condition = JointConditionClass.CLASSIFICATION_UNAVAILABLE
                mapping_status = "UNAVAILABLE"
                classification_status = "CLASSIFICATION_UNAVAILABLE"

            response.condition = condition

            classifier_evidence = ClassifierEvidence(
                classifier="WRc InceptionResNetV2",
                model_id=wrc_res.model_id or "wrc-inceptionresnetv2-baseline-v1",
                raw_prediction=wrc_res.raw_class_name or "Unknown",
                raw_code=wrc_res.raw_class_code or "N/A",
                confidence=float(wrc_res.confidence or 0.0),
                mapped_condition=condition.value if condition else None,
                mapping_status=mapping_status,
                top_k=wrc_res.top_k or [],
                classification_status=classification_status,
            )
            response.classifier_evidence = classifier_evidence

            # Live UI shows NO native-vs-WRc disagreement.
            # Model comparison is populated ONLY in explicit experimental mode.
            if include_model_comparison:
                try:
                    classifier = JointClassifier()
                    max_tol = tolerance_spec.max_gap_mm if tolerance_spec else 15.0
                    cond_res = classifier.classify_joint(
                        image_bgr=rectified_bgr,
                        roi_bbox=seg_res.bbox if seg_res.detected else None,
                        measured_gap_mm=response.mean_gap_mm,
                        max_allowable_gap_mm=max_tol,
                    )
                    response.model_comparison = compare_models(
                        wrc_result=wrc_res,
                        native_result=cond_res,
                        vertex_observation=semantic_res.observation,
                        segmenter_result=seg_res,
                        vertex_live=(semantic_res.model == "gemini-2.5-flash"),
                    )
                except Exception as comp_err:
                    logger.warning("Experimental model comparison failed: %s", comp_err)
                    response.model_comparison = None
            else:
                response.model_comparison = None
        else:
            # Fallback legacy path if primary classifier is explicitly switched to native
            classifier = JointClassifier()
            max_tol = tolerance_spec.max_gap_mm if tolerance_spec else 15.0
            cond_res = classifier.classify_joint(
                image_bgr=rectified_bgr,
                roi_bbox=seg_res.bbox if seg_res.detected else None,
                measured_gap_mm=response.mean_gap_mm,
                max_allowable_gap_mm=max_tol,
            )
            response.condition = cond_res.condition
            response.model_comparison = None

        # Step 8: Decoupled Multi-Component Confidence Fusion
        # Measurement confidence governs physical measurement acceptance.
        # Classification confidence is derived solely from WRc score.
        seg_score = seg_res.confidence if seg_res.detected else 0.50
        breakdown = confidence_engine.fuse_measurement_confidence(
            quality_score=quality_res.quality_score,
            segmentation_score=seg_score,
            geometry_score=geometry_confidence,
        )
        if response.classifier_evidence:
            breakdown.classification_confidence = response.classifier_evidence.confidence
        response.confidence_breakdown = breakdown

        # Acceptance gating based on measurement confidence and geometry tier
        if response.geometry_tier == "PARTIAL_REVIEW_GEOMETRY":
            response.result_status = MeasurementResultStatus.REVIEW_REQUIRED
        else:
            response.result_status = breakdown.decision if is_calibrated else MeasurementResultStatus.REVIEW_REQUIRED

        # Withhold authoritative mm if rejected
        if response.result_status == MeasurementResultStatus.REJECTED_UNRELIABLE:
            if response.mean_gap_mm is not None:
                response.candidate_gap_mm = response.mean_gap_mm
            response.mean_gap_mm = None
            response.min_gap_mm = None
            response.max_gap_mm = None
            response.physical_measurement_available = False
            response.authoritative_gap_mm = None
            response.engineering_result = ToleranceStatus.REVIEW
            if not response.authoritative_reason or "Verified physical calibration" in response.authoritative_reason:
                response.authoritative_reason = (
                    "REJECTED_UNRELIABLE: Measurement confidence insufficient for authoritative determination."
                )

        if not is_calibrated and not response.rejection_reason:
            response.rejection_reason = "CALIBRATION_REQUIRED: Verification needed for authoritative millimeters."
        elif breakdown.decision != MeasurementResultStatus.ACCEPTED_MEASUREMENT and not response.rejection_reason:
            response.rejection_reason = f"Measurement gated for inspector review (confidence {breakdown.overall_confidence:.2f})."

        # Step 9: Vertex Result Explanation
        # Vertex explains why WRc classified it that way and what geometry shows, without rewriting physical facts
        vertex_obs = semantic_res.observation or "Pipe joint inspection scene validated."
        if response.authoritative_gap_mm is not None:
            geom_desc = f"Measured gap is {response.authoritative_gap_mm:.2f} mm ({response.engineering_result.value})"
        elif response.candidate_gap_mm is not None:
            geom_desc = f"Candidate gap is {response.candidate_gap_mm:.2f} mm (diagnostic only; partial geometry review required)"
        elif response.mean_gap_px is not None:
            geom_desc = f"Mean gap is {response.mean_gap_px:.1f} px (physical mm withheld; calibration unverified)"
        else:
            geom_desc = "No valid geometry resolved"

        wrc_pred = response.classifier_evidence.raw_prediction if response.classifier_evidence else "N/A"
        wrc_code = response.classifier_evidence.raw_code if response.classifier_evidence else "N/A"
        wrc_conf = (response.classifier_evidence.confidence * 100) if response.classifier_evidence else 0.0
        wrc_desc = f"WRc InceptionResNetV2 condition: {wrc_pred} ({wrc_code}) at {wrc_conf:.1f}% confidence."
        response.ai_explanation = f"{vertex_obs} {geom_desc}. {wrc_desc}"

        # Final attach of semantic, calibration, and profile metadata
        response.semantic_gate = semantic_res
        response.calibration_source = calibration_source
        response.calibration_profile = cal_profile

        if not is_calibrated or response.result_status == MeasurementResultStatus.REJECTED_UNRELIABLE or response.geometry_tier == "PARTIAL_REVIEW_GEOMETRY":
            response.physical_measurement_available = False
            response.authoritative_gap_mm = None
            response.engineering_result = ToleranceStatus.REVIEW

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
