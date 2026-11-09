"""Task-aware CSV and manifest validation regression tests."""

from copy import deepcopy
import pytest

from backend.app.core.cv.ai.unified_batch_manifest import validate_batch_manifest
from scripts.cloud.create_unified_batch_manifest import convert_worklist


def frame():
    return {
        "frame_id": "f_001",
        "image_uri": "gs://joint-inspection-510310-data/quarantine/frame1.jpg",
        "image_sha256": "a"*64,
        "roi": [10, 15, 360, 400],
        "source_family": "inspector-confirmed-video",
        "source_id": "frame1",
        "rights_status": "RESEARCH_QUARANTINE",
        "annotation_status": "UNVERIFIED_SOURCE_LABEL",
    }


def manifest(row):
    return {
        "schema_version": "1.0",
        "manifest_id": "pilot14taskaware",
        "frames": [row],
    }


@pytest.mark.parametrize("task", [
    "OBJECT_SEGMENTATION", "INFILTRATION_REVIEW",
])
def test_nonjoint_manifest_does_not_accept_seam_geometry(task):
    sample = {**frame(), "task_type": task}
    clean = validate_batch_manifest(manifest(sample))
    assert clean["frames"][0]["task_type"] == task
    assert "geometry" not in clean["frames"][0]
    sample["geometry"] = "VERTICAL_SEAM"
    with pytest.raises(ValueError, match="forbids"):
        validate_batch_manifest(manifest(sample))


def test_legacy_joint_manifest_remains_compatible():
    legacy = {**frame(), "geometry": "VERTICAL_SEAM"}
    clean = validate_batch_manifest(manifest(legacy))
    assert clean["frames"][0]["task_type"] == "JOINT_GEOMETRY"
    assert clean["frames"][0]["geometry"] == "VERTICAL_SEAM"


def test_explicit_joint_requires_seam_geometry():
    with pytest.raises(ValueError, match="requires"):
        validate_batch_manifest(
            manifest({**frame(), "task_type": "JOINT_GEOMETRY"})
        )


def test_never_infer_task_from_source_label():
    m = manifest({
        **frame(), "geometry": "VERTICAL_SEAM",
        "source_label": "Utility intrusion",
    })
    assert validate_batch_manifest(m)["frames"][0]["task_type"] == "JOINT_GEOMETRY"


def test_bad_task_rejected_before_inference():
    with pytest.raises(ValueError, match="Unsupported"):
        validate_batch_manifest(manifest({
            **frame(), "task_type": "INSTANT_DEFECT_DIAGNOSIS"
        }))


def csvrow():
    return {
        "review_status": "READY_FOR_RESEARCH",
        "task_type_TO_REVIEW": "OBJECT_SEGMENTATION",
        "image_uri_TO_VERIFY": (
            "gs://joint-inspection-510310-data/datasets/quarantine/pipe/frame.jpg"
        ),
        "image_sha256": "b"*64,
        "source_family_TO_VERIFY": "confirmed-PI008113",
        "roi_x0": "42", "roi_y0": "109",
        "roi_x1": "375", "roi_y1": "248",
        "geometry_TO_REVIEW": "",
        "dataset_name": "Sewer Defects Public",
        "source_media_id": "PI008113",
        "source_labels": "Utility intrusion",
        "rights_review": "RESEARCH_QUARANTINE",
        "annotation_review": "UNVERIFIED_SOURCE_LABEL",
    }


def test_explicit_nonjoint_csv_converts_without_fabricating_seam():
    row = csvrow()
    out = convert_worklist([row], manifest_id="task_aware_001")
    assert out["frames"][0]["task_type"] == "OBJECT_SEGMENTATION"
    assert "geometry" not in out["frames"][0]
    assert out["frames"][0]["source_label"] == "Utility intrusion"


def test_infiltration_csv_does_not_become_confirmed_label():
    row = csvrow()
    row["task_type_TO_REVIEW"] = "INFILTRATION_REVIEW"
    row["source_labels"] = "Leak"
    out = convert_worklist([row], manifest_id="task_aware_001")
    assert out["frames"][0]["task_type"] == "INFILTRATION_REVIEW"
    assert out["frames"][0]["annotation_status"] == "UNVERIFIED_SOURCE_LABEL"
    assert "reviewed_label" not in out["frames"][0]


def test_nonjoint_csv_with_fake_geometry_is_rejected():
    row = csvrow()
    row["geometry_TO_REVIEW"] = "CIRCULAR_OPENING"
    with pytest.raises(ValueError, match="non-joint task"):
        convert_worklist([row], manifest_id="task_aware_001")


def test_missing_task_defaults_only_to_legacy_joint_contract():
    row = csvrow()
    row.pop("task_type_TO_REVIEW")
    with pytest.raises(ValueError, match="Joint-geometry"):
        convert_worklist([row], manifest_id="task_aware_001")
    row["geometry_TO_REVIEW"] = "VERTICAL_SEAM"
    assert convert_worklist([row], manifest_id="task_aware_001")["frames"][0]["task_type"] == "JOINT_GEOMETRY"
