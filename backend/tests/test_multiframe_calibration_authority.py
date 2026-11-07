"""Multi-frame physical units require a server-owned calibration reference."""

import io
import json
from types import SimpleNamespace

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints import multi_frame
from backend.app.core.cv.calibration_authority import clear_calibration_cache
from backend.app.main import app


def _frames():
    image = np.full((350, 350, 3), 40, dtype=np.uint8)
    cv2.circle(image, (175, 175), 122, (210, 210, 210), -1)
    cv2.circle(image, (175, 175), 98, (20, 20, 20), -1)
    cv2.circle(image, (175, 175), 80, (180, 180, 180), -1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    blob = encoded.tobytes()
    return [
        ("files", (f"frame-{i}.jpg", io.BytesIO(blob), "image/jpeg"))
        for i in range(2)
    ]


def _client_with_stub(monkeypatch, *, fail_second_geometry=False):
    class FakeVertex:
        def evaluate(self, image):
            return SimpleNamespace(processing_allowed=True, user_message=None)

    monkeypatch.setattr(
        "backend.app.core.cv.ai.vertex_semantic_gate.get_vertex_semantic_gate",
        lambda: FakeVertex(),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.multi_frame.validate_image_quality",
        lambda image: SimpleNamespace(usable=True),
        raising=False,
    )
    count = [0]
    def fake_measure(*, pipe_diameter_mm=None, **kwargs):
        count[0] += 1
        accepted = not (fail_second_geometry and count[0] == 2)
        # Even when an implementation has provisional mm from another source,
        # the multi-frame endpoint must independently enforce server authority.
        return SimpleNamespace(
            mean_gap_px=20.0 + count[0],
            debug_info=None,
            mean_gap_mm=7.0,
            authoritative_gap_mm=7.0 if accepted else None,
            physical_measurement_available=accepted,
            geometry_tier="ACCEPTABLE_GEOMETRY" if accepted else "PARTIAL_REVIEW_GEOMETRY",
        )
    monkeypatch.setattr(multi_frame, "measure_circular_gap", fake_measure)
    return TestClient(app)


def _reference(monkeypatch):
    monkeypatch.setenv("JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON", json.dumps([{
        "reference_id": "VERIFIED-100",
        "project_id": "fixture-project",
        "source": "TEST_RIG",
        "camera_id": "FIXTURE-RIG",
        "pipe_diameter_mm": 100.0,
        "validated_joint_types": ["CIRCULAR_OPENING"],
    }]))
    clear_calibration_cache()


def test_legacy_true_boolean_cannot_enable_physical_units(monkeypatch):
    client = _client_with_stub(monkeypatch)
    response = client.post(
        "/api/v1/cv/measure/multi-frame",
        files=_frames(),
        data={
            "pipe_diameter_mm": "100",
            "calibration_source": "TEST_RIG",
            "calibration_verified": "true",
            "max_gap_mm": "15",
        },
    )
    assert response.status_code == 200, response.text
    obj = response.json()
    assert obj["median_gap_px"] > 0
    assert obj["calibration_verified"] is False
    assert obj["physical_measurement_available"] is False
    assert obj["median_gap_mm"] is None
    assert obj["condition"] is None
    assert obj["result_status"] == "REVIEW_REQUIRED"


def test_server_record_matches_only_scoped_camera_and_project(monkeypatch):
    _reference(monkeypatch)
    try:
        for camera, project, expected in [
            ("FIXTURE-RIG", "fixture-project", True),
            ("WRONG-RIG", "fixture-project", False),
            ("FIXTURE-RIG", "wrong-project", False),
            ("", "fixture-project", False),
        ]:
            client = _client_with_stub(monkeypatch)
            response = client.post(
                "/api/v1/cv/measure/multi-frame",
                files=_frames(),
                data={
                    "pipe_diameter_mm": "100",
                    "calibration_source": "TEST_RIG",
                    "calibration_verified": "false",  # trusted reference, not client truth
                    "calibration_reference_id": "VERIFIED-100",
                    "project_id": project,
                    "camera_id": camera,
                },
            )
            assert response.status_code == 200, response.text
            obj = response.json()
            assert obj["calibration_verified"] is expected
            assert obj["physical_measurement_available"] is expected
            assert (obj["median_gap_mm"] is not None) is expected
            # Without an inspector-supplied approved tolerance a normal-joint
            # classification must not be invented.
            assert obj["condition"] is None
    finally:
        clear_calibration_cache()


def test_one_partial_frame_blocks_all_burst_physical_units(monkeypatch):
    _reference(monkeypatch)
    try:
        client = _client_with_stub(monkeypatch, fail_second_geometry=True)
        response = client.post(
            "/api/v1/cv/measure/multi-frame",
            files=_frames(),
            data={
                "pipe_diameter_mm": "100",
                "calibration_source": "TEST_RIG",
                "calibration_reference_id": "VERIFIED-100",
                "project_id": "fixture-project",
                "camera_id": "FIXTURE-RIG",
            },
        )
        assert response.status_code == 200, response.text
        obj = response.json()
        assert obj["calibration_verified"] is True
        assert obj["physical_measurement_available"] is False
        assert obj["median_gap_mm"] is None
        assert obj["result_status"] == "REVIEW_REQUIRED"
        assert "GEOMETRY_REVIEW_REQUIRED" in obj["rejection_reason"]
    finally:
        clear_calibration_cache()
