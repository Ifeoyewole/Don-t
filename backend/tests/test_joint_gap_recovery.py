"""CPU geometry contracts; synthetic edge fixtures are not field accuracy."""
import hashlib
import cv2
import numpy as np

from backend.app.core.cv.ai.joint_gap_recovery import recover_joint_gap, text_exclusion_candidates
from backend.app.core.cv.ai.research_sam2_adapter import propose_sam2_mask


def test_mask_band_without_image_edges_cannot_become_gap():
    image = np.full((220, 220, 3), 150, np.uint8)
    mask = np.zeros((220, 220), np.uint8); mask[:, 80:140] = 255
    result = recover_joint_gap(image, mask, [10, 10, 210, 210], 'VERTICAL_SEAM')
    assert result['gap_estimate_px'] is None


def test_stable_two_sided_visible_seam_uses_image_edges_not_mask_width():
    image = np.full((220, 220, 3), 190, np.uint8); image[:, 104:116] = 20
    mask = np.zeros((220, 220), np.uint8); mask[:, 80:140] = 255
    result = recover_joint_gap(image, mask, [30, 10, 190, 210], 'VERTICAL_SEAM')
    assert result['status'] == 'VISIBLE_GAP_PIXEL_CANDIDATE'
    assert 10 <= result['gap_estimate_px'] <= 16
    assert result['gap_estimate_px'] != 60 and result['physical_gap_mm'] is None
    assert not result['joint_opening_confirmed']


def test_text_candidates_are_excluded_without_inpainting():
    image = np.zeros((220, 320, 3), np.uint8)
    cv2.putText(image, 'JOINT OFFSET', (15, 195), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 1)
    before = image.copy(); excluded, boxes = text_exclusion_candidates(image)
    assert boxes and np.count_nonzero(excluded) > 0
    assert np.array_equal(before, image)


def test_single_step_does_not_have_opposing_gap_faces():
    image = np.full((220, 220, 3), 190, np.uint8);image[:, :110] = 30
    result = recover_joint_gap(image, np.full((220, 220), 255, np.uint8), [10, 10, 210, 210], 'VERTICAL_SEAM')
    assert result['gap_estimate_px'] is None


def test_partial_ring_or_offset_remains_unresolved():
    image = np.full((220, 220, 3), 180, np.uint8)
    mask = np.zeros((220, 220), np.uint8)
    cv2.ellipse(mask, (110, 110), (70, 60), 0, 10, 100, 255, 12)
    result = recover_joint_gap(image, mask, [10, 10, 210, 210], 'CIRCULAR_OPENING')
    assert result['gap_estimate_px'] is None
    assert 'SOCKET' in result['reason']


def test_joint_prompt_supplies_negative_points_and_removes_caption_pixels(tmp_path):
    path = tmp_path/'synthetic';path.write_bytes(b'test fixture, not weights')
    image = np.full((220, 220, 3), 100, np.uint8)
    excluded = np.zeros((220, 220), np.uint8); excluded[150:175, 40:90] = 255
    calls = []
    class Predictor:
        def set_image(self, rgb): pass
        def predict(self, **kwargs):
            calls.append(kwargs)
            mask = np.zeros((220, 220), np.uint8);mask[40:190, 30:190] = 1
            return mask[None], np.array([.9]), None
    result = propose_sam2_mask(image, (20, 20, 200, 200), enabled=True, checkpoint_path=path,
        expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), exclusion_mask=excluded,
        predictor_factory=lambda _: Predictor())
    assert calls[0]['point_labels'].tolist() == [0]
    assert result.mask is not None and not np.any(result.mask[excluded > 0])
