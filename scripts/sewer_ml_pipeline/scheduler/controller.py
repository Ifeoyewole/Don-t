from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Flask, jsonify
from google.cloud import batch_v1, compute_v1, storage
from google.api_core.exceptions import PreconditionFailed

try:
    from .engine import FinancialPolicy, Snapshot, decide
except ImportError:  # Cloud Run source root
    from engine import FinancialPolicy, Snapshot, decide


PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "joint-inspection-510310")
STATE_BUCKET = os.getenv("STATE_BUCKET", "joint-inspection-510310-orchestration")
STATE_PREFIX = os.getenv("STATE_PREFIX", "orchestration/gpu-scheduler/v1")
SUBMISSION_ENABLED = os.getenv("SUBMISSION_ENABLED", "false").lower() == "true"
LOCK_TTL_SECONDS = int(os.getenv("LOCK_TTL_SECONDS", "840"))
app = Flask(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_blob(name: str):
    return storage.Client(project=PROJECT).bucket(STATE_BUCKET).blob(f"{STATE_PREFIX}/{name}")


def acquire_lock(now: datetime) -> tuple[Any, dict[str, Any]]:
    blob = _json_blob("controller.lock.json")
    lease = {
        "owner": f"{socket.gethostname()}:{os.getpid()}",
        "acquired_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=LOCK_TTL_SECONDS)).isoformat(),
    }
    try:
        blob.upload_from_string(json.dumps(lease), content_type="application/json", if_generation_match=0)
        return blob, lease
    except PreconditionFailed:
        blob.reload()
        current = json.loads(blob.download_as_text())
        if datetime.fromisoformat(current["expires_at"]) > now:
            raise RuntimeError("controller lock is already held")
        generation = blob.generation
        blob.upload_from_string(json.dumps(lease), content_type="application/json", if_generation_match=generation)
        return blob, lease


def release_lock(blob: Any) -> None:
    try:
        blob.delete(if_generation_match=blob.generation)
    except Exception:
        app.logger.exception("failed to release controller lock")


def global_gpu_quota() -> float:
    project = compute_v1.ProjectsClient().get(project=PROJECT)
    for quota in project.quotas:
        if quota.metric == "GPUS_ALL_REGIONS":
            return float(quota.limit)
    return 0.0


def configured_financial_policy() -> FinancialPolicy:
    credit = os.getenv("VERIFIED_PROMO_CREDIT_USD")
    verified = os.getenv("CREDIT_VERIFIED_AT")
    expires = os.getenv("PROMO_CREDIT_EXPIRES_AT")
    pricing_verified = os.getenv("PRICING_VERIFIED_AT")
    return FinancialPolicy(
        credit_usd=float(credit) if credit else None,
        credit_verified_at=datetime.fromisoformat(verified) if verified else None,
        credit_expires_at=datetime.fromisoformat(expires) if expires else None,
        pricing_verified_at=datetime.fromisoformat(pricing_verified) if pricing_verified else None,
        estimated_spend_usd=float(os.getenv("ESTIMATED_CAMPAIGN_SPEND_USD", "0")),
        active_liability_usd=float(os.getenv("ACTIVE_LIABILITY_USD", "0")),
        candidate_worst_case_usd=float(os.getenv("CANDIDATE_WORST_CASE_USD", "0")),
        reserve_usd=float(os.getenv("CREDIT_RESERVE_USD", "50")),
        campaign_cap_usd=min(float(os.getenv("CAMPAIGN_CAP_USD", "100")), 240.0),
    )


def discover_campaign_jobs(now: datetime) -> tuple[list[dict[str, Any]], list[str], int]:
    client = batch_v1.BatchServiceClient()
    regions = os.getenv(
        "CANDIDATE_REGIONS",
        "europe-west4,europe-west3,europe-west2,europe-west6,us-central1,us-east1,us-west1,asia-southeast1,asia-east1,asia-south1",
    ).split(",")
    jobs: list[dict[str, Any]] = []
    events: list[str] = []
    oldest_minutes = 0
    for region in regions:
        parent = f"projects/{PROJECT}/locations/{region.strip()}"
        try:
            for job in client.list_jobs(parent=parent):
                job_id = job.name.rsplit("/", 1)[-1]
                if not job_id.startswith("sewer-ml-"):
                    continue
                state = batch_v1.JobStatus.State(job.status.state).name
                jobs.append({"name": job.name, "region": region.strip(), "state": state})
                if state not in {"SUCCEEDED", "FAILED", "DELETION_IN_PROGRESS"}:
                    created = job.create_time.replace(tzinfo=timezone.utc) if job.create_time.tzinfo is None else job.create_time
                    oldest_minutes = max(oldest_minutes, int((now - created).total_seconds() // 60))
                    events.extend(event.description for event in job.status.status_events)
        except Exception as exc:
            events.append(f"inventory failure in {region.strip()}: {type(exc).__name__}")
    return jobs, events, oldest_minutes


def load_state() -> dict[str, Any]:
    blob = _json_blob("state.json")
    if not blob.exists():
        return {"stage": "efficientnet_b0_20k", "attempted_regions": [], "active_jobs": []}
    return json.loads(blob.download_as_text())


def save_status(status: dict[str, Any]) -> None:
    _json_blob("status.json").upload_from_string(json.dumps(status, indent=2), content_type="application/json")


def read_status() -> dict[str, Any]:
    blob = _json_blob("status.json")
    if not blob.exists():
        return {"state": "DISCOVERING", "reason": "Controller inventory has not run yet.", "submission_enabled": SUBMISSION_ENABLED, "jobs": []}
    return json.loads(blob.download_as_text())


def run_controller() -> dict[str, Any]:
    now = utcnow()
    lock, _ = acquire_lock(now)
    try:
        state = load_state()
        discovered_jobs, discovered_events, wait_minutes = discover_campaign_jobs(now)
        snapshot = Snapshot(
            now=now,
            submission_enabled=SUBMISSION_ENABLED,
            global_gpu_quota=global_gpu_quota(),
            active_jobs=discovered_jobs,
            completed_stage=state.get("completed_stage", False),
            wait_minutes=wait_minutes,
            events=discovered_events,
            checkpoint=state.get("checkpoint"),
            financial=configured_financial_policy(),
        )
        decision = decide(snapshot)
        status = {
            "state": decision.state.value,
            "action": decision.action,
            "reason": decision.reason,
            "submission_enabled": SUBMISSION_ENABLED,
            "global_gpu_quota": snapshot.global_gpu_quota,
            "last_controller_execution": now.isoformat(),
            "next_scheduled_execution": (now + timedelta(minutes=15)).isoformat(),
            "stage": state.get("stage", "efficientnet_b0_20k"),
            "attempted_regions": state.get("attempted_regions", []),
            "jobs": discovered_jobs,
            "checkpoint": snapshot.checkpoint,
        }
        # Mutation is deliberately unavailable until every fail-closed gate passes.
        # Batch submit/cancel support is added only when SUBMISSION_ENABLED is approved.
        save_status(status)
        return status
    finally:
        release_lock(lock)


@app.post("/run")
def run_endpoint():
    try:
        return jsonify(run_controller())
    except RuntimeError as exc:
        return jsonify({"state": "MANUAL_REVIEW_REQUIRED", "reason": str(exc)}), 409


@app.get("/status")
def status_endpoint():
    return jsonify(read_status())


@app.get("/report")
def report_endpoint():
    return jsonify({
        "schema_version": 1,
        "generated_at": utcnow().isoformat(),
        "project": PROJECT,
        "controller": "jointinspect-gpu-controller",
        "status": read_status(),
        "security": {"submission_enabled": SUBMISSION_ENABLED, "credentials_included": False, "arbitrary_commands_allowed": False},
    })


@app.get("/healthz")
def health():
    return {"ok": True, "submission_enabled": SUBMISSION_ENABLED}
