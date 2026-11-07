"""Unit checks for original shadow-only geometry and camera-fit alternatives.

All fixtures are generated here, with no third-party repository data,
copyrighted pipe images or externally trained model checkpoints.
"""

import cv2
import numpy as np

from backend.app.core.cv.experimental_geometry import (
    audit_dark_seam,
    compare_seam_candidates,
)
from backend.app.core.cv.experimental_calibration import review_reprojection_fit


def make_seam(width=400, gap=(190, 210), *, height=320):
    image = np.full((height, width, 3), 185, dtype=np.uint8)
    if gap:
        image[:, gap[0]:gap[1]] = (22, 22, 22)
    return cv2.GaussianBlur(image, (3, 3), 0.8)


def test_independent_seam_finds_pixel_width_only_with_local_roi():
    result = audit_dark_seam(
        make_seam(), "VERTICAL_SEAM", (145, 10, 255, 310)
    )
    assert result.status == "EVIDENCE_CANDIDATE"
    assert 16 <= result.candidate_gap_px <= 24
    assert result.coverage >= 0.90
    assert result.dispersion_px is not None
    assert compare_seam_candidates(20.0, result) == "CONSISTENT_PIXEL_CANDIDATES"
    assert compare_seam_candidates(440.6, result) == "DISAGREEMENT_REVIEW"


def test_no_roi_no_automatically_assumed_geometry():
    result = audit_dark_seam(make_seam(), "VERTICAL_SEAM", None)
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.candidate_gap_px is None
    assert compare_seam_candidates(20.0, result) == "UNVERIFIABLE"


def test_unrelated_enormous_dark_band_rejected():
    result = audit_dark_seam(
        make_seam(width=600, gap=(150, 450)),
        "VERTICAL_SEAM",
        (0, 0, 600, 320),
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.candidate_gap_px is None


def test_blank_frame_not_measurable():
    result = audit_dark_seam(make_seam(gap=None), "VERTICAL_SEAM", (0, 0, 400, 320))
    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_roi_excludes_seam_then_no_candidate():
    result = audit_dark_seam(
        make_seam(), "VERTICAL_SEAM", (0, 0, 140, 320)
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_horizontal_seam_supported_without_assuming_vertical():
    image = np.full((400, 300, 3), 182, dtype=np.uint8)
    image[190:210, :] = (21, 21, 21)
    result = audit_dark_seam(
        image, "HORIZONTAL_SEAM", (0, 150, 300, 250)
    )
    assert result.status == "EVIDENCE_CANDIDATE"
    assert 16 <= result.candidate_gap_px <= 24


def _synthetic_calibration_views():
    object_coords = np.float32(
        [[float(x), float(y), 0.0] for y in range(6) for x in range(8)]
    )
    intrinsic = np.array(
        [[740.0, 0.0, 320.0], [0.0, 738.0, 240.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    distortion = np.zeros((5, 1), dtype=np.float64)
    obj, img, rot, trans = [], [], [], []
    for index in range(6):
        rotation = np.array([[0.015 * index], [0.025 * index], [0.002 * index]])
        translation = np.array([[0.3 * index], [0.2 * index], [14.0 + index]])
        projected, _ = cv2.projectPoints(
            object_coords, rotation, translation, intrinsic, distortion
        )
        obj.append(object_coords.copy())
        img.append(projected.reshape(-1, 2))
        rot.append(rotation)
        trans.append(translation)
    return obj, img, rot, trans, intrinsic, distortion


def test_multiview_calibration_good_fit_is_only_advisory():
    args = _synthetic_calibration_views()
    result = review_reprojection_fit(*args)
    assert result.status == "REPROJECTION_EVIDENCE"
    assert result.rms_px is not None and result.rms_px < 0.1
    assert result.views_used == 6
    assert not hasattr(result, "calibration_verified")
    assert not hasattr(result, "millimeters_per_pixel")


def test_multiview_calibration_detects_bad_correspondences():
    obj, img, rot, trans, intrinsic, distortion = _synthetic_calibration_views()
    img[2] = img[2] + np.array([8.0, 7.0])
    result = review_reprojection_fit(obj, img, rot, trans, intrinsic, distortion)
    assert result.status == "REVIEW_REQUIRED"
    assert result.rms_px is not None and result.rms_px > 1.5


def test_calibration_requires_multiple_target_views():
    obj, img, rot, trans, intrinsic, distortion = _synthetic_calibration_views()
    result = review_reprojection_fit(
        obj[:1], img[:1], rot[:1], trans[:1], intrinsic, distortion
    )
    assert result.status == "REVIEW_REQUIRED"
    assert result.rms_px is None
