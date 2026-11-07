"""Synthetic rough concrete boundaries; research evidence cannot issue physical mm."""

import cv2
import numpy as np

from backend.app.core.cv.experimental_rough_profile import (
    draw_rough_profile_overlay,
    profile_rough_seam,
)
from scripts.benchmark_rough_profile import evaluate_manifest


def synthetic_rough_image(horizontal: bool = False) -> np.ndarray:
    h, w = 480, 440
    image = np.full((h, w, 3), 185, dtype=np.uint8)
    for y in range(h):
        left = 170 + int(5 * np.sin(y / 26.0))
        width = 30 + int(5 * np.sin(y / 33.0))
        image[y, left:left + width] = (24, 24, 24)
    image = cv2.GaussianBlur(image, (3, 3), 0.8)
    return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE) if horizontal else image


def test_rough_vertical_profile_tracks_left_right_and_widths():
    image = synthetic_rough_image()
    before = image.copy()
    audit = profile_rough_seam(image, "VERTICAL_SEAM", (110, 10, 270, 470))
    assert audit.status == "PIXEL_PROFILE_CANDIDATE"
    assert audit.coverage > 0.8
    assert audit.sampled_rows == 80
    assert audit.supported_rows > 60
    assert 25 <= audit.median_width_px <= 38
    assert audit.min_width_px is not None
    assert audit.max_width_px is not None
    assert audit.p95_width_px is not None
    assert audit.width_mad_px is not None
    assert all(
        s.right_point[0] > s.left_point[0]
        and abs((s.right_point[0] - s.left_point[0]) - s.width_px) < 1
        for s in audit.samples if s.width_px is not None
    )
    output = draw_rough_profile_overlay(image, audit)
    assert output.shape == image.shape
    assert not np.array_equal(output, image)
    assert np.array_equal(before, image)
    assert not hasattr(audit, "physical_gap_mm")
    assert not hasattr(audit, "engineering_pass")


def test_rough_horizontal_profile_keeps_full_frame_coordinates():
    image = synthetic_rough_image(horizontal=True)
    audit = profile_rough_seam(image, "HORIZONTAL_SEAM", (10, 110, 470, 270))
    assert audit.status == "PIXEL_PROFILE_CANDIDATE"
    assert 25 <= audit.median_width_px <= 38
    assert all(
        s.right_point[1] > s.left_point[1]
        for s in audit.samples if s.width_px is not None
    )


def test_blank_concrete_wall_returns_review_not_invented_gap():
    blank = np.full((480, 440, 3), 170, dtype=np.uint8)
    audit = profile_rough_seam(blank, "VERTICAL_SEAM", (90, 10, 290, 470))
    assert audit.status == "REVIEW_REQUIRED"
    assert audit.median_width_px is None
    assert audit.supported_rows == 0


def test_invalid_roi_and_unsupported_geometry_fail_closed():
    image = synthetic_rough_image()
    assert profile_rough_seam(image, "VERTICAL_SEAM", None).status == "REVIEW_REQUIRED"
    assert profile_rough_seam(image, "VERTICAL_SEAM", (200, 30, 100, 410)).status == "REVIEW_REQUIRED"
    assert profile_rough_seam(image, "CIRCULAR_OPENING", (10, 10, 410, 470)).status == "REVIEW_REQUIRED"


def test_oversized_dark_shadow_is_not_a_width_measurement():
    image = np.full((480, 440, 3), 180, dtype=np.uint8)
    image[:, 75:365] = (22, 22, 22)
    audit = profile_rough_seam(image, "VERTICAL_SEAM", (50, 10, 390, 470))
    assert audit.status == "REVIEW_REQUIRED"
    assert audit.median_width_px is None


def test_cli_manifest_exports_original_pixel_evidence(tmp_path):
    image = synthetic_rough_image()
    path = tmp_path / "photo.jpg"
    assert cv2.imwrite(str(path), image)
    manifest = {
        "geometry": "VERTICAL_SEAM",
        "frames": [{
            "frame_id": "rough-1",
            "file": "photo.jpg",
            "proposals": [{
                "source": "INSPECTOR",
                "bbox": [110, 10, 270, 470],
                "geometry": "VERTICAL_SEAM",
            }],
        }],
    }
    report, overlays = evaluate_manifest(manifest, tmp_path)
    assert report["physical_measurement_authorized"] is False
    assert report["research_only"] is True
    assert report["units"] == "pixels_only"
    assert report["frames"][0]["median_width_px"] > 0
    assert len(overlays) == 1
