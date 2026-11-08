"""Offline Gemini signed-reuse tests; no network or paid model calls."""

from copy import deepcopy
import hashlib
import json
import pytest

from backend.app.core.cv.ai.signed_gemini_receipt import (
    sign_existing_semantic_result, verify_signed_semantic_receipt,
)
from backend.app.core.cv.ai.gemini_receipt_export import export_existing_gate_receipt
from backend.app.core.cv.ai.unified_vision_v1 import build_unified_result

KEY = "a-private-secret-key-that-is-long-enough-for-testing-12345"
IMAGE = b"test image bytes, not a real CCTV image"
SHA = hashlib.sha256(IMAGE).hexdigest()
NOW = 1794178800


def _gate():
    return {
        "model": "gemini-3.1-pro-preview",
        "domain_status": "PIPE_JOINT_INSPECTION",
        "pipe_visible": True, "joint_visible": True,
        "quality": "OK", "processing_allowed": True,
        "prompt_image_conflict": False,
        "suggested_joint_type": "VERTICAL_SEAM",
        "observation": "untrusted text that should not be exported",
        "operator_context": "private note that must not leave backend",
    }


def _signed():
    return sign_existing_semantic_result(
        IMAGE, _gate(), signing_secret=KEY, issued_at=NOW,
    )


def test_roundtrip_authenticates_existing_semantic_result_and_strips_notes():
    signed = _signed()
    assert signed["image_sha256"] == SHA
    assert "observation" not in json.dumps(signed)
    assert "operator_context" not in json.dumps(signed)
    result = verify_signed_semantic_receipt(
        signed, original_image_sha256=SHA, signing_secret=KEY, now=NOW + 100,
    )
    assert result["semantic_gate"]["model"] == "gemini-3.1-pro-preview"
    assert result["semantic_gate"]["processing_allowed"] is True
    assert "signature" not in result


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(image_sha256="f" * 64),
    lambda r: r["semantic_gate"].update(processing_allowed=False),
    lambda r: r["semantic_gate"].update(domain_status="UNRELATED_IMAGE"),
    lambda r: r.update(signature="0" * 64),
    lambda r: r.update(issuer="forged-user"),
])
def test_tampering_rejected(mutation):
    signed = _signed()
    mutation(signed)
    with pytest.raises(ValueError):
        verify_signed_semantic_receipt(
            signed, original_image_sha256=SHA,
            signing_secret=KEY, now=NOW + 100,
        )


def test_wrong_image_rejected_even_when_receipt_is_signed():
    with pytest.raises(ValueError):
        verify_signed_semantic_receipt(
            _signed(), original_image_sha256="b" * 64,
            signing_secret=KEY, now=NOW + 100,
        )


@pytest.mark.parametrize("now", [NOW + 31 * 86400, NOW - 62])
def test_stale_or_future_receipts_rejected(now):
    with pytest.raises(ValueError):
        verify_signed_semantic_receipt(
            _signed(), original_image_sha256=SHA,
            signing_secret=KEY, now=now,
        )


def test_no_short_signing_secret():
    with pytest.raises(ValueError):
        sign_existing_semantic_result(IMAGE, _gate(), signing_secret="weak", issued_at=NOW)


def test_signed_receipt_reuses_existing_gate_in_unified_result():
    signed = _signed()
    receipt = verify_signed_semantic_receipt(
        signed, original_image_sha256=SHA, signing_secret=KEY, now=NOW,
    )
    fusion = {
        "status": "MULTI_MODEL_REVIEW",
        "geometry": "VERTICAL_SEAM",
        "inspect_view_ready": False,
        "inspect_view_advisories": [],
        "sam2_status": "MODEL_UNAVAILABLE",
        "cv_status": "REVIEW_REQUIRED",
    }
    result = build_unified_result(
        fusion, inspect_view_payload=None,
        image_sha256=SHA, gemini_receipt=receipt,
    )
    assert result["gemini"]["status"] == "ADVISORY_DOMAIN_ACCEPTED"
    assert result["defect"] == "UNDETERMINED"
    assert result["geometry"]["physical_gap_mm"] is None


class FakeBlob:
    def __init__(self):
        self.data = None
        self.kwargs = None

    def upload_from_string(self, payload, **kwargs):
        self.data = payload
        self.kwargs = kwargs


class FakeBucket:
    def __init__(self):
        self.saved = {}

    def blob(self, name):
        obj = FakeBlob()
        self.saved[name] = obj
        return obj


def test_server_export_creates_private_receipt_without_recalling_gemini(monkeypatch):
    bucket = FakeBucket()
    uri = export_existing_gate_receipt(
        IMAGE, _gate(), signing_secret=KEY, bucket_client=bucket,
    )
    assert uri.startswith("gs://joint-inspection-510310-data/")
    assert len(bucket.saved) == 1
    blob = list(bucket.saved.values())[0]
    assert blob.kwargs["if_generation_match"] == 0
    assert b"untrusted text" not in blob.data
    receipt = json.loads(blob.data.decode())
    verified = verify_signed_semantic_receipt(
        receipt, original_image_sha256=SHA, signing_secret=KEY,
        now=receipt["issued_at"],
    )
    assert verified["semantic_gate"]["joint_visible"] is True
