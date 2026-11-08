"""JointInspect Unified Vision v1: one fail-closed decision from four sources.

This is a *decision contract*, not a merged neural checkpoint. Inspect View
supplies exploratory class evidence; SAM2 supplies promptable masks; OpenCV
supplies candidate pixel geometry; Gemini 3.1 Pro supplies a semantic domain\nassessment. No single source may upgrade another into
a verified defect, a calibrated gap, or an engineering acceptance decision.

Pure Python, independent of Torch/CV and safe to test without model weights.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA_VERSION = "1.0.0"
ENGINE_ID = "jointinspect-unified-vision-v1"
UNVALIDATED_CLASSES = frozenset({
    "OPEN_JOINT", "INFILTRATION", "PROTRUDING_LATERAL",
})
ALLOWED_FUSION_STATUSES = frozenset({
    "MULTI_MODEL_REVIEW", "MULTI_MODEL_RESEARCH_EVIDENCE",
    "SEGMENTATION_ONLY_REVIEW",
})
PIXEL_STATUSES = frozenset({
    "PIXEL_PROFILE_CANDIDATE", "SINGLE_FRAME_RING_CANDIDATE",
})


def _is_probability(value: Any) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value) and 0.0 <= value <= 1.0
    )


def _valid_sha(value: Any) -> bool:
    return (
        isinstance(value, str) and len(value) == 64
        and all(char in "0123456789abcdef" for char in value.lower())
    )


def build_unified_result(
    fusion: Mapping[str, Any],
    *,
    inspect_view_payload: Mapping[str, Any] | None,
    image_sha256: str,
    gemini_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one research advisory for the exact image.

    Input fusion MUST originate from the existing same-frame SAM2/Inspect
    View/OpenCV adapter. A preview payload is accepted for candidates only
    when its SHA and version agree with the fusion report. A model-produced
    class probability is never interpreted as a diagnosis on its own.
    """
    if not _valid_sha(image_sha256):
        raise ValueError("Expected SHA-256 of the exact source image bytes")
    image_sha256 = image_sha256.lower()
    if not isinstance(fusion, Mapping):
        raise TypeError("Fusion report must be a mapping")
    preview = inspect_view_payload if isinstance(inspect_view_payload, Mapping) else {}
    preview_bound = (
        bool(fusion.get("inspect_view_ready") is True)
        and preview.get("model_ready") is True
        and preview.get("research_preview") is True
        and preview.get("image_sha256") == image_sha256
        and isinstance(preview.get("model_version"), str)
        and preview.get("model_version") == fusion.get("inspect_view_version")
    )
    reasons: list[str] = []
    if not preview_bound:
        reasons.append("INSPECT_VIEW_UNAVAILABLE_OR_IMAGE_PROVENANCE_UNVERIFIED")

    # Reuse an existing Vertex AI Gemini 3.1 Pro semantic-gate result; DO NOT
    # issue a second paid provider call here. Only an image-hash-matched,
    # server-created receipt is eligible. Gemini's text is never a command,
    # defect label, calibration source or engineering verdict.
    semantic_status = "NOT_PROVIDED"
    semantic_model = None
    semantic_domain = None
    semantic_geometry_suggestion = None
    if gemini_receipt is not None:
        if (
            not isinstance(gemini_receipt, Mapping)
            or gemini_receipt.get("image_sha256") != image_sha256
            or not isinstance(gemini_receipt.get("semantic_gate"), Mapping)
        ):
            semantic_status = "UNVERIFIED"
            reasons.append("GEMINI_IMAGE_PROVENANCE_MISSING_OR_MISMATCHED")
        else:
            gate = gemini_receipt["semantic_gate"]
            semantic_model = gate.get("model")
            semantic_domain = gate.get("domain_status")
            if semantic_model != "gemini-3.1-pro-preview":
                semantic_status = "UNVERIFIED"
                reasons.append("GEMINI_MODEL_ID_UNVERIFIED")
            elif (
                semantic_domain != "PIPE_JOINT_INSPECTION"
                or gate.get("processing_allowed") is not True
                or gate.get("pipe_visible") is not True
                or gate.get("joint_visible") is not True
                or gate.get("prompt_image_conflict") is not False
                or gate.get("quality") != "OK"
            ):
                semantic_status = "BLOCKED"
                reasons.append("GEMINI_SEMANTIC_DOMAIN_OR_QUALITY_GATE_BLOCKED")
            else:
                semantic_status = "ADVISORY_DOMAIN_ACCEPTED"
                suggestion = gate.get("suggested_joint_type")
                if suggestion in ("VERTICAL_SEAM", "HORIZONTAL_SEAM", "CIRCULAR_OPENING"):
                    semantic_geometry_suggestion = suggestion
                    if suggestion != fusion.get("geometry"):
                        reasons.append("GEMINI_GEOMETRY_SUGGESTION_CONFLICT")

    # If a Gemini receipt is submitted and it fails, expose only a safe
    # review status. The separate legacy backend already blocks non-joint
    # scenes; this contract mirrors that rule without changing production.
    semantic_blocks = gemini_receipt is not None and semantic_status != "ADVISORY_DOMAIN_ACCEPTED"

    # The fusion adapter has already checked the mask's image digest, shape,
    # bbox/pixels, and score. Do not surface a mask from a rejected fusion.
    fused = fusion.get("status") in ALLOWED_FUSION_STATUSES
    mask_accepted = (
        fused and fusion.get("sam2_status") == "MASK_CANDIDATE_RESEARCH"
        and isinstance(fusion.get("mask_bbox"), (tuple, list))
        and len(fusion["mask_bbox"]) == 4
        and _is_probability(fusion.get("mask_quality"))
    )
    if not mask_accepted:
        reasons.append("SAM2_MASK_UNAVAILABLE_OR_NOT_VERIFIED_FOR_SOURCE_IMAGE")

    geometry_status = str(fusion.get("cv_status") or "NOT_EVALUATED")
    px = fusion.get("cv_pixel_candidate")
    pixel_candidate = (
        float(px)
        if mask_accepted and geometry_status in PIXEL_STATUSES
        and isinstance(px, (int, float)) and not isinstance(px, bool)
        and math.isfinite(px) and px > 0
        else None
    )
    if semantic_blocks:
        pixel_candidate = None
    if pixel_candidate is None:
        reasons.append("NO_SUPPORTED_PIXEL_GEOMETRY")

    # Use only preview-gated detections corroborated by the fusion's class
    # status. All other classes, especially our three unsupported targets,
    # remain unvalidated. This is an advisory rank, not a final defect.
    fusion_classes = {
        item["label"]: item for item in fusion.get("inspect_view_advisories", [])
        if isinstance(item, Mapping) and isinstance(item.get("label"), str)
    } if preview_bound else {}
    preview_classes = preview.get("classes") if preview_bound else None
    candidate_rows = []
    normal_detected = False
    if isinstance(preview_classes, Mapping):
        for label, raw in preview_classes.items():
            if not isinstance(label, str) or not isinstance(raw, Mapping):
                continue
            gate = fusion_classes.get(label)
            if (
                label in UNVALIDATED_CLASSES or gate is None
                or gate.get("status") != "EXPLORATORY"
                or raw.get("status") != "EXPLORATORY"
                or raw.get("detected") is not True
                or not _is_probability(raw.get("probability"))
                or not _is_probability(gate.get("probability"))
                or abs(float(raw["probability"]) - float(gate["probability"])) > 1e-6
            ):
                continue
            if label == "NORMAL":
                normal_detected = True
            else:
                candidate_rows.append({
                    "label": label,
                    "probability": round(float(raw["probability"]), 6),
                    "classification_status": "EXPLORATORY",
                })
    if semantic_blocks:
        candidate_rows.clear()
        normal_detected = False
    candidate_rows.sort(key=lambda item: (-item["probability"], item["label"]))
    if len(candidate_rows) > 1:
        reasons.append("MULTIPLE_EXPLORATORY_DEFECT_CANDIDATES")
    if normal_detected and candidate_rows:
        reasons.append("CONFLICTING_NORMAL_AND_DEFECT_ADVISORIES")
    if candidate_rows:
        reasons.append("CLASS_CANDIDATE_REQUIRES_SPECIALIST_VERIFICATION")
    elif not normal_detected:
        reasons.append("NO_SUPPORTED_DEFECT_CANDIDATE")

    # Semantic target identity, frame sequence and physical calibration are
    # not proven by this pipeline. Never infer PASS, even with a pixel width.
    reasons.append("MASK_TARGET_IDENTITY_NOT_VERIFIED")
    reasons.append("PHYSICAL_CALIBRATION_NOT_VERIFIED")
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": ENGINE_ID,
        "research_only": True,
        "image_sha256": image_sha256,
        "decision": "REVIEW_REQUIRED",
        "defect": "UNDETERMINED",
        "primary_advisory": candidate_rows[0] if candidate_rows else None,
        "advisory_candidates": candidate_rows,
        "normal_advisory": bool(normal_detected),
        "segmentation": {
            "status": "CANDIDATE_REVIEW" if mask_accepted else "UNAVAILABLE_OR_REJECTED",
            "bbox": list(fusion["mask_bbox"]) if mask_accepted else None,
            "model_quality_score": float(fusion["mask_quality"]) if mask_accepted else None,
            "target_identity_verified": False,
        },
        "geometry": {
            "type": fusion.get("geometry"),
            "status": geometry_status,
            "pixel_candidate": pixel_candidate,
            "physical_gap_mm": None,
            "calibration_verified": False,
        },
        "inspect_view_version": fusion.get("inspect_view_version") if preview_bound else None,
        "gemini": {
            "status": semantic_status,
            "model": semantic_model,
            "domain_status": semantic_domain,
            "processing_allowed": semantic_status == "ADVISORY_DOMAIN_ACCEPTED",
            "suggested_joint_type": semantic_geometry_suggestion,
            "semantic_evidence_authoritative": False,
        },
        "reasons": reasons,
        "engineering_result": None,
    }
