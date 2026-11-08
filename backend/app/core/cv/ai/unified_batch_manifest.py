"""Strict, offline validation for Unified Vision v1 GCS batch research manifests.

No network, model loading, licence grants, or GCS side effects. Source
labels and quarantine images are never silently promoted to ground truth.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

BUCKET = "joint-inspection-510310-data"
MAX_FRAMES = 100
MAX_MANIFEST_BYTES = 256 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
_GEOMETRIES = frozenset({"VERTICAL_SEAM", "HORIZONTAL_SEAM", "CIRCULAR_OPENING"})
_RIGHTS = frozenset({"RESEARCH_QUARANTINE", "RIGHTS_REVIEWED_RESEARCH"})
_LABEL_STATUS = frozenset({"UNVERIFIED_SOURCE_LABEL", "REVIEWED_GROUND_TRUTH"})
_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
_HEX_SHA = re.compile(r"^[a-f0-9]{64}$")
_FRAME_FIELDS = frozenset({
    "frame_id", "image_uri", "image_sha256", "geometry", "roi",
    "source_family", "source_id", "rights_status", "annotation_status",
    "source_label", "reviewed_label", "review_id",
    "gemini_receipt_uri", "gemini_receipt_sha256",
})


def checked_gcs_uri(uri: Any) -> str:
    """Permit only data in the configured project bucket, not arbitrary GCS."""
    if not isinstance(uri, str) or not uri.startswith(f"gs://{BUCKET}/"):
        raise ValueError("GCS URI must use the project data bucket")
    key = uri[len(f"gs://{BUCKET}/"):]
    if (not key or len(key) > 1024 or any(ord(c) < 32 or ord(c) == 127 for c in key)
            or any(part in ("", ".", "..") for part in key.split("/"))
            or "\\" in key or "?" in key or "#" in key):
        raise ValueError("Malformed or unsafe project GCS URI")
    return uri


def checked_sha(value: Any) -> str:
    if not isinstance(value, str) or not _HEX_SHA.fullmatch(value):
        raise ValueError("Expected lowercase 64-hex SHA-256")
    return value


def _nonempty(value: Any, field: str, *, limit: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be a nonempty string <= {limit} characters")
    return value.strip()


def validate_batch_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Reject malformed manifests *before* starting any GPU or GCS processing."""
    if not isinstance(manifest, Mapping):
        raise ValueError("Manifest must be a JSON object")
    if set(manifest) != {"schema_version", "manifest_id", "frames"}:
        raise ValueError("Manifest needs schema_version, manifest_id, frames only")
    if manifest["schema_version"] != "1.0":
        raise ValueError("Unsupported manifest schema version")
    manifest_id = manifest["manifest_id"]
    if not isinstance(manifest_id, str) or not _SAFE_ID.fullmatch(manifest_id):
        raise ValueError("Invalid manifest_id")
    frames = manifest["frames"]
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"Manifest needs 1–{MAX_FRAMES} frames")

    clean = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for index, item in enumerate(frames):
        if not isinstance(item, dict) or set(item) - _FRAME_FIELDS:
            raise ValueError(f"Invalid fields on frame {index}")
        required = {
            "frame_id", "image_uri", "image_sha256", "geometry", "roi",
            "source_family", "source_id", "rights_status", "annotation_status",
        }
        if not required <= set(item):
            raise ValueError(f"Frame {index} missing required fields")
        fid = item["frame_id"]
        if not isinstance(fid, str) or not _SAFE_ID.fullmatch(fid) or fid in seen_ids:
            raise ValueError(f"Invalid or repeated frame_id at index {index}")
        seen_ids.add(fid)
        digest = checked_sha(item["image_sha256"])
        if digest in seen_hashes:
            raise ValueError("Exact duplicate frames are not allowed in one batch")
        seen_hashes.add(digest)
        image_uri = checked_gcs_uri(item["image_uri"])
        if item["geometry"] not in _GEOMETRIES:
            raise ValueError(f"Unsupported geometry on {fid}")
        roi = item["roi"]
        if (not isinstance(roi, list) or len(roi) != 4
                or any(type(v) is not int for v in roi)
                or not (0 <= roi[0] < roi[2] and 0 <= roi[1] < roi[3])
                or roi[2] - roi[0] < 24 or roi[3] - roi[1] < 24):
            raise ValueError(f"Invalid inspector ROI on {fid}")
        rights = item["rights_status"]
        if rights not in _RIGHTS:
            raise ValueError(f"Rights status required for {fid}")
        annotation = item["annotation_status"]
        if annotation not in _LABEL_STATUS:
            raise ValueError(f"Annotation review status required for {fid}")
        clean_item = dict(item)
        clean_item["source_family"] = _nonempty(item["source_family"], "source_family")
        clean_item["source_id"] = _nonempty(item["source_id"], "source_id")
        if annotation == "REVIEWED_GROUND_TRUTH":
            clean_item["reviewed_label"] = _nonempty(
                item.get("reviewed_label"), "reviewed_label", limit=80
            )
            clean_item["review_id"] = _nonempty(
                item.get("review_id"), "review_id", limit=128
            )
        elif item.get("reviewed_label") or item.get("review_id"):
            raise ValueError("Unreviewed source labels cannot be submitted as ground truth")
        if "source_label" in item and item["source_label"] is not None:
            clean_item["source_label"] = _nonempty(item["source_label"], "source_label", limit=128)
        has_receipt = bool(item.get("gemini_receipt_uri"))
        has_digest = bool(item.get("gemini_receipt_sha256"))
        if has_receipt != has_digest:
            raise ValueError(f"Gemini receipt URI and hash required together on {fid}")
        if has_receipt:
            clean_item["gemini_receipt_uri"] = checked_gcs_uri(item["gemini_receipt_uri"])
            clean_item["gemini_receipt_sha256"] = checked_sha(item["gemini_receipt_sha256"])
        clean.append(clean_item)

    # Rights review is distinct from annotation review: both are recorded,
    # neither is inferred from the source's own labels.
    return {"schema_version": "1.0", "manifest_id": manifest_id, "frames": clean}
