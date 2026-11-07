"""Cloud-job input validation; no GPU, model download or Google credentials."""
import pytest
from scripts.cloud.inspect_view_sam2_vertex import checked_sha, split_gs

def test_uri_rejects_non_gcs_and_bucket_only():
    for value in ("http://example.com/x", "/tmp/model.pt", "gs://bucket", "gs:///x", "gs://bucket/a/../b"):
        with pytest.raises(ValueError):
            split_gs(value)

def test_uri_accepts_specific_object():
    assert split_gs("gs://model-bucket/inspect/r5.pt") == ("model-bucket", "inspect/r5.pt")

def test_sha256_requires_complete_hex():
    for value in ("", "pending", "ab" * 31, "z" * 64):
        with pytest.raises(ValueError):
            checked_sha(value)
    assert checked_sha("A" * 64) == "a" * 64
