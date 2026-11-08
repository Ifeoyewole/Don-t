"""Offline manifest/provenance tests for bounded Vertex AI research batches."""

from copy import deepcopy

import pytest

from backend.app.core.cv.ai.unified_batch_manifest import (
    checked_gcs_uri, validate_batch_manifest,
)

ROOT = "gs://joint-inspection-510310-data"


def _manifest():
    return {
        "schema_version": "1.0",
        "manifest_id": "research-first-frames",
        "frames": [
            {
                "frame_id": "frame_1",
                "image_uri": ROOT + "/quarantine/source/1.png",
                "image_sha256": "a" * 64,
                "geometry": "VERTICAL_SEAM",
                "roi": [20, 10, 80, 160],
                "source_family": "source-family-1",
                "source_id": "source-1",
                "rights_status": "RESEARCH_QUARANTINE",
                "annotation_status": "UNVERIFIED_SOURCE_LABEL",
                "source_label": "Utility intrusion",
            },
        ],
    }


def test_quarantine_is_research_only_not_implicitly_ground_truth():
    value = validate_batch_manifest(_manifest())
    frame = value["frames"][0]
    assert frame["rights_status"] == "RESEARCH_QUARANTINE"
    assert frame["annotation_status"] == "UNVERIFIED_SOURCE_LABEL"
    assert "reviewed_label" not in frame


def test_reviewed_ground_truth_is_separate_from_rights_review():
    value = _manifest()
    frame = value["frames"][0]
    frame["annotation_status"] = "REVIEWED_GROUND_TRUTH"
    frame["reviewed_label"] = "JOINT_DISPLACEMENT"
    frame["review_id"] = "inspection-review-2026-001"
    assert validate_batch_manifest(value)["frames"][0]["reviewed_label"] == "JOINT_DISPLACEMENT"


@pytest.mark.parametrize("change", [
    ("geometry", "OPEN_JOINT"),
    ("roi", [5, 5, 5, 44]),
    ("roi", [5, 5, 15, 44]),
    ("roi", [5.0, 5, 50, 50]),
    ("roi", [True, 5, 50, 50]),
    ("rights_status", "COMMERCIAL_APPROVED"),
    ("annotation_status", "REVIEWED"),
    ("image_sha256", "Z" * 64),
    ("frame_id", "../escape"),
    ("image_uri", "gs://foreign-bucket/photo.png"),
    ("image_uri", ROOT + "/../photos.png"),
    ("image_uri", ROOT + "/a\tbad/photo.png"),
])
def test_invalid_frame_fields_fail_before_gpu(change):
    key, value = change
    manifest = _manifest()
    manifest["frames"][0][key] = value
    with pytest.raises(ValueError):
        validate_batch_manifest(manifest)


def test_receipt_reference_requires_matching_file_sha():
    m = _manifest()
    m["frames"][0]["gemini_receipt_uri"] = ROOT + "/gemini/r1.json"
    with pytest.raises(ValueError):
        validate_batch_manifest(m)
    m["frames"][0]["gemini_receipt_sha256"] = "b" * 64
    assert validate_batch_manifest(m)["frames"][0]["gemini_receipt_uri"].endswith("r1.json")


def test_unreviewed_cannot_claim_verified_class():
    m = _manifest()
    m["frames"][0]["reviewed_label"] = "NORMAL"
    with pytest.raises(ValueError):
        validate_batch_manifest(m)


def test_exact_duplicate_sha_and_repeated_id_are_rejected():
    m = _manifest()
    m["frames"].append(deepcopy(m["frames"][0]))
    with pytest.raises(ValueError):
        validate_batch_manifest(m)
    m["frames"][1]["frame_id"] = "frame_2"
    with pytest.raises(ValueError, match="duplicate"):
        validate_batch_manifest(m)


def test_batch_cannot_exceed_100_frames():
    m = _manifest()
    m["frames"] = [
        {**deepcopy(m["frames"][0]),
         "frame_id": f"frame_{i}", "image_sha256": f"{i:064x}"}
        for i in range(101)
    ]
    with pytest.raises(ValueError):
        validate_batch_manifest(m)


def test_unknown_fields_rejected():
    m = _manifest()
    m["frames"][0]["engineering_pass"] = True
    with pytest.raises(ValueError):
        validate_batch_manifest(m)


def test_gcs_allowlist_blocks_cross_bucket_and_query_strings():
    assert checked_gcs_uri(ROOT + "/dataset/frame.png").endswith("frame.png")
    for item in ("https://example.test/xx.png", "gs://other/xx.png",
                 ROOT + "/a//b.png", ROOT + "/a?generation=1"):
        with pytest.raises(ValueError):
            checked_gcs_uri(item)
