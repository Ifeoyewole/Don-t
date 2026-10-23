"""Truthful presentation helpers for persisted WRc campaign snapshots.

Persisted GCS JSON is evidence of what was recorded, never evidence that a
Cloud Build or Batch operation is currently live.  Provider reconciliation in
``controller.py`` is the only code allowed to promote a step to a live state.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def mark_stored_pipeline_unverified(pipeline: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Return a fail-closed view of a stored campaign snapshot.

    ``reported_state`` retains the forensic value of the stored state.  A
    recent timestamp or self-declared source must not manufacture live status.
    """
    if not isinstance(pipeline, dict):
        return {
            "state": "UNVERIFIED",
            "verification": "STORED_SNAPSHOT_UNVERIFIED",
            "reason": "Pipeline snapshot is not a JSON object",
            "steps": [],
        }

    safe = deepcopy(pipeline)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds: int | None = None
    updated_at = safe.get("updated_at")
    if isinstance(updated_at, str):
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                age_seconds = max(0, int((current - parsed.astimezone(timezone.utc)).total_seconds()))
        except (TypeError, ValueError):
            pass

    safe.update(
        {
            "reported_state": safe.get("state", "UNKNOWN"),
            "state": "UNVERIFIED",
            "verification": "STORED_SNAPSHOT_UNVERIFIED",
            "status_source": "PERSISTED_GCS",
            "verified_live_at": None,
            "snapshot_age_seconds": age_seconds,
            "reason": "Stored pipeline snapshot; not verified against live GCP resources",
        }
    )
    steps: list[dict[str, Any]] = []
    for reported in safe.get("steps", []):
        if not isinstance(reported, dict):
            continue
        step = deepcopy(reported)
        reported_state = str(step.get("state", "UNKNOWN")).upper()
        step.update(
            {
                "reported_state": reported_state,
                "status_source": "PERSISTED_GCS",
                "verified_live_at": None,
                "state": "PLANNED" if reported_state == "QUEUED" else reported_state if reported_state == "BLOCKED" else "UNVERIFIED",
                "detail": "Planned in campaign; no GCP resource verified"
                if reported_state == "QUEUED"
                else "Waiting for prior planned steps; not a live provider status"
                if reported_state == "BLOCKED"
                else "Unverified stored status; inspect a live Cloud Build or Batch resource ID",
            }
        )
        steps.append(step)
    safe["steps"] = steps
    return safe
