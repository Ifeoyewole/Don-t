"""Offline worklist-to-batch conversion: no fabricated ROI or labels."""

from copy import deepcopy

import pytest

from scripts.cloud.create_unified_batch_manifest import convert_worklist


def _row():
    return {
        "review_status": "READY_FOR_RESEARCH",
        "image_sha256": "a"*64,
        "image_uri_TO_VERIFY": "gs://joint-inspection-510310-data/datasets/quarantine/pipe/frame.png",
        "source_family_TO_VERIFY": "video_family_confirmed_007",
        "roi_x0": "20", "roi_y0": "30",
        "roi_x1": "200", "roi_y1": "400",
        "geometry_TO_REVIEW": "VERTICAL_SEAM",
        "dataset_name": "Sewer Defects Public",
        "source_media_id": "frame-07",
        "source_labels": "Joint offset",
        "rights_review": "RESEARCH_QUARANTINE",
        "annotation_review": "UNVERIFIED_SOURCE_LABEL",
    }


def test_valid_manual_row_converts_without_upgrading_source_label():
    m = convert_worklist([_row()], manifest_id="reviewed_batch_01")
    frame = m["frames"][0]
    assert frame["frame_id"] == "frame_" + "a"*24
    assert frame["roi"] == [20, 30, 200, 400]
    assert frame["annotation_status"] == "UNVERIFIED_SOURCE_LABEL"
    assert frame["source_label"] == "Joint offset"
    assert "reviewed_label" not in frame


def test_unreviewed_rows_skipped_and_empty_batch_rejected():
    row = _row()
    row["review_status"] = "NEEDS_HUMAN_REVIEW"
    with pytest.raises(ValueError):
        convert_worklist([row], manifest_id="batch_1")


def test_missing_verified_roi_and_source_family_are_fatal():
    for k, val in (
        ("image_uri_TO_VERIFY", ""),
        ("source_family_TO_VERIFY", ""),
        ("source_family_TO_VERIFY", "UNVERIFIED_0001"),
        ("roi_x0", ""),
        ("geometry_TO_REVIEW", ""),
    ):
        row = _row()
        row[k] = val
        with pytest.raises(ValueError):
            convert_worklist([row], manifest_id="batch_1")


def test_reviewed_ground_truth_requires_independent_review_id():
    row = _row()
    row["annotation_review"] = "REVIEWED_GROUND_TRUTH"
    row["reviewed_ground_truth_label"] = "JOINT_DISPLACEMENT"
    with pytest.raises(ValueError):
        convert_worklist([row], manifest_id="batch_1")
    row["review_id"] = "inspector-verified-0001"
    m = convert_worklist([row], manifest_id="batch_1")
    assert m["frames"][0]["reviewed_label"] == "JOINT_DISPLACEMENT"


def test_duplicate_sha_not_silently_reused():
    rows = [_row(), deepcopy(_row())]
    with pytest.raises(ValueError):
        convert_worklist(rows, manifest_id="batch_1")


def test_target_limit_blocks_excess_ready_rows():
    rows = [_row(), {**_row(), "image_sha256": "b"*64}]
    with pytest.raises(ValueError):
        convert_worklist(rows, manifest_id="batch_1", limit=1)
