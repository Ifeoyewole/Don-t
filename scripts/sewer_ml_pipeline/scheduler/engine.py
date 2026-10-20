from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class CampaignState(str, Enum):
    DISCOVERING = "DISCOVERING"
    WAITING_FOR_CAPACITY = "WAITING_FOR_CAPACITY"
    ALLOCATING = "ALLOCATING"
    RUNNING = "RUNNING"
    CHECKPOINTING = "CHECKPOINTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BUDGET_PAUSED = "BUDGET_PAUSED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


ALLOCATION_ERRORS = (
    "CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED",
    "RESOURCE_POOL_EXHAUSTED",
    "does not have enough resources",
)


@dataclass(frozen=True)
class FinancialPolicy:
    credit_usd: float | None
    credit_verified_at: datetime | None
    credit_expires_at: datetime | None
    pricing_verified_at: datetime | None
    estimated_spend_usd: float
    active_liability_usd: float
    candidate_worst_case_usd: float
    reserve_usd: float = 50.0
    campaign_cap_usd: float = 240.0
    max_credit_age_hours: int = 24
    max_pricing_age_hours: int = 168

    def blocker(self, now: datetime) -> str | None:
        if self.credit_usd is None or self.credit_verified_at is None:
            return "promotional credit balance is unverified"
        if now - self.credit_verified_at > timedelta(hours=self.max_credit_age_hours):
            return "promotional credit balance is stale"
        if self.credit_expires_at is None or self.credit_expires_at <= now:
            return "promotional credits are expired or expiry is unverified"
        if self.pricing_verified_at is None or now - self.pricing_verified_at > timedelta(hours=self.max_pricing_age_hours):
            return "cost information is missing or stale"
        liability = self.estimated_spend_usd + self.active_liability_usd + self.candidate_worst_case_usd
        if liability > self.campaign_cap_usd:
            return "campaign authorization cap would be exceeded"
        if self.credit_usd - liability < self.reserve_usd:
            return "promotional credit safety reserve would be threatened"
        return None


@dataclass
class Snapshot:
    now: datetime
    submission_enabled: bool
    global_gpu_quota: float
    active_jobs: list[dict[str, Any]] = field(default_factory=list)
    completed_stage: bool = False
    wait_minutes: int = 0
    events: list[str] = field(default_factory=list)
    checkpoint: str | None = None
    financial: FinancialPolicy | None = None


@dataclass(frozen=True)
class Decision:
    state: CampaignState
    action: str
    reason: str


def decide(snapshot: Snapshot, wait_limit_minutes: int = 90) -> Decision:
    if snapshot.completed_stage:
        return Decision(CampaignState.COMPLETED, "disable_trigger", "stage already completed")
    running = [j for j in snapshot.active_jobs if j.get("state") == "RUNNING"]
    if running:
        return Decision(CampaignState.RUNNING, "observe", "a GPU training job is running")
    nonterminal = [j for j in snapshot.active_jobs if j.get("state") not in {"SUCCEEDED", "FAILED", "DELETION_IN_PROGRESS"}]
    if len(nonterminal) > 1:
        return Decision(CampaignState.MANUAL_REVIEW_REQUIRED, "block", "multiple active GPU jobs detected")
    if snapshot.global_gpu_quota < 1:
        return Decision(CampaignState.MANUAL_REVIEW_REQUIRED, "block", "GPUS_ALL_REGIONS quota is below one")
    if snapshot.financial is None:
        return Decision(CampaignState.BUDGET_PAUSED, "block", "financial preflight is unavailable")
    financial_blocker = snapshot.financial.blocker(snapshot.now)
    if financial_blocker:
        return Decision(CampaignState.BUDGET_PAUSED, "block", financial_blocker)
    if not snapshot.submission_enabled:
        return Decision(CampaignState.MANUAL_REVIEW_REQUIRED, "dry_run", "GPU submission is disabled")
    if nonterminal:
        allocation_failure = any(any(code in event for code in ALLOCATION_ERRORS) for event in snapshot.events)
        if allocation_failure and snapshot.wait_minutes >= wait_limit_minutes:
            return Decision(CampaignState.WAITING_FOR_CAPACITY, "failover", "allocation wait limit reached")
        return Decision(CampaignState.ALLOCATING, "observe", "one allocation attempt is pending")
    return Decision(CampaignState.DISCOVERING, "submit", "all safety preflights passed")
