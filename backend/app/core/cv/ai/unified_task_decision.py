"""Task-aware research decisions for sewer CCTV frames without joint geometry.

Do not run OpenCV seam/ring profiling for object or water-ingress tasks.
Outputs are advisory only, never a defect diagnosis or mm measurement.
No network calls or model loads. Gemini input must be a signed, verified
receipt from the trusted worker, never plain operator-provided JSON.
"""

from __future__ import annotations

import math
from typing import Any, Mapping
from backend.app.core.cv.ai.unified_vision_v1 import (
    ENGINE_ID, SCHEMA_VERSION, UNVALIDATED_CLASSES,
)

NONJOINT_TASKS = frozenset({"OBJECT_SEGMENTATION", "INFILTRATION_REVIEW"})
R5_VERSION = "repr-convnext-masked-r5-20261104"


def _probability(value: Any) -> bool:
    return (type(value) in (float, int) and math.isfinite(value)
            and 0.0 <= value <= 1.0)


def _sha(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _gemini_for_nonjoint(
    receipt: Mapping[str, Any] | None, image_sha256: str
) -> tuple[dict[str, Any], bool, list[str]]:
    """Reuse a previously verified same-image semantic receipt.

    PIPE_INTERIOR_NO_JOINT can be research-suitable. It NEVER changes the
    production measurement gate's processing_allowed=false.
    """
    status, model, domain = "NOT_PROVIDED", None, None
    live_allowed, research_eligible = False, False
    reasons: list[str] = []
    if receipt is not None:
        if (not isinstance(receipt, Mapping)
                or receipt.get("image_sha256") != image_sha256
                or not isinstance(receipt.get("semantic_gate"), Mapping)):
            status = "UNVERIFIED"
            reasons.append("GEMINI_RECEIPT_PROVENANCE_INVALID")
        else:
            gate = receipt["semantic_gate"]
            model, domain = gate.get("model"), gate.get("domain_status")
            live_allowed = gate.get("processing_allowed") is True
            valid = (
                model == "gemini-3.1-pro-preview"
                and gate.get("pipe_visible") is True
                and gate.get("quality") == "OK"
                and gate.get("prompt_image_conflict") is False
                and type(gate.get("joint_visible")) is bool
                and type(gate.get("processing_allowed")) is bool
            )
            if not valid:
                status = "BLOCKED"
            elif (domain == "PIPE_INTERIOR_NO_JOINT"
                  and gate.get("joint_visible") is False
                  and live_allowed is False):
                status, research_eligible = "RESEARCH_PIPE_INTERIOR_ACCEPTED", True
                reasons.append("PRODUCTION_JOINT_MEASUREMENT_GATE_REMAINS_BLOCKED")
            elif (domain == "PIPE_JOINT_INSPECTION"
                  and gate.get("joint_visible") is True
                  and live_allowed is True):
                status, research_eligible = "ADVISORY_DOMAIN_ACCEPTED", True
            else:
                status = "BLOCKED"
            if status == "BLOCKED":
                reasons.append("GEMINI_SCENE_QUALITY_OR_DOMAIN_BLOCKED")
    evidence = {
        "status": status,
        "model": model,
        "domain_status": domain,
        "processing_allowed": live_allowed if status != "UNVERIFIED" else False,
        "research_scene_eligible": research_eligible,
        "semantic_evidence_authoritative": False,
    }
    return evidence, (receipt is not None and not research_eligible), reasons


def build_nonjoint_research_result(
    *,
    task_type: str,
    image_sha256: str,
    inspect_view_payload: Mapping[str, Any] | None,
    sam2_status: str,
    sam2_bbox: tuple[int, int, int, int] | None,
    sam2_quality: float | None,
    mask_pixel_verified: bool,
    verified_gemini_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Make one non-joint advisory after independent mask-pixel verification.

    The caller must independently verify the SAM image BGR digest,
    mask dimensions and exact pixel-derived bbox. A Gemini receipt may be
    passed only after checking signature, issuer, original SHA and expiry.
    """
    if task_type not in NONJOINT_TASKS:
        raise ValueError("Only non-joint tasks allowed")
    if not _sha(image_sha256):
        raise ValueError("Original source image must have a lowercase SHA-256")

    reasons: list[str] = []
    preview = inspect_view_payload if isinstance(inspect_view_payload, Mapping) else {}
    r5_ready = (
        preview.get("research_preview") is True
        and preview.get("model_ready") is True
        and preview.get("image_sha256") == image_sha256
        and preview.get("model_version") == R5_VERSION
    )
    if not r5_ready:
        reasons.append("INSPECT_VIEW_R5_MISSING_OR_SOURCE_MISMATCHED")

    gemini, blocked, semantic_reasons = _gemini_for_nonjoint(
        verified_gemini_receipt, image_sha256
    )
    reasons.extend(semantic_reasons)
    if verified_gemini_receipt is None:
        reasons.append("GEMINI_SEMANTIC_RECEIPT_NOT_PROVIDED")

    good_bbox = (
        isinstance(sam2_bbox, tuple) and len(sam2_bbox) == 4
        and all(type(n) is int and n >= 0 for n in sam2_bbox)
        and sam2_bbox[0] < sam2_bbox[2]
        and sam2_bbox[1] < sam2_bbox[3]
    )
    mask_ok = (
        mask_pixel_verified is True
        and sam2_status == "MASK_CANDIDATE_RESEARCH"
        and good_bbox and _probability(sam2_quality)
        and sam2_quality >= 0.70
    )
    if not mask_ok:
        reasons.append("SAM2_OBJECT_REGION_NOT_VERIFIED")
    if blocked:
        mask_ok = False
        reasons.append("SEMANTIC_GATE_PREVENTS_RESEARCH_MASK_ACCEPTANCE")

    candidate_rows: list[dict[str, Any]] = []
    normal = False
    classes = preview.get("classes") if r5_ready else None
    if isinstance(classes, Mapping) and not blocked:
        for label, record in classes.items():
            if (not isinstance(label, str) or label in UNVALIDATED_CLASSES
                    or not isinstance(record, Mapping)
                    or record.get("status") != "EXPLORATORY"
                    or record.get("detected") is not True
                    or not _probability(record.get("probability"))):
                continue
            if label == "NORMAL":
                normal = True
            else:
                candidate_rows.append({
                    "label": label,
                    "probability": round(float(record["probability"]), 6),
                    "classification_status": "EXPLORATORY",
                })
    candidate_rows.sort(key=lambda item: (-item["probability"], item["label"]))
    if candidate_rows:
        reasons.append("CLASS_EVIDENCE_REQUIRES_SPECIALIST_VERIFICATION")
    if normal and candidate_rows:
        reasons.append("CONFLICTING_NORMAL_AND_DEFECT_ADVISORIES")

    if task_type == "INFILTRATION_REVIEW":
        reasons.extend([
            "ACTIVE_INFILTRATION_REQUIRES_TEMPORAL_OR_FIELD_EVIDENCE",
            "WET_STAIN_IS_NOT_PROOF_OF_ACTIVE_INGRESS",
        ])
        task_evidence = {
            "target": "POSSIBLE_WATER_INGRESS_FEATURE",
            "active_infiltration_confirmed": False,
            "temporal_confirmation": "REQUIRED",
            "video_sequence_verified": False,
        }
    else:
        reasons.append("MASK_CANNOT_PROVE_PROTRUDING_LATERAL_IDENTITY")
        task_evidence = {
            "target": "PROMPTED_INTRUDING_OBJECT_CANDIDATE",
            "protruding_lateral_confirmed": False,
        }
    reasons.extend(["NO_JOINT_GAP_MEASUREMENT_FOR_TASK",
                    "TARGET_IDENTITY_NOT_INDEPENDENTLY_VERIFIED"])
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": ENGINE_ID,
        "research_only": True,
        "task_type": task_type,
        "image_sha256": image_sha256,
        "decision": "REVIEW_REQUIRED",
        "defect": "UNDETERMINED",
        "primary_advisory": candidate_rows[0] if candidate_rows else None,
        "advisory_candidates": candidate_rows,
        "normal_advisory": normal,
        "segmentation": {
            "status": "CANDIDATE_REVIEW" if mask_ok else "UNAVAILABLE_OR_REJECTED",
            "bbox": list(sam2_bbox) if mask_ok else None,
            "model_quality_score": float(sam2_quality) if mask_ok else None,
            "target_identity_verified": False,
        },
        "geometry": {
            "type": None, "status": "NOT_APPLICABLE_FOR_TASK",
            "pixel_candidate": None, "physical_gap_mm": None,
            "calibration_verified": False,
        },
        "inspect_view_version": R5_VERSION if r5_ready else None,
        "gemini": gemini,
        "task_evidence": task_evidence,
        "reasons": reasons,
        "engineering_result": None,
    }
