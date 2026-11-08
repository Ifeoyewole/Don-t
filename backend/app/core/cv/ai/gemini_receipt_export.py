"""Opt-in backend capture of an ALREADY COMPUTED Vertex semantic result.

No second Gemini request. Never invoked unless the measurement endpoint has
confirmed the optional research token and feature flag. Stores only selected
structured gate fields, *not* CCTV bytes or original operator text.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import uuid
from typing import Any, Mapping

from backend.app.core.cv.ai.signed_gemini_receipt import sign_existing_semantic_result
from backend.app.core.cv.ai.unified_batch_manifest import BUCKET, checked_gcs_uri

DEFAULT_PREFIX = (
    f"gs://{BUCKET}/models/inspect-view/research-results/gemini-receipts"
)


def export_existing_gate_receipt(
    original_image_bytes: bytes,
    computed_gate: Mapping[str, Any],
    *,
    signing_secret: str,
    bucket_client: Any = None,
) -> str:
    """Create-only upload of an authenticated original-image-matched receipt."""
    prefix = os.getenv("JOINTINSPECT_GEMINI_RECEIPT_PREFIX", DEFAULT_PREFIX).rstrip("/")
    checked_gcs_uri(prefix + "/marker.json")
    receipt = sign_existing_semantic_result(
        original_image_bytes, computed_gate,
        signing_secret=signing_secret,
    )
    digest = receipt["image_sha256"]
    nonce = uuid.uuid4().hex
    uri = f"{prefix}/{digest[:2]}/{digest}/{receipt['issued_at']}-{nonce}.json"
    checked_gcs_uri(uri)
    if bucket_client is None:
        from google.cloud import storage
        bucket_client = storage.Client().bucket(BUCKET)
    elif callable(getattr(bucket_client, "bucket", None)):
        bucket_client = bucket_client.bucket(BUCKET)
    # No external image or human notes. Gemini structured flags are all that
    # the GPU batch evaluator is allowed to consume.
    payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    object_name = uri[len(f"gs://{BUCKET}/"):]
    bucket_client.blob(object_name).upload_from_string(
        payload, content_type="application/json", if_generation_match=0
    )
    return uri
