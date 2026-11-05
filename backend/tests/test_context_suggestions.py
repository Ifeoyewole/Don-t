"""Preflight suggestions never fabricate engineering or calibration authority."""

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.core.cv.ai.vertex_semantic_gate import get_vertex_semantic_gate
from backend.app.main import app
from backend.app.schemas.domain import DomainStatus, JointType
from backend.app.schemas.measurement import VertexSemanticGateResult


@pytest.fixture
def jpeg() -> bytes:
    rng = np.random.default_rng(41)
    image = rng.integers(75, 190, (320, 320, 3), dtype=np.uint8)
    cv2.rectangle(image, (136, 0), (178, 319), (22, 22, 22), -1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_suggests_geometry_but_never_verifies_metadata(monkeypatch, jpeg):
    gate = get_vertex_semantic_gate()
    monkeypatch.setattr(gate, "evaluate", lambda image_bgr, operator_context=None: VertexSemanticGateResult(
        domain_status=DomainStatus.PIPE_JOINT_INSPECTION,
        pipe_visible=True,
        joint_visible=True,
        quality="OK",
        processing_allowed=True,
        prompt_image_conflict=False,
        user_message="Pipe joint visible",
        observation="Two concrete-like edges flank a dark strip.",
        suggested_joint_type=JointType.VERTICAL_SEAM,
        suggested_inspection_context="Two visible rough boundaries flank a dark strip; review possible separation.",
        possible_gap_visible=True,
        model="gemini-3.1-pro-preview",
    ))
    response = TestClient(app).post(
        "/api/v1/cv/context-suggestions",
        files={"file": ("photo.jpg", jpeg, "image/jpeg")},
        data={"metadata_pipe_diameter_mm": "900", "metadata_source": "MANHOLE_METADATA"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_joint_type"] == "VERTICAL_SEAM"
    assert data["possible_gap_visible"] is True
    assert data["calibration"]["pipe_diameter_mm"] == 900
    assert data["calibration"]["source"] == "MANHOLE_METADATA"
    assert data["calibration"]["verified"] is False
    assert data["calibration"]["calibration_reference_id"] is None
    assert data["review_required"] is True
    assert "authoritative_gap_mm" not in data


def test_unrelated_scene_blocks_context_but_preserves_unverified_metadata(monkeypatch, jpeg):
    gate = get_vertex_semantic_gate()
    monkeypatch.setattr(gate, "evaluate", lambda image_bgr, operator_context=None: VertexSemanticGateResult(
        domain_status=DomainStatus.UNRELATED_IMAGE,
        pipe_visible=False,
        joint_visible=False,
        quality="OK",
        processing_allowed=False,
        prompt_image_conflict=False,
        user_message="Unrelated scene",
        observation="No pipe interior",
        suggested_joint_type=JointType.VERTICAL_SEAM,
        suggested_inspection_context="Potential joint",
        possible_gap_visible=True,
        model="gemini-3.1-pro-preview",
    ))
    response = TestClient(app).post(
        "/api/v1/cv/context-suggestions",
        files={"file": ("photo.jpg", jpeg, "image/jpeg")},
        data={"metadata_pipe_diameter_mm": "900"},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["processing_allowed"] is False
    assert data["suggested_joint_type"] is None
    assert data["suggested_inspection_context"] is None
    assert data["possible_gap_visible"] is None
    assert data["calibration"]["verified"] is False


def test_image_cannot_infer_diameter(monkeypatch, jpeg):
    gate = get_vertex_semantic_gate()
    monkeypatch.setattr(gate, "evaluate", lambda image_bgr, operator_context=None: VertexSemanticGateResult(
        domain_status=DomainStatus.PIPE_JOINT_INSPECTION,
        pipe_visible=True,
        joint_visible=True,
        quality="OK",
        processing_allowed=True,
        prompt_image_conflict=False,
        user_message="Pipe joint visible",
        observation="Visible seam",
        model="gemini-3.1-pro-preview",
    ))
    response = TestClient(app).post(
        "/api/v1/cv/context-suggestions",
        files={"file": ("photo.jpg", jpeg, "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["calibration"]["pipe_diameter_mm"] is None
    assert response.json()["calibration"]["verified"] is False


def test_invalid_file_rejected():
    response = TestClient(app).post(
        "/api/v1/cv/context-suggestions",
        files={"file": ("bad.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
