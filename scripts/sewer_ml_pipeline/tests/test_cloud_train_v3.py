import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cloud_train_v3 import (
    BOOT_DISK_SIZE_BYTES,
    FILESYSTEM_SAFETY_MARGIN_BYTES,
    MAX_TOTAL_BYTES,
    artifact_inventory,
    check_disk_space,
    download_verified,
    parse_gs_uri,
    publish_artifacts,
    read_csv_bytes,
    validate_checkpoint_state,
    validate_rows,
)
from curate_staged import TARGETS
from wrc_feasibility import evaluate as evaluate_wrc


class MockBlob:
    def __init__(self, name: str, data: bytes, size: int | None = None):
        self.name = name
        self.data = data
        self.size = size if size is not None else len(data)

    def reload(self):
        pass

    def download_to_filename(self, filename: str):
        Path(filename).write_bytes(self.data)


def row(name, group, split):
    value = {"Filename": name, "source_group": group, "sha256": "a" * 64,
             "GCS_URI": f"gs://bucket/images/{name}"}
    value.update({code: "1" if code == "FS" else "0" for code in TARGETS})
    return value


def test_gcs_uri_contract_is_fail_closed():
    assert parse_gs_uri("gs://bucket/prefix/object") == ("bucket", "prefix/object")
    for value in ("https://bucket/object", "gs://bucket", "gs://bucket/a/../secret", "gs:///object"):
        with pytest.raises(ValueError):
            parse_gs_uri(value)


def test_manifest_contract_requires_group_disjoint_splits():
    splits = {name: [row(f"{name}.jpg", name, name)]
              for name in ("train", "early_stop", "threshold_tune", "dev_report")}
    assert validate_rows(splits, "bucket")["train"] == 1
    splits["dev_report"][0]["source_group"] = "train"
    with pytest.raises(ValueError, match="leakage"):
        validate_rows(splits)


def test_duplicate_group_assignments_fail_closed():
    splits = {
        "train": [row("img1.jpg", "group-alpha", "train")],
        "early_stop": [row("img2.jpg", "group-beta", "early_stop")],
        "threshold_tune": [row("img3.jpg", "group-alpha", "threshold_tune")],
        "dev_report": [row("img4.jpg", "group-delta", "dev_report")],
    }
    with pytest.raises(ValueError, match="leakage: group-alpha appears in train and threshold_tune"):
        validate_rows(splits)


def test_manifest_rejects_unapproved_bucket():
    splits = {name: [row(f"{name}.jpg", name, name)]
              for name in ("train", "early_stop", "threshold_tune", "dev_report")}
    splits["train"][0]["GCS_URI"] = "gs://unexpected/images/train.jpg"
    with pytest.raises(ValueError, match="approved GCS bucket"):
        validate_rows(splits, "bucket")


def test_corrupt_manifests_fail_closed():
    # Non-UTF8 payload
    with pytest.raises(ValueError, match="cannot decode UTF-8"):
        read_csv_bytes(b"\xff\xfe\x00\x00notutf8")

    # Empty payload
    with pytest.raises(ValueError, match="payload is empty"):
        read_csv_bytes(b"")
    with pytest.raises(ValueError, match="payload is empty"):
        read_csv_bytes(b"   \n\n  \n")

    # Missing header
    with pytest.raises(ValueError, match="missing CSV header"):
        read_csv_bytes(b",,\n")

    # Missing required columns
    with pytest.raises(ValueError, match="missing required columns"):
        read_csv_bytes(b"Filename,some_other_column\nfile1.jpg,val\n")

    # Header with no data rows
    with pytest.raises(ValueError, match="no data rows"):
        read_csv_bytes(b"Filename,sha256,GCS_URI\n")

    # Valid manifest parses cleanly
    valid_csv = b"Filename,sha256,GCS_URI,source_group,FS\nimg.jpg," + b"a" * 64 + b",gs://b/img.jpg,grp1,1\n"
    rows = read_csv_bytes(valid_csv)
    assert len(rows) == 1
    assert rows[0]["Filename"] == "img.jpg"


def test_insufficient_storage_fails_closed(tmp_path: Path):
    # Demanding more space than physical disk capacity must fail closed
    with pytest.raises(RuntimeError, match="Insufficient disk space"):
        check_disk_space(tmp_path, required_bytes=1000 * 1024**3)

    # Staging allowance must reconcile safely within 150 GiB boot disk
    assert MAX_TOTAL_BYTES < BOOT_DISK_SIZE_BYTES
    assert MAX_TOTAL_BYTES == 80 * 1024**3
    assert FILESYSTEM_SAFETY_MARGIN_BYTES == 15 * 1024**3
    assert MAX_TOTAL_BYTES + FILESYSTEM_SAFETY_MARGIN_BYTES < BOOT_DISK_SIZE_BYTES

    # Exceeding remaining bytes quota in download_verified
    mock_blob = MockBlob("test.jpg", b"x" * 1024, size=1024)
    with pytest.raises(RuntimeError, match="byte limit exceeded"):
        download_verified(mock_blob, tmp_path / "img.jpg", "a" * 64, remaining_bytes=512)


def test_missing_and_empty_images_fail_closed(tmp_path: Path):
    # Empty blob (size 0)
    empty_blob = MockBlob("empty.jpg", b"", size=0)
    with pytest.raises(RuntimeError, match="Missing or empty image blob"):
        download_verified(empty_blob, tmp_path / "empty.jpg", "a" * 64, remaining_bytes=1024**2)

    # Blob reporting size < 1
    zero_blob = MockBlob("zero.jpg", b"", size=-1)
    with pytest.raises(RuntimeError, match="Missing or empty image blob"):
        download_verified(zero_blob, tmp_path / "zero.jpg", "a" * 64, remaining_bytes=1024**2)


def test_hash_mismatch_fails_closed_and_unlinks(tmp_path: Path):
    content = b"valid image content bytes"
    target = tmp_path / "corrupt.jpg"
    blob = MockBlob("corrupt.jpg", content, size=len(content))
    wrong_hash = "0" * 64
    with pytest.raises(RuntimeError, match="Checksum mismatch"):
        download_verified(blob, target, expected_sha256=wrong_hash, remaining_bytes=1024**2)
    assert not target.exists(), "Corrupted file must be unlinked on checksum failure"


def test_interrupted_staging_fails_closed_and_unlinks(tmp_path: Path):
    # Blob metadata claims 100 bytes, but only 40 bytes are downloaded
    target = tmp_path / "partial.jpg"
    blob = MockBlob("partial.jpg", b"x" * 40, size=100)
    expected_hash = hashlib.sha256(b"x" * 40).hexdigest()
    with pytest.raises(RuntimeError, match="Interrupted staging"):
        download_verified(blob, target, expected_sha256=expected_hash, remaining_bytes=1024**2)
    assert not target.exists(), "Partial file must be unlinked on interrupted staging"


def test_checkpoint_resume_errors_fail_closed():
    # Not a dictionary
    with pytest.raises(RuntimeError, match="checkpoint state is not a dictionary"):
        validate_checkpoint_state("not a dict", "cfg-123")

    # Missing required keys
    incomplete_state = {"epoch": 1, "config_id": "cfg-123"}
    with pytest.raises(RuntimeError, match="missing required keys"):
        validate_checkpoint_state(incomplete_state, "cfg-123")

    # Config ID mismatch
    mismatched_state = {
        "epoch": 2, "config_id": "wrong-cfg", "best_f1": 0.85, "wait": 0,
        "model": {}, "optimizer": {}, "scheduler": {},
    }
    with pytest.raises(RuntimeError, match="config_id mismatch"):
        validate_checkpoint_state(mismatched_state, "expected-cfg")

    # Invalid epoch
    invalid_epoch_state = {
        "epoch": -1, "config_id": "expected-cfg", "best_f1": 0.85, "wait": 0,
        "model": {}, "optimizer": {}, "scheduler": {},
    }
    with pytest.raises(RuntimeError, match="invalid epoch"):
        validate_checkpoint_state(invalid_epoch_state, "expected-cfg")

    # Valid checkpoint passes
    valid_state = {
        "epoch": 5, "config_id": "expected-cfg", "best_f1": 0.85, "wait": 1,
        "model": {"weights": 1}, "optimizer": {"lr": 0.001}, "scheduler": {"step": 5},
    }
    validate_checkpoint_state(valid_state, "expected-cfg")


def test_artifacts_must_be_complete_and_nonproduction(tmp_path: Path):
    for name in ("best.pt", "model.onnx", "metrics.json", "history.json"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "model_card.json").write_text(json.dumps({
        "production_approved": False, "locked_test_evaluated": False
    }))
    assert {item["name"] for item in artifact_inventory(tmp_path)} >= {"model.onnx", "best.pt"}
    (tmp_path / "model_card.json").write_text(json.dumps({"production_approved": True}))
    with pytest.raises(RuntimeError, match="safety flags"):
        artifact_inventory(tmp_path)


def test_artifact_publication_failure_fails_closed(tmp_path: Path):
    mock_client = MagicMock()

    # Empty inventory
    with pytest.raises(RuntimeError, match="artifact inventory is empty"):
        publish_artifacts(tmp_path, mock_client, "bucket", "prefix", "cfg-1", [])

    # Missing file on disk
    fake_inventory = [{"name": "missing.pt", "bytes": 100, "sha256": "0" * 64}]
    with pytest.raises(RuntimeError, match="missing or empty artifact missing.pt"):
        publish_artifacts(tmp_path, mock_client, "bucket", "prefix", "cfg-1", fake_inventory)

    # Empty (0-byte) file on disk
    (tmp_path / "empty_art.pt").write_bytes(b"")
    zero_inventory = [{"name": "empty_art.pt", "bytes": 0, "sha256": "0" * 64}]
    with pytest.raises(RuntimeError, match="missing or empty artifact empty_art.pt"):
        publish_artifacts(tmp_path, mock_client, "bucket", "prefix", "cfg-1", zero_inventory)


def test_invalid_dataset_source_provenance_fails_closed():
    # Provenance audit: missing rights fields must block fine-tuning
    empty_meta = {}
    result = evaluate_wrc(empty_meta)
    assert result["research_finetune_ready"] is False
    assert any("Missing provenance" in b for b in result["blockers"])

    # Explicit research permission required
    pending_meta = {
        "original_weights_sha256": "abc", "source_commit": "def",
        "original_class_codes": ["VA"], "preprocessing": {},
        "research_finetune_allowed": False, "rights_evidence_uri": "uri",
        "authorized_training_dataset": "ds", "architecture_available": True,
        "commercial_release_allowed": False, "training_head_strategy": "new_multilabel_head",
        "label_mapping_verified": True,
    }
    pending_result = evaluate_wrc(pending_meta)
    assert pending_result["research_finetune_ready"] is False
    assert any("Fine-tuning rights not explicitly established" in b for b in pending_result["blockers"])

