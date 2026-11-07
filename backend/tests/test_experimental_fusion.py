"""Synthetic contract tests for integrated ROI/partial-arc video research.

No changes to production measurement; no dataset or third-party source code.
"""

import cv2
import numpy as np

from backend.app.core.cv.experimental_fusion import (
    FrameRequest, RoiProposal, _select_roi, audit_geometry_frames,
)


def _ring_frame(partial: bool = False, shade: int = 180) -> np.ndarray:
    image = np.full((480, 640, 3), shade, dtype=np.uint8)
    end = 240 if partial else 360
    for axes, color in [((180, 99), (30, 30, 30)), ((144, 79), (40, 40, 40))]:
        cv2.ellipse(image, (320, 235), axes, 28, 0, end, color, 5)
    return image


def _frame(index: int, image: np.ndarray, source: str = "INSPECTOR", sequence: str = "video-1") -> FrameRequest:
    return FrameRequest(
        frame_id=f"frame-{sequence}-{index}",
        frame_index=index,
        sequence_id=sequence,
        image_bgr=image,
        proposals=[RoiProposal(source, (60, 40, 580, 450), "CIRCULAR_OPENING", None if source == "INSPECTOR" else 0.93)],
    )


def test_full_ring_evidence_has_no_defect_or_mm_authority():
    result = audit_geometry_frames([_frame(1, _ring_frame())], "CIRCULAR_OPENING")
    assert result.status == "SINGLE_FRAME_RING_CANDIDATE"
    assert result.frame_audits[0].status == "FULL_RING_CANDIDATE"
    assert result.frame_audits[0].projected_pixel_candidate is not None
    assert not hasattr(result, "physical_gap_mm")
    assert not hasattr(result, "engineering_pass")
    assert not hasattr(result, "defect_label")


def test_partial_ring_single_frame_requires_temporal_confirmation():
    result = audit_geometry_frames([_frame(1, _ring_frame(partial=True))], "CIRCULAR_OPENING")
    assert result.status == "REVIEW_REQUIRED"
    assert result.frame_audits[0].status == "PARTIAL_RING_CANDIDATE"


def test_two_distinct_adjacent_partial_frames_can_support_visual_pair():
    frames = [
        _frame(1, _ring_frame(partial=True, shade=181)),
        _frame(2, _ring_frame(partial=True, shade=182)),
    ]
    result = audit_geometry_frames(frames, "CIRCULAR_OPENING")
    assert result.status == "TEMPORAL_PARTIAL_RING_CANDIDATE"
    assert all(x.status == "PARTIAL_RING_CANDIDATE" for x in result.frame_audits)


def test_duplicate_image_cannot_count_as_second_frame():
    same = _ring_frame(partial=True)
    result = audit_geometry_frames([_frame(1, same), _frame(2, same.copy())], "CIRCULAR_OPENING")
    assert result.status == "REVIEW_REQUIRED"
    assert result.frame_audits[-1].reason == "duplicate_image_bytes"


def test_unrelated_video_frames_cannot_confirm_partial_pair():
    first = _frame(1, _ring_frame(partial=True, shade=179), sequence="video-1")
    second = _frame(2, _ring_frame(partial=True, shade=180), sequence="video-2")
    result = audit_geometry_frames([first, second], "CIRCULAR_OPENING")
    assert result.status == "REVIEW_REQUIRED"


def test_roi_source_priority_and_validation():
    frame = _ring_frame()
    proposals = [
        RoiProposal("GEMINI", (30, 30, 560, 420), "CIRCULAR_OPENING", 0.95),
        RoiProposal("INSPECT_VIEW", (50, 40, 570, 450), "CIRCULAR_OPENING", 0.94),
        RoiProposal("INSPECTOR", (60, 40, 580, 450), "CIRCULAR_OPENING"),
        RoiProposal("INSPECTOR", (-10, 0, 100, 100), "CIRCULAR_OPENING"),
    ]
    selection = _select_roi(proposals, frame, "CIRCULAR_OPENING")
    assert selection is not None and selection.source == "INSPECTOR"
    assert selection.bbox == (60, 40, 580, 450)
    assert _select_roi([RoiProposal("GEMINI", (60, 40, 580, 450), "CIRCULAR_OPENING", 0.2)], frame, "CIRCULAR_OPENING") is None
    assert _select_roi([RoiProposal("UNKNOWN", (60, 40, 580, 450), "CIRCULAR_OPENING", 1.0)], frame, "CIRCULAR_OPENING") is None


def test_invalid_geometry_and_missing_roi_fail_closed():
    img = _ring_frame()
    missing = FrameRequest("f", 0, "v", img, [])
    assert audit_geometry_frames([missing], "CIRCULAR_OPENING").status == "REVIEW_REQUIRED"
    assert audit_geometry_frames([missing], "OPEN_JOINT").status == "REVIEW_REQUIRED"


def test_seam_is_processed_as_seam_not_misclassified_as_ellipse():
    image = np.full((320, 400, 3), 180, dtype=np.uint8)
    image[:, 190:210] = (22, 22, 22)
    frame = FrameRequest("seam-1", 1, "v", image, [
        RoiProposal("INSPECTOR", (145, 10, 255, 310), "VERTICAL_SEAM"),
    ])
    result = audit_geometry_frames([frame], "VERTICAL_SEAM")
    assert result.status == "PIXEL_SEAM_CANDIDATE"
    assert 15 <= result.frame_audits[0].projected_pixel_candidate <= 25
