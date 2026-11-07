"""Fusion contract: existing Inspect View r5 + SAM 2.1 + OpenCV remain advisory.

All images and masks are generated in tests; no pretrained model or copyrighted
dataset is downloaded and no engineering decision or mm scale is invented.
"""

from hashlib import sha256

import numpy as np

from backend.app.core.cv.ai.research_inspect_view_sam2_fusion import (
    combine_inspect_view_and_sam2,
)
from backend.app.core.cv.ai.research_sam2_adapter import Sam2MaskEvidence


def _image():
    image = np.full((320, 400, 3), 185, dtype=np.uint8)
    image[:, 190:210] = (22, 22, 22)
    return image


def _sam(image, *, bbox=(145, 10, 255, 310), digest=None):
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    x0, y0, x1, y1 = bbox
    mask[y0:y1, x0:x1] = 255
    return Sam2MaskEvidence(
        status="MASK_CANDIDATE_RESEARCH",
        model_id="sam2.1_hiera_tiny",
        prompt_bbox=bbox,
        mask_bbox=bbox,
        mask_quality_score=0.94,
        mask=mask,
        reason="test_mask",
        image_sha256=digest or sha256(np.ascontiguousarray(image).tobytes()).hexdigest(),
    )


def _inspect(*, loaded=True):
    return {
        "model_ready": loaded,
        "research_preview": True,
        "model_version": "repr-convnext-masked-r5-20261104",
        "classes": {
            "SURFACE_DAMAGE": {"status": "EXPLORATORY", "probability": 0.68},
            "OPEN_JOINT": {"status": "EXPLORATORY", "probability": 0.99},
            "INFILTRATION": {"status": "EXPLORATORY", "probability": 0.98},
            "PROTRUDING_LATERAL": {"status": "EXPLORATORY", "probability": 0.90},
        },
    }


def test_combination_retains_inspect_view_and_fuses_mask_with_pixel_evidence():
    image = _image()
    result = combine_inspect_view_and_sam2(
        image, geometry="VERTICAL_SEAM",
        inspect_view_payload=_inspect(),
        sam2_evidence=_sam(image),
    )
    assert result.status == "MULTI_MODEL_RESEARCH_EVIDENCE"
    assert result.inspect_view_ready is True
    assert result.inspect_view_version == "repr-convnext-masked-r5-20261104"
    assert result.sam2_status == "MASK_CANDIDATE_RESEARCH"
    assert result.cv_status == "PIXEL_PROFILE_CANDIDATE"
    assert result.cv_pixel_candidate is not None
    assert 12 <= result.cv_pixel_candidate <= 28
    assert result.mask_bbox == (145, 10, 255, 310)
    assert result.research_only is True
    assert not hasattr(result, "authoritative_gap_mm")
    assert not hasattr(result, "engineering_result")
    cls = {c.label: c for c in result.inspect_view_advisories}
    assert cls["SURFACE_DAMAGE"].probability == 0.68
    for name in ("OPEN_JOINT", "INFILTRATION", "PROTRUDING_LATERAL"):
        assert cls[name].status == "UNVALIDATED"
        assert cls[name].probability is None


def test_inspect_view_unavailable_still_keeps_separate_segmentation_evidence():
    image = _image()
    result = combine_inspect_view_and_sam2(
        image, geometry="VERTICAL_SEAM",
        inspect_view_payload=_inspect(loaded=False),
        sam2_evidence=_sam(image),
    )
    assert result.status == "SEGMENTATION_ONLY_REVIEW"
    assert result.inspect_view_ready is False
    assert result.inspect_view_advisories == ()
    assert result.cv_pixel_candidate is not None


def test_fusion_rejects_mask_generated_for_another_photo():
    image = _image()
    result = combine_inspect_view_and_sam2(
        image, geometry="VERTICAL_SEAM", inspect_view_payload=_inspect(),
        sam2_evidence=_sam(image, digest="0" * 64),
    )
    assert result.status == "REVIEW_REQUIRED"
    assert result.reason == "sam_mask_image_provenance_missing_or_mismatched"
    assert result.cv_pixel_candidate is None


def test_fusion_rejects_inconsistent_declared_bbox_and_actual_mask_pixels():
    image = _image()
    evidence = _sam(image)
    object.__setattr__(evidence, "mask_bbox", (155, 10, 255, 310))
    result = combine_inspect_view_and_sam2(
        image, geometry="VERTICAL_SEAM", inspect_view_payload=_inspect(),
        sam2_evidence=evidence,
    )
    assert result.status == "REVIEW_REQUIRED"
    assert result.reason == "sam_mask_bbox_disagrees_with_pixels"


def test_fusion_rejects_empty_and_unavailable_masks():
    image = _image()
    unavailable = Sam2MaskEvidence(
        "MODEL_UNAVAILABLE", "sam2.1_hiera_tiny", None, None, None, None,
        "checkpoint_required",
    )
    result = combine_inspect_view_and_sam2(
        image, geometry="VERTICAL_SEAM", inspect_view_payload=_inspect(),
        sam2_evidence=unavailable,
    )
    assert result.status == "REVIEW_REQUIRED"
    assert result.cv_pixel_candidate is None


def test_fusion_never_forces_unsupported_defect_into_seam_geometry():
    image = _image()
    result = combine_inspect_view_and_sam2(
        image, geometry="INFILTRATION", inspect_view_payload=_inspect(),
        sam2_evidence=_sam(image),
    )
    assert result.status == "REVIEW_REQUIRED"
    assert result.reason == "unsupported_geometry"
