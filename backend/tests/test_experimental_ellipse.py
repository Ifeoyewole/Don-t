"""Synthetic-only tests for the projected-ring research alternative.

No user photos, third-party dataset, copied model code or calibration data.
A nested projected ring is NOT automatically a pipe defect or physical gap.
"""

import cv2
import numpy as np

from backend.app.core.cv.experimental_ellipse import audit_projected_pipe_rings


def make_ring_scene(
    *,
    inner: bool = True,
    center_offset: tuple[int, int] = (0, 0),
    outer_angle: float = 28,
    inner_angle: float = 28,
) -> np.ndarray:
    image = np.full((480, 640, 3), 185, dtype=np.uint8)
    cv2.ellipse(
        image, (320, 235), (180, 99), outer_angle, 0, 360,
        (20, 20, 20), thickness=5,
    )
    if inner:
        cv2.ellipse(
            image,
            (320 + center_offset[0], 235 + center_offset[1]),
            (144, 79), inner_angle, 0, 360,
            (25, 25, 25), thickness=5,
        )
    return image


def test_tilted_nested_rings_yield_projected_evidence_not_physical_gap():
    evidence = audit_projected_pipe_rings(
        make_ring_scene(), roi_bbox=(60, 40, 580, 450)
    )
    assert evidence.status == "PROJECTED_RING_EVIDENCE"
    assert evidence.inner_ring is not None
    assert evidence.outer_ring is not None
    assert 20 < evidence.projected_semiaxis_spacing_px < 50
    assert evidence.inner_ring.coverage > 0.85
    assert evidence.outer_ring.coverage > 0.85
    assert evidence.reason == "consistent_projected_ring_boundaries_not_axial_gap"
    assert not hasattr(evidence, "physical_gap_mm")
    assert not hasattr(evidence, "defect_classification")
    assert not hasattr(evidence, "engineering_pass")


def test_single_ring_not_mistaken_for_nested_pair():
    evidence = audit_projected_pipe_rings(
        make_ring_scene(inner=False), roi_bbox=(60, 40, 580, 450)
    )
    assert evidence.status == "INSUFFICIENT_EVIDENCE"
    assert evidence.projected_semiaxis_spacing_px is None


def test_very_different_centers_rejected():
    evidence = audit_projected_pipe_rings(
        make_ring_scene(center_offset=(65, 40)),
        roi_bbox=(60, 40, 580, 450),
    )
    assert evidence.status == "INSUFFICIENT_EVIDENCE"


def test_incompatible_ellipse_orientations_rejected():
    evidence = audit_projected_pipe_rings(
        make_ring_scene(outer_angle=28, inner_angle=74),
        roi_bbox=(60, 40, 580, 450),
    )
    assert evidence.status == "INSUFFICIENT_EVIDENCE"


def test_blank_frame_and_unselected_roi_fail_closed():
    blank = np.full((480, 640, 3), 180, dtype=np.uint8)
    assert audit_projected_pipe_rings(
        blank, roi_bbox=(60, 40, 580, 450)
    ).status == "INSUFFICIENT_EVIDENCE"
    assert audit_projected_pipe_rings(
        make_ring_scene(), roi_bbox=None
    ).reason == "localized_joint_roi_required"


def test_invalid_roi_and_excluded_rings_fail_closed():
    image = make_ring_scene()
    assert audit_projected_pipe_rings(
        image, (200, 300, 100, 400)
    ).reason == "invalid_roi"
    assert audit_projected_pipe_rings(
        image, (5, 5, 90, 90)
    ).status == "INSUFFICIENT_EVIDENCE"


def test_grayscale_input_is_supported_without_changing_geometry_authority():
    image = cv2.cvtColor(make_ring_scene(), cv2.COLOR_BGR2GRAY)
    evidence = audit_projected_pipe_rings(image, (60, 40, 580, 450))
    assert evidence.status == "PROJECTED_RING_EVIDENCE"
    assert evidence.projected_semiaxis_spacing_px is not None
