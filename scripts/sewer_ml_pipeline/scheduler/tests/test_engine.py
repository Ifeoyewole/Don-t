from datetime import datetime, timedelta, timezone

import pytest

from scripts.sewer_ml_pipeline.scheduler.engine import CampaignState, FinancialPolicy, Snapshot, decide


NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def funded(**overrides):
    values = dict(
        credit_usd=290,
        credit_verified_at=NOW,
        credit_expires_at=NOW + timedelta(days=30),
        pricing_verified_at=NOW,
        estimated_spend_usd=0,
        active_liability_usd=0,
        candidate_worst_case_usd=20,
        reserve_usd=50,
        campaign_cap_usd=100,
    )
    values.update(overrides)
    return FinancialPolicy(**values)


def snap(**overrides):
    values = dict(now=NOW, submission_enabled=True, global_gpu_quota=1, financial=funded())
    values.update(overrides)
    return Snapshot(**values)


def test_initial_scheduling():
    assert decide(snap()).action == "submit"


def test_zone_capacity_exhaustion_waits_before_limit():
    result = decide(snap(active_jobs=[{"state": "SCHEDULED"}], events=["CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED"], wait_minutes=30))
    assert result.action == "observe"


def test_regional_failover_after_limit():
    result = decide(snap(active_jobs=[{"state": "SCHEDULED"}], events=["CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED"], wait_minutes=90))
    assert result.action == "failover"


def test_duplicate_active_jobs_blocked():
    assert decide(snap(active_jobs=[{"state": "QUEUED"}, {"state": "SCHEDULED"}])).state == CampaignState.MANUAL_REVIEW_REQUIRED


def test_global_quota_exhaustion_blocks():
    result = decide(snap(global_gpu_quota=0))
    assert result.action == "block" and "GPUS_ALL_REGIONS" in result.reason


def test_credit_unavailable_pauses():
    assert decide(snap(financial=funded(credit_usd=None))).state == CampaignState.BUDGET_PAUSED


def test_budget_safety_stop():
    assert decide(snap(financial=funded(candidate_worst_case_usd=60, credit_usd=100))).state == CampaignState.BUDGET_PAUSED


def test_successful_allocation_is_never_cancelled():
    result = decide(snap(active_jobs=[{"state": "RUNNING"}], wait_minutes=999, events=["RESOURCE_POOL_EXHAUSTED"]))
    assert result.state == CampaignState.RUNNING and result.action == "observe"


def test_checkpoint_is_preserved_while_running():
    result = decide(snap(active_jobs=[{"state": "RUNNING"}], checkpoint="gs://bucket/ckpt"))
    assert result.state == CampaignState.RUNNING


def test_completed_stage_not_resubmitted():
    assert decide(snap(completed_stage=True)).action == "disable_trigger"


def test_expired_credit_pauses():
    assert decide(snap(financial=funded(credit_expires_at=NOW - timedelta(seconds=1)))).state == CampaignState.BUDGET_PAUSED


def test_restart_recovers_single_pending_job():
    assert decide(snap(active_jobs=[{"state": "QUEUED"}])).state == CampaignState.ALLOCATING


def test_submission_disabled_is_dry_run():
    result = decide(snap(submission_enabled=False))
    assert result.action == "dry_run"


def test_missing_financial_preflight_pauses():
    assert decide(snap(financial=None)).state == CampaignState.BUDGET_PAUSED
