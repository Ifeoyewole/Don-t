"""Task-aware local batch inference without GPU, weights or external services."""

import hashlib
from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.app.core.cv.ai.research_sam2_adapter import Sam2MaskEvidence
from scripts.task_aware_unified_review import (
    analyze_nonjoint_image, mask_matches_source_pixels,
)

SHA_MODEL = "repr-convnext-masked-r5-20261104"


def test_mask_provenance_and_pixel_bbox_validation():
    image = np.zeros((416, 416, 3), dtype=np.uint8)
    mask = np.zeros((416, 416), dtype=np.uint8)
    mask[40:200, 160:340] = 255
    sha = hashlib.sha256(image.tobytes()).hexdigest()
    good = Sam2MaskEvidence(
        "MASK_CANDIDATE_RESEARCH", "sam2.1_hiera_tiny",
        (100, 20, 360, 230), (160, 40, 340, 200),
        0.88, mask, "research_only", sha,
    )
    assert mask_matches_source_pixels(good, image)
    assert not mask_matches_source_pixels(
        Sam2MaskEvidence(
            good.status, good.model_id, good.prompt_bbox,
            (150, 40, 340, 200), good.mask_quality_score,
            mask, good.reason, sha,
        ), image
    )
    assert not mask_matches_source_pixels(
        Sam2MaskEvidence(
            good.status, good.model_id, good.prompt_bbox,
            good.mask_bbox, good.mask_quality_score,
            mask, good.reason, "a"*64,
        ), image
    )


@pytest.mark.parametrize("task", [
    "OBJECT_SEGMENTATION", "INFILTRATION_REVIEW",
])
def test_nonjoint_runner_never_runs_open_cv_joint_geometry(monkeypatch, tmp_path, task):
    import backend.app.api.v1.endpoints.engineering_preview as preview_module
    import scripts.task_aware_unified_review as runner
    import backend.app.core.cv.experimental_rough_profile as rough
    import backend.app.core.cv.experimental_fusion as fusion

    def forbidden(*a, **kw):
        raise AssertionError("No joint-gap geometry permitted for nonjoint tasks")

    monkeypatch.setattr(rough, "profile_rough_seam", forbidden)
    monkeypatch.setattr(fusion, "audit_geometry_frames", forbidden)

    image = np.zeros((416, 416, 3), dtype=np.uint8)
    image[:, :, 1] = 70
    valid, jpeg = cv2.imencode(".jpg", image)
    assert valid
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(jpeg.tobytes())
    encoded_sha = hashlib.sha256(jpeg.tobytes()).hexdigest()
    decoded = cv2.imdecode(
        np.frombuffer(jpeg.tobytes(), dtype=np.uint8), cv2.IMREAD_COLOR
    )
    decoded_sha = hashlib.sha256(decoded.tobytes()).hexdigest()
    mask = np.zeros((416, 416), dtype=np.uint8)
    mask[50:220, 160:300] = 255

    def fake_sam(*args, **kwargs):
        return Sam2MaskEvidence(
            "MASK_CANDIDATE_RESEARCH", "sam2.1_hiera_tiny",
            (140, 30, 320, 250), (160, 50, 300, 220),
            0.92, mask, "candidate_only", decoded_sha,
        )

    def fake_preview(payload):
        assert hashlib.sha256(payload).hexdigest() == encoded_sha
        return {
            "model_ready": True, "research_preview": True,
            "model_version": SHA_MODEL,
            "image_sha256": encoded_sha,
            "classes": {
                "PROTRUDING_LATERAL": {
                    "status": "UNVALIDATED", "detected": False,
                    "probability": None,
                }
            },
        }

    monkeypatch.setattr(runner, "propose_sam2_mask", fake_sam)
    monkeypatch.setattr(preview_module, "infer", fake_preview)
    report, overlay = analyze_nonjoint_image(
        image_path, task_type=task, bbox=(140, 30, 320, 250),
        checkpoint_path=tmp_path / "sam.pt",
        checkpoint_sha256="b"*64,
        mask_output_path=tmp_path / "candidate.png",
        sam2_predictor_factory=lambda _: object(),
    )
    result = report["unified_result"]
    assert result["task_type"] == task
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["defect"] == "UNDETERMINED"
    assert result["segmentation"]["status"] == "CANDIDATE_REVIEW"
    assert (tmp_path / 'candidate.png').exists()
    assert report['mask_artifact']['defect_identity_verified'] is False
    assert report["sam2_mask_pixels_verified"] is True
    assert result["geometry"]["status"] == "NOT_APPLICABLE_FOR_TASK"
    assert result["geometry"]["physical_gap_mm"] is None
    assert overlay is not None


def test_task_runner_rejects_roi_outside_image(tmp_path):
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    _, jpeg = cv2.imencode(".jpg", image)
    path = tmp_path / "frame.jpg"
    path.write_bytes(jpeg.tobytes())
    with pytest.raises(ValueError, match="ROI"):
        analyze_nonjoint_image(
            path, task_type="OBJECT_SEGMENTATION",
            bbox=(100, 0, 410, 500),
            checkpoint_path=Path("dummy"),
            checkpoint_sha256="a"*64,
            sam2_predictor_factory=lambda _: object(),
        )
