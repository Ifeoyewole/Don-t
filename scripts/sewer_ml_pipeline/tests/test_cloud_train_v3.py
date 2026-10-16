import json
from pathlib import Path

import pytest

from cloud_train_v3 import artifact_inventory, parse_gs_uri, validate_rows
from curate_staged import TARGETS


def row(name, group, split):
    value = {"Filename": name, "source_group": group, "sha256": "a" * 64,
             "GCS_URI": f"gs://bucket/images/{name}"}
    value.update({code: "1" if code == "FS" else "0" for code in TARGETS})
    return value


def test_gcs_uri_contract_is_fail_closed():
    assert parse_gs_uri("gs://bucket/prefix/object") == ("bucket", "prefix/object")
    for value in ("https://bucket/object", "gs://bucket", "gs://bucket/a/../secret"):
        with pytest.raises(ValueError):
            parse_gs_uri(value)


def test_manifest_contract_requires_group_disjoint_splits():
    splits = {name: [row(f"{name}.jpg", name, name)]
              for name in ("train", "early_stop", "threshold_tune", "dev_report")}
    assert validate_rows(splits, "bucket")["train"] == 1
    splits["dev_report"][0]["source_group"] = "train"
    with pytest.raises(ValueError, match="leakage"):
        validate_rows(splits)


def test_manifest_rejects_unapproved_bucket():
    splits = {name: [row(f"{name}.jpg", name, name)]
              for name in ("train", "early_stop", "threshold_tune", "dev_report")}
    splits["train"][0]["GCS_URI"] = "gs://unexpected/images/train.jpg"
    with pytest.raises(ValueError, match="approved GCS bucket"):
        validate_rows(splits, "bucket")


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
