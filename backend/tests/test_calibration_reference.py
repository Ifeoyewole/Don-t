"""Read-only calibration checks must never grant authority from user-entered metadata."""
import json

from fastapi.testclient import TestClient

from backend.app.core.cv.calibration_authority import clear_calibration_cache, get_verified_calibration
from backend.app.main import app
from backend.app.schemas.domain import CalibrationSource


def test_reference_requires_exact_camera_and_project(monkeypatch):
    monkeypatch.setenv("JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON", json.dumps([{
        "reference_id": "RIG-900",
        "project_id": "project-A",
        "source": "TEST_RIG",
        "pipe_diameter_mm": 900,
        "camera_id": "CCTV-RIG-A",
        "validated_joint_types": ["CIRCULAR_OPENING"],
    }]))
    clear_calibration_cache()
    common = dict(
        reference_id="RIG-900",
        source=CalibrationSource.TEST_RIG,
        pipe_diameter_mm=900,
    )
    try:
        assert get_verified_calibration(**common, project_id="project-A", camera_id="CCTV-RIG-A", joint_type="CIRCULAR_OPENING")
        assert get_verified_calibration(**common, project_id=None, camera_id="CCTV-RIG-A", joint_type="CIRCULAR_OPENING") is None
        assert get_verified_calibration(**common, project_id="project-B", camera_id="CCTV-RIG-A", joint_type="CIRCULAR_OPENING") is None
        assert get_verified_calibration(**common, project_id="project-A", camera_id=None, joint_type="CIRCULAR_OPENING") is None
        assert get_verified_calibration(**common, project_id="project-A", camera_id="OTHER", joint_type="CIRCULAR_OPENING") is None
        assert get_verified_calibration(**common, project_id="project-A", camera_id="CCTV-RIG-A", joint_type="VERTICAL_SEAM") is None
    finally:
        clear_calibration_cache()


def test_metadata_cannot_create_reference(monkeypatch):
    monkeypatch.setenv("JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON", "[]")
    clear_calibration_cache()
    try:
        response = TestClient(app).post("/api/v1/cv/calibration/check-reference", json={
            "reference_id": "UNVERIFIED-900",
            "project_id": "unknown",
            "source": "MANHOLE_METADATA",
            "pipe_diameter_mm": 900,
        })
        assert response.status_code == 200
        assert response.json()["reference_verified"] is False
        assert response.json()["status"] == "CALIBRATION_REQUIRED"
    finally:
        clear_calibration_cache()
