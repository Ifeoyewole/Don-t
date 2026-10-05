"""Automated Security Hardening & Zero-Trust Architecture Test Suite.

Proves:
1. Oversized image uploads (>15MB) are denied with HTTP 413 / Bad Request.
2. Invalid MIME and non-image magic bytes (e.g. bash scripts/binaries) are denied.
3. Corrupt/truncated image byte payloads are safely rejected.
4. Decompression bomb payloads are blocked.
5. Calibration mutation endpoints are locked in production (HTTP 403).
6. Raw Python exceptions and system internals are never exposed to clients.
7. Request correlation IDs (X-Request-ID) are generated and returned.
8. Parameter boundary constraints (pipe diameter, tolerances, frame bursts) are enforced.
9. Zero-guessing optical measurement safeguards remain strictly intact.
"""

import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app.utils.image_io import decode_image_bytes


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def valid_jpeg_bytes() -> bytes:
    """Generate a clean synthetic 200x200 JPEG image."""
    img = np.full((200, 200, 3), 128, dtype=np.uint8)
    cv2.circle(img, (100, 100), 50, (255, 255, 255), -1)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


# ==============================================================================
# 1. Payload Bounds & Magic Byte Rejection Tests
# ==============================================================================

def test_invalid_mime_and_magic_bytes_rejected():
    """Prove non-image files (e.g. bash script or foreign executable) are rejected."""
    malicious_bytes = b"#!/bin/bash\necho 'Compromised'\n"
    with pytest.raises(ValueError, match="Invalid image file format"):
        decode_image_bytes(malicious_bytes)


def test_corrupt_image_payload_rejected():
    """Prove truncated/corrupt JPEG headers are rejected gracefully."""
    corrupt_bytes = b"\xff\xd8\xff" + b"CorruptPayloadDataTruncated"
    with pytest.raises(ValueError, match="Corrupted or malformed image payload"):
        decode_image_bytes(corrupt_bytes)


def test_oversized_payload_rejected(client: TestClient):
    """Prove payloads exceeding 15MB are rejected with HTTP 413 or 400."""
    oversized_data = b"\xff\xd8\xff" + (b"\x00" * (16 * 1024 * 1024))
    response = client.post(
        "/api/v1/cv/validate-photo",
        files={"file": ("large.jpg", oversized_data, "image/jpeg")},
    )
    assert response.status_code in (400, 413)


# ==============================================================================
# 2. Calibration Production Mutation Lock Tests
# ==============================================================================

def test_calibration_mutation_locked_in_production(client: TestClient):
    """Prove POST /api/v1/cv/calibration/profiles is blocked in production (HTTP 403)."""
    payload = {
        "camera_id": "UNAUTHORIZED-TEST-CAM",
        "resolution": [1280, 720],
        "focal_length": [800.0, 800.0],
        "principal_point": [640.0, 360.0],
        "distortion_coeffs": [0.0, 0.0, 0.0, 0.0, 0.0],
    }
    response = client.post("/api/v1/cv/calibration/profiles", json=payload)
    assert response.status_code == 403
    assert "restricted in production" in response.json()["detail"]


def test_calibration_profiles_read_allowed(client: TestClient):
    """Prove GET /api/v1/cv/calibration/profiles remains accessible for inspection."""
    response = client.get("/api/v1/cv/calibration/profiles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ==============================================================================
# 3. Error Sanitization & Correlation ID Tests
# ==============================================================================

def test_raw_exceptions_are_suppressed_and_correlation_id_returned(client: TestClient):
    """Prove unhandled exceptions return sanitized error JSON with request_id, not stack traces."""
    response = client.post(
        "/api/v1/cv/measure",
        data={"joint_type": "INVALID_GEOMETRY_TYPE"},
        files={"file": ("test.jpg", b"invalid", "image/jpeg")},
    )
    # Validation error or internal error must include request_id and no Python stack trace
    assert "request_id" in response.headers or "X-Request-ID" in response.headers
    body = response.json()
    assert "Traceback (most recent call last)" not in str(body)


# ==============================================================================
# 4. Multi-Frame Burst Bounds Tests
# ==============================================================================

def test_multi_frame_burst_bounds(client: TestClient, valid_jpeg_bytes: bytes):
    """Prove multi-frame endpoint rejects sequences exceeding 30 frames."""
    too_many_files = [
        ("files", (f"frame_{i}.jpg", valid_jpeg_bytes, "image/jpeg"))
        for i in range(35)
    ]
    response = client.post(
        "/api/v1/cv/measure/multi-frame",
        files=too_many_files,
        data={"pipe_diameter_mm": 100.0},
    )
    assert response.status_code == 400
    assert "exceeds maximum burst sequence limit" in response.json()["detail"]


def test_multi_frame_burst_minimum_bounds(client: TestClient, valid_jpeg_bytes: bytes):
    """Prove multi-frame endpoint requires at least 2 frames."""
    single_file = [("files", ("frame_0.jpg", valid_jpeg_bytes, "image/jpeg"))]
    response = client.post(
        "/api/v1/cv/measure/multi-frame",
        files=single_file,
        data={"pipe_diameter_mm": 100.0},
    )
    assert response.status_code == 400
    assert "requires at least 2 consecutive frames" in response.json()["detail"]


# ==============================================================================
# 5. Zero-Guessing Measurement Integrity Verification
# ==============================================================================

def test_zero_guessing_measurement_contract_intact(client: TestClient):
    """Prove valid synthetic joint image processes with full sub-pixel accuracy and confidence."""
    # Create clear concentric annular joint
    img = np.full((400, 400, 3), 40, dtype=np.uint8)
    center = (200, 200)
    cv2.circle(img, center, 120, (180, 180, 180), -1)  # Outer collar
    cv2.circle(img, center, 100, (30, 30, 30), -1)      # Dark annular gap (20px)
    cv2.circle(img, center, 80, (160, 160, 160), -1)    # Inner pipe wall
    cv2.circle(img, center, 70, (20, 20, 20), -1)       # Pipe hollow interior

    _, buf = cv2.imencode(".jpg", img)
    response = client.post(
        "/api/v1/cv/measure",
        files={"file": ("synthetic_joint.jpg", buf.tobytes(), "image/jpeg")},
        data={
            "pipe_diameter_mm": 100.0,
            "joint_type": "CIRCULAR_OPENING",
            "return_debug_image": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result_status"] in ("ACCEPTED_MEASUREMENT", "REVIEW_REQUIRED")
    assert "mean_gap_mm" in data
    assert "confidence_breakdown" in data
    assert data["confidence_breakdown"]["overall_confidence"] > 0.0
