"""Offline contract tests for GCS-only quarantined CCTV review sheets."""

from csv import DictReader
import hashlib
from io import BytesIO, StringIO
import json

from PIL import Image
import pytest

from scripts.cloud.create_unified_review_contact_sheets import (
    BASE, BUCKET, SOURCE_PREFIXES,
    checked_relative_path, checked_uri, expected_archive_suffix,
    find_verified_object_name, generate, tentative_family,
)


def _image_bytes():
    canvas = Image.new("RGB", (100, 180), (30, 80, 115))
    out = BytesIO()
    canvas.save(out, format="JPEG")
    return out.getvalue()


class FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name
        self.generation = 1
        self.size = None

    def reload(self):
        self.size = len(self.store[self.name])

    def download_as_bytes(self, **kwargs):
        assert kwargs["if_generation_match"] == self.generation
        return self.store[self.name]

    def upload_from_string(self, body, **kwargs):
        assert kwargs["if_generation_match"] == 0
        assert self.name not in self.store
        self.store[self.name] = body


class FakeBucket:
    def __init__(self, store):
        self.store = store

    def blob(self, name):
        return FakeBlob(self.store, name)


class FakeClient:
    def __init__(self, store):
        self.store = store

    def bucket(self, name):
        assert name == BUCKET
        return FakeBucket(self.store)

    def list_blobs(self, bucket, *, prefix):
        assert bucket == BUCKET
        return [
            FakeBlob(self.store, name) for name in self.store
            if name.startswith(prefix)
        ]


def _fixtures():
    data = _image_bytes()
    sha = hashlib.sha256(data).hexdigest()
    prefix = SOURCE_PREFIXES["Sewer Defects Public"]
    image_name = (
        prefix + "sewer-defects-v1/extracted/dataset-contents/"
        "train/images/PI005299_f11640_jpg.rf.abcdef.jpg"
    )
    worklist_key = "datasets/quarantine/review-worklists/test.csv"
    rows = "\n".join([
        "candidate_bucket,dataset_name,source_image_path,source_media_id,"
        "image_sha256,image_uri_TO_VERIFY,source_family_TO_VERIFY,roi_x0",
        "JOINT_DISPLACEMENT_CANDIDATE,Sewer Defects Public,"
        f"train/images/PI005299_f11640_jpg.rf.abcdef.jpg,"
        f"PI005299_f11640_jpg.rf.abcdef,{sha},,,",
    ]) + "\n"
    registry = {
        "dataset_name": "Sewer Defects Public",
        "commercial_training_eligible": False,
        "source_root_within_extracted_archive": "dataset-contents",
        "records": [{
            "original_image_path": "train/images/PI005299_f11640_jpg.rf.abcdef.jpg",
            "sha256": sha,
        }],
    }
    other = {
        "dataset_name": "Pipeline CCTV Defect Public",
        "commercial_training_eligible": False,
        "records": [],
    }
    store = {
        image_name: data,
        worklist_key: rows.encode("utf-8-sig"),
        prefix + "dataset_registry.json": json.dumps(registry).encode(),
        SOURCE_PREFIXES["Pipeline CCTV Defect Public"] + "dataset_registry.json":
            json.dumps(other).encode(),
    }
    return store, worklist_key, image_name, sha, registry


def test_only_exact_registry_media_suffix_is_resolved():
    store, _, image_name, sha, registry = _fixtures()
    row = {
        "source_image_path": "train/images/PI005299_f11640_jpg.rf.abcdef.jpg",
        "image_sha256": sha,
    }
    prefix = SOURCE_PREFIXES["Sewer Defects Public"]
    assert expected_archive_suffix(registry, row["source_image_path"]) == (
        "extracted/dataset-contents/train/images/"
        "PI005299_f11640_jpg.rf.abcdef.jpg"
    )
    assert find_verified_object_name(
        registry, row, prefix=prefix, available_names=list(store)
    ) == image_name
    assert find_verified_object_name(
        registry, {**row, "image_sha256": "f"*64},
        prefix=prefix, available_names=list(store)
    ) is None
    assert find_verified_object_name(
        registry, row, prefix=prefix,
        available_names=[image_name, prefix + "duplicate/" + image_name[len(prefix):]]
    ) is None


def test_contact_sheets_verify_real_bytes_and_do_not_approve_annotations():
    store, worklist, image_name, sha, _ = _fixtures()
    client = FakeClient(store)
    result = generate(
        client,
        worklist_uri=BASE + "/" + worklist,
        output_prefix_uri=BASE + "/datasets/quarantine/review-sheets/test001",
    )
    assert result["sha256_verified_image_count"] == 1
    assert result["unresolved_count"] == 0
    assert result["family_hints_not_ground_truth"] == {"PI005299": 1}
    assert result["commercial_training_eligible"] is False
    key = "datasets/quarantine/review-sheets/test001/review-worklist-verified.csv"
    csv = list(DictReader(StringIO(store[key].decode("utf-8-sig"))))
    assert csv[0]["image_uri_TO_VERIFY"] == BASE + "/" + image_name
    assert csv[0]["source_family_TO_VERIFY"] == ""
    assert csv[0]["roi_x0"] == ""
    assert csv[0]["review_status"] == "NEEDS_HUMAN_REVIEW"
    assert "contact-sheet-01.jpg" in result["pages"][0]
    assert len(store["datasets/quarantine/review-sheets/test001/contact-sheet-01.jpg"]) > 1000


def test_sha_changed_object_is_excluded_and_not_published():
    store, worklist, image_name, _, _ = _fixtures()
    store[image_name] = b"tampered image bytes"
    with pytest.raises(ValueError, match="No source objects verified"):
        generate(
            FakeClient(store), worklist_uri=BASE + "/" + worklist,
            output_prefix_uri=BASE + "/datasets/quarantine/review-sheets/test002",
        )


@pytest.mark.parametrize("bad", [
    "https://example.com/a.png",
    "gs://other-bucket/a.png",
    BASE + "/../bad.jpg",
    BASE + "/a//bad.jpg",
    BASE + "/a?b=1",
])
def test_untrusted_gcs_locations_are_rejected(bad):
    with pytest.raises(ValueError):
        checked_uri(bad)


@pytest.mark.parametrize("bad", ["/absolute.png", "../escape.png", "a/../b.jpg", "", r"a\b.png"])
def test_untrusted_relative_media_paths_are_rejected(bad):
    with pytest.raises(ValueError):
        checked_relative_path(bad)


def test_family_ids_are_only_hints():
    assert tentative_family("PI005455_f3240_jpg.rf.abc") == "PI005455"
    assert tentative_family("opaque-img-filename") is None
