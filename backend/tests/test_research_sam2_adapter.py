"""Research SAM 2 adapter tests; synthetic masks, no external model or media."""

import hashlib

import numpy as np

from backend.app.core.cv.ai.research_sam2_adapter import propose_sam2_mask
from backend.app.core.cv.experimental_fusion import _select_roi


def _weights(tmp_path):
    checkpoint = tmp_path / "official-publisher-weights-placeholder.pt"
    data = b"test-only-checkpoint-not-actual-sam-weights"
    checkpoint.write_bytes(data)
    return checkpoint, hashlib.sha256(data).hexdigest()


def _image():
    return np.full((300, 400, 3), [17, 47, 94], dtype=np.uint8)


class FakeSam2:
    def __init__(self, *, score=0.92, bad_shape=False, outside=False):
        self.score = score
        self.bad_shape = bad_shape
        self.outside = outside
        self.received_rgb = None
        self.received_box = None

    def set_image(self, image_rgb):
        self.received_rgb = image_rgb.copy()

    def predict(self, *, box, multimask_output):
        self.received_box = box
        assert multimask_output is True
        h, w = self.received_rgb.shape[:2]
        masks = np.zeros((2, h, w), dtype=np.float32)
        if self.outside:
            masks[0, 220:280, 300:370] = 1.0
        else:
            masks[0, 85:220, 105:260] = 1.0
        masks[1, 95:200, 150:200] = 1.0
        if self.bad_shape:
            masks = masks[:, :150, :]
        return masks, np.asarray([self.score, 0.21]), None


def test_disabled_by_default_no_package_or_model_needed():
    evidence = propose_sam2_mask(_image(), (80, 60, 280, 240))
    assert evidence.status == "MODEL_UNAVAILABLE"
    assert evidence.mask is None
    assert evidence.to_roi_proposal("VERTICAL_SEAM") is None


def test_good_faux_mask_maps_to_jointinspect_proposal_without_mm(tmp_path):
    checkpoint, digest = _weights(tmp_path)
    predictor = FakeSam2()
    evidence = propose_sam2_mask(
        _image(), (80, 60, 280, 240),
        enabled=True, checkpoint_path=checkpoint, expected_sha256=digest,
        predictor_factory=lambda _: predictor,
    )
    assert evidence.status == "MASK_CANDIDATE_RESEARCH"
    assert evidence.mask_bbox == (105, 85, 260, 220)
    assert evidence.mask.shape == (300, 400)
    assert set(np.unique(evidence.mask)).issubset({0, 255})
    assert tuple(predictor.received_rgb[0, 0]) == (94, 47, 17)
    assert list(predictor.received_box) == [80, 60, 280, 240]
    roi = evidence.to_roi_proposal("VERTICAL_SEAM")
    assert roi is not None and roi.source == "CV_MASK"
    assert roi.geometry == "VERTICAL_SEAM"
    assert roi.bbox == (105, 85, 260, 220)
    selected = _select_roi([roi], _image(), "VERTICAL_SEAM")
    assert selected == roi
    assert not hasattr(evidence, "gap_mm")
    assert not hasattr(evidence, "engineering_pass")
    assert not hasattr(evidence, "defect_classification")


def test_sha_mismatch_refuses_even_fake_predictor(tmp_path):
    checkpoint, _ = _weights(tmp_path)
    response = propose_sam2_mask(
        _image(), (80, 60, 280, 240),
        enabled=True, checkpoint_path=checkpoint,
        expected_sha256="f" * 64,
        predictor_factory=lambda _: FakeSam2(),
    )
    assert response.status == "MODEL_UNAVAILABLE"
    assert "sha256" in response.reason


def test_missing_checkpoint_and_invalid_prompt_fail_closed(tmp_path):
    checkpoint, digest = _weights(tmp_path)
    assert propose_sam2_mask(
        _image(), (80, 60, 280, 240), enabled=True
    ).status == "MODEL_UNAVAILABLE"
    assert propose_sam2_mask(
        _image(), (-1, 0, 270, 270), enabled=True,
        checkpoint_path=checkpoint, expected_sha256=digest,
        predictor_factory=lambda _: FakeSam2(),
    ).status == "MODEL_UNAVAILABLE"


def test_low_quality_and_off_target_masks_cannot_become_roi(tmp_path):
    checkpoint, digest = _weights(tmp_path)
    for predictor in (FakeSam2(score=0.45), FakeSam2(outside=True), FakeSam2(bad_shape=True)):
        evidence = propose_sam2_mask(
            _image(), (80, 60, 280, 240), enabled=True,
            checkpoint_path=checkpoint, expected_sha256=digest,
            predictor_factory=lambda _, p=predictor: p,
        )
        assert evidence.status == "REVIEW_REQUIRED"
        assert evidence.to_roi_proposal("CIRCULAR_OPENING") is None
