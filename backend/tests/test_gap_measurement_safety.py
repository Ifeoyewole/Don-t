"""Regression tests for unrelated edges and unverified mm provenance."""

import io

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.core.cv.seam_detector import measure_seam_gap
from backend.app.main import app
from backend.app.schemas.domain import JointType


def _stripe(width: int, gap_start: int, gap_end: int) -> np.ndarray:
    img = np.full((400, width, 3), 180, dtype=np.uint8)
    img[:, gap_start:gap_end] = (20, 20, 20)
    return cv2.GaussianBlur(img, (3, 3), 0.8)


def test_large_nonlocalized_stripe_is_not_reported_as_a_joint_gap():
    # A 300px dark strip is not defensible evidence of a 300px joint gap.
    with pytest.raises(ValueError, match="joint_geometry_not_reliable"):
        measure_seam_gap(
            _stripe(600, 150, 450),
            joint_type=JointType.VERTICAL_SEAM,
            num_scanlines=20,
        )


def test_seam_roi_must_contain_the_joint():
    img = _stripe(400, 191, 209)
    with pytest.raises(ValueError, match="joint_geometry_not_reliable"):
        measure_seam_gap(
            img,
            joint_type=JointType.VERTICAL_SEAM,
            roi_bbox=(0, 0, 110, 400),
            num_scanlines=20,
        )


def test_localized_seam_keeps_pixel_measurement_without_mm():
    img = _stripe(400, 191, 209)
    result = measure_seam_gap(
        img,
        joint_type=JointType.VERTICAL_SEAM,
        roi_bbox=(145, 0, 255, 400),
        num_scanlines=20,
    )
    assert 10 < result.mean_gap_px < 30
    assert result.mean_gap_mm is None
    assert result.candidate_gap_mm is None
    assert result.authoritative_gap_mm is None


def test_unverified_nominal_diameter_never_creates_candidate_mm():
    img = _stripe(400, 191, 209)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    response = TestClient(app).post(
        "/api/v1/cv/measure",
        files={"file": ("seam.jpg", io.BytesIO(encoded.tobytes()), "image/jpeg")},
        data={
            "joint_type": "VERTICAL_SEAM",
            "pipe_diameter_mm": "900",
            "calibration_verified": "true",  # client self-attestation is not authority
            "num_samples": "20",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["authoritative_gap_mm"] is None
    assert result["candidate_gap_mm"] is None
    assert result["physical_measurement_available"] is False
    assert result["engineering_result"] == "REVIEW"
    assert result["pixels_per_mm"] is None


def test_reject_invalid_seam_roi():
    with pytest.raises(ValueError, match="joint_geometry_not_reliable"):
        measure_seam_gap(
            _stripe(400, 191, 209),
            joint_type=JointType.VERTICAL_SEAM,
            roi_bbox=(500, 0, 600, 400),
        )
