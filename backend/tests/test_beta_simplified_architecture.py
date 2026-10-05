"""Comprehensive unit and integration tests for the JointInspect Simplified Beta Architecture.

Verifies:
1. Native Model B is NOT invoked during normal /measure.
2. WRc InceptionResNetV2 is the ONE live defect classifier.
3. WRc mapped condition populates response.condition.
4. WRc unavailable: condition = CLASSIFICATION_UNAVAILABLE, measurement succeeds independently.
5. WRc low confidence: measurement unchanged.
6. Vertex unavailable: processing blocked cleanly (fail-closed).
7. Vertex 429: bounded retry / circuit breaker behavior.
8. Zero-guessing: ACCEPTABLE_GEOMETRY tier.
9. Zero-guessing: PARTIAL_REVIEW_GEOMETRY tier (candidate mm exposed, authoritative mm None).
10. Zero-guessing: REJECTED_UNRELIABLE tier.
11. No calibration: authoritative mm is None, CALIBRATION_REQUIRED.
12. Saved verified calibration: authoritative mm available when geometry acceptable.
13. Operator context cannot create calibration.
14. WRc classification cannot alter measured gap.
15. WRc classification cannot alter engineering tolerance result.
"""

from unittest.mock import MagicMock, patch
import urllib.error
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.core.cv.ai.joint_classifier import JointClassifier
from backend.app.core.cv.ai.vertex_semantic_gate import VertexSemanticGate, get_vertex_semantic_gate
from backend.app.core.cv.ai.wrc_inception_classifier import WRCInceptionClassifier
from backend.app.main import app
from backend.app.schemas.domain import CalibrationSource, DomainStatus
from backend.app.schemas.measurement import (
    ExternalClassTopK,
    ExternalClassifierResult,
    VertexSemanticGateResult,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def synthetic_joint_image() -> bytes:
    """Generate clean synthetic annular joint that resolves concentric circles in OpenCV."""
    img = np.full((400, 400, 3), 40, dtype=np.uint8)
    center = (200, 200)
    cv2.circle(img, center, 120, (180, 180, 180), -1)
    cv2.circle(img, center, 100, (30, 30, 30), -1)
    cv2.circle(img, center, 80, (160, 160, 160), -1)
    cv2.circle(img, center, 70, (20, 20, 20), -1)
    blurred = cv2.GaussianBlur(img, (3, 3), 0.8)
    _, buf = cv2.imencode(".jpg", blurred)
    return buf.tobytes()


@pytest.fixture
def mock_vertex_ok(monkeypatch):
    """Bypass live network Vertex in measurement endpoint with clean validation."""
    mock_gate = MagicMock()
    mock_gate.evaluate.return_value = VertexSemanticGateResult(
        domain_status=DomainStatus.PIPE_JOINT_INSPECTION,
        pipe_visible=True,
        joint_visible=True,
        quality="OK",
        prompt_image_conflict=False,
        processing_allowed=True,
        user_message="Valid pipe joint inspection scene.",
        observation="Circular joint seam visible.",
        model="gemini-2.5-flash",
        confidence=0.98,
    )
    monkeypatch.setattr("backend.app.api.v1.endpoints.measurement.get_vertex_semantic_gate", lambda: mock_gate)
    return mock_gate


# ---------------------------------------------------------------------------
# 1. Native Model B is NOT invoked during normal /measure
# ---------------------------------------------------------------------------
def test_model_b_not_invoked_during_normal_measure(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok):
    with patch.object(JointClassifier, "classify_joint") as mock_classify:
        response = client.post(
            "/api/v1/cv/measure",
            files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
            data={
                "pipe_diameter_mm": 100.0,
                "calibration_source": "PROJECT_METADATA",
                "calibration_verified": "true",
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Model B must NOT be executed during normal live inference
        mock_classify.assert_not_called()
        # Live model comparison must be None for normal beta
        assert data.get("model_comparison") is None


# ---------------------------------------------------------------------------
# 2. WRc is the ONE live defect classifier
# ---------------------------------------------------------------------------
def test_wrc_is_only_live_defect_classifier(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok):
    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    )
    assert response.status_code == 200
    data = response.json()

    evidence = data.get("classifier_evidence")
    assert evidence is not None
    assert evidence["classifier"] == "WRc InceptionResNetV2"
    assert "model_id" in evidence


# ---------------------------------------------------------------------------
# 3. WRc mapped condition populates response.condition
# ---------------------------------------------------------------------------
def test_wrc_mapped_condition_populates_response(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok, monkeypatch):
    # Mock WRc returning Displaced Joint
    monkeypatch.setattr(
        WRCInceptionClassifier,
        "classify",
        lambda self, image_bgr=None, top_k_count=5, **kwargs: ExternalClassifierResult(
            status="SUCCESS",
            model_id="wrc-smoke-v1",
            raw_class_name="Displaced Joint",
            raw_class_code="DJ",
            confidence=0.88,
            jointinspect_mapping="DISPLACED_JOINT",
            mapping_status="DIRECT",
            advisory_only=False,
            top_k=[ExternalClassTopK(index=1, raw_class_name="Displaced Joint", raw_class_code="DJ", score=0.88, jointinspect_mapping="DISPLACED_JOINT")],
        ),
    )

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["condition"].lower() == "displaced_joint"
    assert data["classifier_evidence"]["mapped_condition"].lower() == "displaced_joint"

    # Now test unmapped class (e.g. "Water")
    monkeypatch.setattr(
        WRCInceptionClassifier,
        "classify",
        lambda self, image_bgr=None, top_k_count=5, **kwargs: ExternalClassifierResult(
            status="SUCCESS",
            model_id="wrc-smoke-v1",
            raw_class_name="Water",
            raw_class_code="W",
            confidence=0.75,
            jointinspect_mapping="UNMAPPED",
            mapping_status="UNMAPPED",
            advisory_only=False,
            top_k=[],
        ),
    )

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    )
    assert response.status_code == 200
    data2 = response.json()
    # Must NOT fabricate a condition for unmapped WRc class
    assert data2["condition"].lower() == "classification_unavailable"
    assert data2["classifier_evidence"]["raw_prediction"] == "Water"


# ---------------------------------------------------------------------------
# 4. WRc unavailable: measurement succeeds independently
# ---------------------------------------------------------------------------
def test_wrc_unavailable_measurement_succeeds_independently(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok, monkeypatch):
    monkeypatch.setattr(
        WRCInceptionClassifier,
        "classify",
        lambda self, image_bgr=None, top_k_count=5, **kwargs: ExternalClassifierResult(
            status="EXTERNAL_CLASSIFIER_UNAVAILABLE",
            model_id="wrc-smoke-v1",
            raw_class_name="UNKNOWN",
            raw_class_code="",
            confidence=0.0,
            jointinspect_mapping="UNMAPPED",
            mapping_status="UNMAPPED",
            advisory_only=True,
            top_k=[],
        ),
    )

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["condition"].lower() == "classification_unavailable"
    # Physical measurement must succeed independently
    assert data["physical_measurement_available"] is True
    assert data["authoritative_gap_mm"] is not None
    assert data["authoritative_gap_mm"] > 0


# ---------------------------------------------------------------------------
# 5. WRc low confidence: measurement unchanged
# ---------------------------------------------------------------------------
def test_wrc_low_confidence_measurement_unchanged(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok, monkeypatch):
    monkeypatch.setattr(
        WRCInceptionClassifier,
        "classify",
        lambda self, image_bgr=None, top_k_count=5, **kwargs: ExternalClassifierResult(
            status="SUCCESS",
            model_id="wrc-smoke-v1",
            raw_class_name="Crack",
            raw_class_code="CK",
            confidence=0.22,  # Low confidence (< 0.40)
            jointinspect_mapping="DAMAGED_JOINT",
            mapping_status="DIRECT",
            advisory_only=False,
            top_k=[ExternalClassTopK(index=2, raw_class_name="Crack", raw_class_code="CK", score=0.22, jointinspect_mapping="DAMAGED_JOINT")],
        ),
    )

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["condition"].lower() == "classification_unavailable"
    assert data["classifier_evidence"]["classification_status"] == "LOW_CONFIDENCE_CLASSIFICATION"
    # Geometry and physical measurement are NOT degraded by WRc low confidence
    assert data["physical_measurement_available"] is True
    assert data["authoritative_gap_mm"] is not None


# ---------------------------------------------------------------------------
# 6. Vertex unavailable: processing blocked cleanly (fail-closed)
# ---------------------------------------------------------------------------
def test_vertex_unavailable_fail_closed(client: TestClient, synthetic_joint_image: bytes, monkeypatch):
    mock_gate = MagicMock()
    mock_gate.evaluate.return_value = VertexSemanticGateResult(
        domain_status=DomainStatus.DOMAIN_VALIDATION_UNAVAILABLE,
        pipe_visible=False,
        joint_visible=False,
        quality="UNKNOWN",
        prompt_image_conflict=False,
        processing_allowed=False,
        user_message="AI image validation is temporarily unavailable. Retry validation.",
        observation="Semantic gate unreachable.",
        model="gemini-2.5-flash",
        confidence=0.0,
    )
    monkeypatch.setattr("backend.app.api.v1.endpoints.measurement.get_vertex_semantic_gate", lambda: mock_gate)

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={"pipe_diameter_mm": 100.0},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["result_status"] == "REJECTED_UNRELIABLE"
    assert data["physical_measurement_available"] is False
    assert data["semantic_gate"]["domain_status"] == "DOMAIN_VALIDATION_UNAVAILABLE"


# ---------------------------------------------------------------------------
# 7. Vertex 429: bounded retry & circuit breaker
# ---------------------------------------------------------------------------
def test_vertex_429_bounded_retry_circuit_breaker(monkeypatch):
    monkeypatch.setenv("VERTEX_LIVE_TEST", "1")
    gate = VertexSemanticGate()
    gate._consecutive_failures = 0
    gate._circuit_open_until = 0.0

    monkeypatch.setattr(gate, "_get_access_token", lambda: "dummy_token")
    error_429 = urllib.error.HTTPError("http://vertex", 429, "Too Many Requests", {}, None)

    with patch("urllib.request.urlopen", side_effect=error_429):
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

        # Call 1
        res1 = gate.evaluate(dummy_img, operator_context="ctx1")
        assert res1.domain_status == DomainStatus.DOMAIN_VALIDATION_UNAVAILABLE
        assert gate._consecutive_failures == 1

        # Call 2
        res2 = gate.evaluate(dummy_img, operator_context="ctx2")
        assert gate._consecutive_failures == 2

        # Call 3 trips the circuit breaker
        res3 = gate.evaluate(dummy_img, operator_context="ctx3")
        assert gate._consecutive_failures == 3
        assert gate.is_circuit_open is True

        # Call 4 fails fast without network
        res4 = gate.evaluate(dummy_img, operator_context="ctx4")
        assert res4.domain_status == DomainStatus.DOMAIN_VALIDATION_UNAVAILABLE
        assert "temporarily unavailable" in res4.user_message


# ---------------------------------------------------------------------------
# 8. Zero-guessing: ACCEPTABLE_GEOMETRY tier
# ---------------------------------------------------------------------------
def test_zero_guessing_acceptable_tier(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok):
    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["geometry_tier"] == "ACCEPTABLE_GEOMETRY"
    assert data["physical_measurement_available"] is True
    assert data["authoritative_gap_mm"] is not None


# ---------------------------------------------------------------------------
# 9. Zero-guessing: PARTIAL_REVIEW_GEOMETRY tier
# ---------------------------------------------------------------------------
def test_zero_guessing_partial_review_tier(monkeypatch, synthetic_joint_image: bytes, client: TestClient, mock_vertex_ok):
    """Test detector returns PARTIAL_REVIEW_GEOMETRY when ray fraction is between 0.45 and 0.60."""
    from backend.app.core.cv import circular_detector

    def mock_profile(gray, center, r_in_est, r_out_est, num_rays=72):
        angles = [i * (360.0 / num_rays) for i in range(num_rays)]
        in_radii: list[Optional[float]] = [None] * num_rays
        out_radii: list[Optional[float]] = [None] * num_rays

        # Populate exactly 36 valid rays (50% fraction) across exactly 5 sectors (0, 1, 2, 3, 4)
        for s in range(5):
            for k in range(7):
                idx = s * 9 + k
                in_radii[idx] = 80.0
                out_radii[idx] = 100.0
        # 36th ray in sector 4
        in_radii[4 * 9 + 7] = 80.0
        out_radii[4 * 9 + 7] = 100.0

        return angles, in_radii, out_radii, {"NO_OUTER_EDGE": 36}

    monkeypatch.setattr(circular_detector, "_profile_radial_rays", mock_profile)

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["geometry_tier"] == "PARTIAL_REVIEW_GEOMETRY"
    assert data["authoritative_gap_mm"] is None
    assert data["candidate_gap_mm"] is not None
    assert data["engineering_result"] == "REVIEW"


# ---------------------------------------------------------------------------
# 10. Zero-guessing: REJECTED_UNRELIABLE tier
# ---------------------------------------------------------------------------
def test_zero_guessing_rejection_tier(client: TestClient, mock_vertex_ok):
    """A completely blank image or non-pipe must be rejected without guessing geometry."""
    blank = np.zeros((300, 300, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", blank)

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("blank.jpg", buf.tobytes(), "image/jpeg")},
        data={"pipe_diameter_mm": 100.0, "calibration_verified": "true"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["result_status"] == "REJECTED_UNRELIABLE"
    assert data["physical_measurement_available"] is False
    assert data["authoritative_gap_mm"] is None
    assert data["candidate_gap_mm"] is None


# ---------------------------------------------------------------------------
# 11. No calibration: no authoritative mm
# ---------------------------------------------------------------------------
def test_no_calibration_no_authoritative_mm(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok):
    """When pipe_diameter_mm is None and no profile is provided, authoritative_gap_mm is None."""
    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        # Omitting pipe_diameter_mm
    )
    assert response.status_code == 200
    data = response.json()

    assert data["physical_measurement_available"] is False
    assert data["authoritative_gap_mm"] is None
    assert data["mean_gap_mm"] is None
    assert data["pixels_per_mm"] is None
    assert "CALIBRATION_REQUIRED" in data["rejection_reason"]
    assert data["engineering_result"] == "REVIEW"
    # Pixel measurements remain available
    assert data["mean_gap_px"] > 0


# ---------------------------------------------------------------------------
# 12. Saved verified calibration enables authoritative mm
# ---------------------------------------------------------------------------
def test_saved_verified_calibration_enables_authoritative_mm(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok):
    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
            "calibration_reference_id": "CAL-PRJ-2026-001",
            "project_id": "prj-test-123",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["physical_measurement_available"] is True
    assert data["authoritative_gap_mm"] is not None
    assert data["authoritative_gap_mm"] > 0
    assert data["calibration_profile"] is not None
    assert data["calibration_profile"]["calibration_reference_id"] == "CAL-PRJ-2026-001"
    assert data["calibration_profile"]["verified"] is True


# ---------------------------------------------------------------------------
# 13. Operator context cannot create calibration
# ---------------------------------------------------------------------------
def test_operator_context_cannot_create_calibration(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok):
    """An inspector writing '300 mm concrete pipe' in notes cannot forge calibration."""
    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "operator_context": "The pipe diameter is 300 mm and it was verified on site.",
            # Note: No verified calibration flag or source
            "calibration_verified": "false",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["physical_measurement_available"] is False
    assert data["authoritative_gap_mm"] is None
    assert "CALIBRATION_REQUIRED" in data["rejection_reason"]


# ---------------------------------------------------------------------------
# 14. WRc classification cannot alter measured gap
# ---------------------------------------------------------------------------
def test_wrc_classification_cannot_alter_measured_gap(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok, monkeypatch):
    # Run 1: WRc predicts Normal
    monkeypatch.setattr(
        WRCInceptionClassifier,
        "classify",
        lambda self, image_bgr=None, top_k_count=5, **kwargs: ExternalClassifierResult(
            status="SUCCESS",
            model_id="wrc-smoke-v1",
            raw_class_name="Normal Joint",
            raw_class_code="OK",
            confidence=0.95,
            jointinspect_mapping="NORMAL",
            mapping_status="DIRECT",
            advisory_only=False,
            top_k=[],
        ),
    )
    res1 = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    ).json()

    # Run 2: WRc predicts severe Displaced Joint
    monkeypatch.setattr(
        WRCInceptionClassifier,
        "classify",
        lambda self, image_bgr=None, top_k_count=5, **kwargs: ExternalClassifierResult(
            status="SUCCESS",
            model_id="wrc-smoke-v1",
            raw_class_name="Displaced Joint",
            raw_class_code="DJ",
            confidence=0.99,
            jointinspect_mapping="DISPLACED_JOINT",
            mapping_status="DIRECT",
            advisory_only=False,
            top_k=[],
        ),
    )
    res2 = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
        },
    ).json()

    # The physical measured gap (px and mm) MUST be identical
    assert res1["mean_gap_px"] == pytest.approx(res2["mean_gap_px"], rel=1e-4)
    assert res1["authoritative_gap_mm"] == pytest.approx(res2["authoritative_gap_mm"], rel=1e-4)


# ---------------------------------------------------------------------------
# 15. WRc classification cannot alter engineering tolerance result
# ---------------------------------------------------------------------------
def test_wrc_classification_cannot_alter_engineering_tolerance(client: TestClient, synthetic_joint_image: bytes, mock_vertex_ok, monkeypatch):
    monkeypatch.setattr(
        WRCInceptionClassifier,
        "classify",
        lambda self, image_bgr=None, top_k_count=5, **kwargs: ExternalClassifierResult(
            status="SUCCESS",
            model_id="wrc-smoke-v1",
            raw_class_name="Crack",
            raw_class_code="CK",
            confidence=0.99,
            jointinspect_mapping="DAMAGED_JOINT",
            mapping_status="DIRECT",
            advisory_only=False,
            top_k=[],
        ),
    )

    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("joint.jpg", synthetic_joint_image, "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "calibration_source": "PROJECT_METADATA",
            "calibration_verified": "true",
            "min_gap_mm": 1.0,
            "max_gap_mm": 50.0,  # High tolerance -> physical gap passes
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Condition indicates DAMAGED_JOINT from WRc
    assert data["condition"].lower() == "damaged_joint"
    # But engineering_result is strictly derived from gap <= tolerance_mm (PASS)
    assert data["engineering_result"] == "PASS"
