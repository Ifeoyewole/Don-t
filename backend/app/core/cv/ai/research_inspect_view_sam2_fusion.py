"""Inspect View + SAM 2.1 + JointInspect OpenCV research evidence bridge.

This combines separate inference *outputs* without mixing checkpoints,
copying upstream repositories, changing live endpoints, or treating a mask
as a defect classification. Inspect View keeps its existing class evidence;
SAM 2.1 contributes a region proposal; original OpenCV estimates optional
pixel geometry. A result is always advisory, never a PASS/FAIL or mm value.

The caller supplies the actual Inspect View preview payload (as returned by
engineering_preview.infer) and a SAM 2 mask result generated independently
from the same image. No model is implicitly loaded or remotely invoked.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Optional

import numpy as np

from backend.app.core.cv.ai.research_sam2_adapter import Sam2MaskEvidence
from backend.app.core.cv.experimental_fusion import FrameRequest, audit_geometry_frames
from backend.app.core.cv.experimental_rough_profile import profile_rough_seam

_SUPPORTED_GEOMETRIES = frozenset({
    "CIRCULAR_OPENING", "VERTICAL_SEAM", "HORIZONTAL_SEAM",
})
# Known unvalidated Inspect View labels are NEVER upgraded through SAM masks.
_UNSUPPORTED_LABELS = frozenset({
    "OPEN_JOINT", "INFILTRATION", "PROTRUDING_LATERAL",
})


@dataclass(frozen=True)
class InspectViewAdvisory:
    label: str
    status: str
    probability: Optional[float]


@dataclass(frozen=True)
class JointInspectFusionEvidence:
    status: str
    geometry: str
    inspect_view_version: str | None
    inspect_view_ready: bool
    inspect_view_advisories: tuple[InspectViewAdvisory, ...]
    sam2_status: str
    mask_bbox: tuple[int, int, int, int] | None
    mask_quality: float | None
    cv_status: str
    cv_pixel_candidate: float | None
    reason: str
    research_only: bool = True
    # No condition/PASS/FAIL, final class label, millimetres, or scale here.


def _classes(payload: dict[str, Any]) -> tuple[InspectViewAdvisory, ...]:
    classes = payload.get("classes")
    if not isinstance(classes, dict):
        return ()
    output: list[InspectViewAdvisory] = []
    for label, record in sorted(classes.items()):
        if not isinstance(label, str) or not isinstance(record, dict):
            continue
        status = record.get("status")
        if not isinstance(status, str):
            status = "UNVALIDATED"
        if label in _UNSUPPORTED_LABELS:
            status = "UNVALIDATED"
        probability = record.get("probability")
        if (
            status != "EXPLORATORY"
            or isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(probability)
            or not 0.0 <= probability <= 1.0
        ):
            probability = None
        output.append(InspectViewAdvisory(label, status, probability))
    return tuple(output)


def combine_inspect_view_and_sam2(
    image_bgr: np.ndarray,
    *,
    geometry: str,
    inspect_view_payload: dict[str, Any] | None,
    sam2_evidence: Sam2MaskEvidence,
    frame_id: str = "research-frame",
) -> JointInspectFusionEvidence:
    """Compose independent class and mask evidence; no automatic model calls."""
    payload = inspect_view_payload if isinstance(inspect_view_payload, dict) else {}
    model_ready = (
        payload.get("model_ready") is True
        and payload.get("research_preview") is True
    )
    version = payload.get("model_version")
    if not isinstance(version, str) or not version.strip():
        version = None
        model_ready = False
    advisories = _classes(payload) if model_ready else ()

    def result(
        status: str,
        cv_status: str,
        candidate: float | None,
        reason: str,
    ) -> JointInspectFusionEvidence:
        return JointInspectFusionEvidence(
            status=status,
            geometry=geometry,
            inspect_view_version=version,
            inspect_view_ready=model_ready,
            inspect_view_advisories=advisories,
            sam2_status=sam2_evidence.status,
            mask_bbox=sam2_evidence.mask_bbox if sam2_evidence.status == "MASK_CANDIDATE_RESEARCH" else None,
            mask_quality=sam2_evidence.mask_quality_score if sam2_evidence.status == "MASK_CANDIDATE_RESEARCH" else None,
            cv_status=cv_status,
            cv_pixel_candidate=candidate,
            reason=reason,
        )

    if geometry not in _SUPPORTED_GEOMETRIES:
        return result("REVIEW_REQUIRED", "NOT_EVALUATED", None, "unsupported_geometry")
    if (
        not isinstance(image_bgr, np.ndarray)
        or image_bgr.ndim != 3
        or image_bgr.shape[2] != 3
        or image_bgr.size == 0
    ):
        return result("REVIEW_REQUIRED", "NOT_EVALUATED", None, "invalid_image")
    proposal = sam2_evidence.to_roi_proposal(geometry)
    if proposal is None:
        return result("REVIEW_REQUIRED", "NOT_EVALUATED", None, "mask_roi_unavailable")

    if geometry in ("VERTICAL_SEAM", "HORIZONTAL_SEAM"):
        cv = profile_rough_seam(image_bgr, geometry, proposal.bbox)
        cv_status = cv.status
        pixel = cv.median_width_px if cv.status == "PIXEL_PROFILE_CANDIDATE" else None
    else:
        audit = audit_geometry_frames(
            [FrameRequest(
                frame_id=frame_id,
                frame_index=0,
                sequence_id="single-image-research",
                image_bgr=image_bgr,
                proposals=[proposal],
            )],
            geometry,
        )
        cv_status = audit.status
        pixel = (
            audit.frame_audits[0].projected_pixel_candidate
            if audit.status == "SINGLE_FRAME_RING_CANDIDATE" and audit.frame_audits
            else None
        )

    if not model_ready:
        return result(
            "SEGMENTATION_ONLY_REVIEW", cv_status, pixel,
            "inspect_view_unavailable_no_defect_classification",
        )
    if pixel is None:
        return result(
            "MULTI_MODEL_REVIEW", cv_status, None,
            "mask_and_class_evidence_without_supported_pixel_geometry",
        )
    return result(
        "MULTI_MODEL_RESEARCH_EVIDENCE", cv_status, pixel,
        "independent_class_mask_and_pixel_evidence_not_verified_defect_or_mm",
    )
