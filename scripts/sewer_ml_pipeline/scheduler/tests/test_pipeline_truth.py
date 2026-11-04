from datetime import datetime, timezone
from pathlib import Path

from scripts.sewer_ml_pipeline.scheduler.pipeline_truth import mark_stored_pipeline_unverified


def test_stored_running_step_is_not_presented_as_live():
    seed = {
        "state": "PREPARING",
        "updated_at": "2026-10-22T01:20:00Z",
        "steps": [
            {"id": "prepare-wrc", "state": "RUNNING"},
            {"id": "smoke-wrc", "state": "QUEUED"},
        ],
    }

    actual = mark_stored_pipeline_unverified(seed, now=datetime(2026, 10, 23, tzinfo=timezone.utc))

    assert actual["state"] == "UNVERIFIED"
    assert actual["steps"][0]["state"] == "UNVERIFIED"
    assert actual["steps"][0]["reported_state"] == "RUNNING"
    assert actual["steps"][1]["state"] == "PLANNED"
    assert actual["steps"][0]["verified_live_at"] is None
    assert seed["steps"][0]["state"] == "RUNNING"


def test_recent_stored_status_is_still_unverified_without_provider_evidence():
    result = mark_stored_pipeline_unverified(
        {"updated_at": "2026-10-23T19:35:00Z", "steps": [{"state": "SUCCEEDED"}]},
        now=datetime(2026, 10, 23, 19, 35, tzinfo=timezone.utc),
    )
    assert result["steps"][0]["state"] == "UNVERIFIED"
    assert result["verified_live_at"] is None

def test_wrc_cloudbuild_config_has_no_direct_batch_submission():
    config = Path("scripts/sewer_ml_pipeline/cloud_configs/cloudbuild-wrc-campaign.yaml").read_text(encoding="utf-8")
    assert "gcloud batch jobs submit" not in config
    assert "GPU Batch submission disabled" in config
