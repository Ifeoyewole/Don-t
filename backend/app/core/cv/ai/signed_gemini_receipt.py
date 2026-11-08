"""Authenticate reuse of a *previously executed* Gemini semantic-gate decision.

The backend must mint receipts from its actual VertexSemanticGateResult and
original image bytes, not from client-supplied JSON. The research GPU worker
verifies HMAC with a separately provisioned shared Secret Manager value.
This helper never calls Gemini or uploads media.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Any, Mapping

ISSUER = "jointinspect-backend-vertex-semantic-gate"
SCHEMA = "jointinspect-gemini-receipt-v1"
SEMANTIC_FIELDS = frozenset({
    "model", "domain_status", "pipe_visible", "joint_visible", "quality",
    "processing_allowed", "prompt_image_conflict", "suggested_joint_type",
})
MAX_AGE_SECONDS = 30 * 86400


def _secret_bytes(secret: str | bytes) -> bytes:
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("A server-side receipt signing secret of at least 32 bytes is required")
    return secret


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("utf-8")


def _original_image_digest(image_bytes: bytes) -> str:
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("Nonempty original source image bytes required")
    return hashlib.sha256(image_bytes).hexdigest()


def _normalize_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(gate, Mapping):
        raise ValueError("Expected server-computed semantic gate mapping")
    selected = {k: gate.get(k) for k in SEMANTIC_FIELDS}
    if not isinstance(selected["model"], str):
        raise ValueError("Semantic model identifier missing")
    if not isinstance(selected["domain_status"], str):
        raise ValueError("Semantic domain status missing")
    for k in ("pipe_visible", "joint_visible", "processing_allowed", "prompt_image_conflict"):
        if type(selected[k]) is not bool:
            raise ValueError(f"Semantic field {k} must be boolean")
    if selected["quality"] not in ("OK", "BLURRY", "UNDEREXPOSED", "OVEREXPOSED", "DEGRADED"):
        raise ValueError("Invalid semantic quality")
    if selected["suggested_joint_type"] not in (
        None, "VERTICAL_SEAM", "HORIZONTAL_SEAM", "CIRCULAR_OPENING"
    ):
        raise ValueError("Invalid semantic geometry hint")
    return selected


def sign_existing_semantic_result(
    original_image_bytes: bytes,
    semantic_gate: Mapping[str, Any],
    *,
    signing_secret: str | bytes,
    issued_at: int | None = None,
) -> dict[str, Any]:
    """Sign backend-origin semantic output, without issuing a Gemini request."""
    key = _secret_bytes(signing_secret)
    if issued_at is None:
        issued_at = int(datetime.now(timezone.utc).timestamp())
    if not isinstance(issued_at, int) or isinstance(issued_at, bool) or issued_at < 0:
        raise ValueError("Invalid receipt issue time")
    envelope = {
        "schema": SCHEMA,
        "issuer": ISSUER,
        "issued_at": issued_at,
        "image_sha256": _original_image_digest(original_image_bytes),
        "semantic_gate": _normalize_gate(semantic_gate),
    }
    return {
        **envelope,
        "signature": hmac.new(key, _canonical(envelope), hashlib.sha256).hexdigest(),
    }


def verify_signed_semantic_receipt(
    receipt: Mapping[str, Any],
    *,
    original_image_sha256: str,
    signing_secret: str | bytes,
    now: int | None = None,
    max_age_seconds: int = MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Return the existing compatible gate shape, or fail closed.

    Signature is required; source image SHA and receipt age are checked too.
    Copies only the fields needed by Unified Vision v1.
    """
    key = _secret_bytes(signing_secret)
    if not isinstance(receipt, Mapping) or set(receipt) != {
        "schema", "issuer", "issued_at", "image_sha256", "semantic_gate", "signature"
    }:
        raise ValueError("Unsigned or malformed Gemini receipt")
    if receipt.get("schema") != SCHEMA or receipt.get("issuer") != ISSUER:
        raise ValueError("Untrusted receipt issuer or schema")
    if (not isinstance(original_image_sha256, str) or
            len(original_image_sha256) != 64 or
            any(c not in "0123456789abcdef" for c in original_image_sha256)):
        raise ValueError("Invalid original image digest")
    if receipt.get("image_sha256") != original_image_sha256:
        raise ValueError("Gemini receipt belongs to another image")
    if now is None:
        now = int(datetime.now(timezone.utc).timestamp())
    issued_at = receipt.get("issued_at")
    if (type(issued_at) is not int or type(now) is not int
            or not 1 <= max_age_seconds <= MAX_AGE_SECONDS
            or issued_at > now + 60 or issued_at < now - max_age_seconds):
        raise ValueError("Gemini receipt is stale or has an invalid timestamp")
    signature = receipt.get("signature")
    if (not isinstance(signature, str) or len(signature) != 64
            or any(c not in "0123456789abcdef" for c in signature)):
        raise ValueError("Invalid Gemini receipt signature")
    envelope = {k: v for k, v in receipt.items() if k != "signature"}
    expected = hmac.new(key, _canonical(envelope), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Gemini receipt signature verification failed")
    clean_gate = _normalize_gate(receipt["semantic_gate"])
    return {"image_sha256": original_image_sha256, "semantic_gate": clean_gate}
