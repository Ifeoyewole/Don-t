"""Immutable Audit Event Store for Human Annotation & Review.

Maintains an append-only JSONL ledger (annotation_events.jsonl).
Never overwrites historical events.
Enforces review states:
- PENDING
- VERIFIED
- REJECTED
- AMBIGUOUS
- NEEDS_SECOND_REVIEW
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("review_store")

VALID_ACTIONS = {"ACCEPT", "REJECT", "SKIP", "UPDATE_ANNOTATION", "FLAG_AMBIGUOUS", "REQUEST_SECOND_REVIEW"}
VALID_STATES = {"PENDING", "VERIFIED", "REJECTED", "AMBIGUOUS", "NEEDS_SECOND_REVIEW"}


class AnnotationEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:12].upper()}")
    asset_id: str
    reviewer_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str  # ACCEPT, REJECT, SKIP, UPDATE_ANNOTATION, etc.
    review_status: str  # VERIFIED, REJECTED, AMBIGUOUS, NEEDS_SECOND_REVIEW
    old_value: Optional[Dict[str, Any]] = None
    new_value: Dict[str, Any]
    review_notes: str = ""


class ReviewStore:
    def __init__(self, ledger_path: Path = Path("data/reviews/annotation_events.jsonl")):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.events: List[AnnotationEvent] = []
        self._load_ledger()

    def _load_ledger(self):
        if not self.ledger_path.exists():
            return
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self.events.append(AnnotationEvent(**data))
                except Exception as e:
                    logger.warning("Corrupt or invalid event skipped: %s", e)

    def record_event(
        self,
        asset_id: str,
        reviewer_id: str,
        action: str,
        new_value: Dict[str, Any],
        old_value: Optional[Dict[str, Any]] = None,
        review_notes: str = "",
    ) -> AnnotationEvent:
        """Appends an immutable audit event to the ledger."""
        if action not in VALID_ACTIONS:
            raise ValueError(f"Invalid review action '{action}'. Must be one of {VALID_ACTIONS}")

        # Map action to canonical state
        if action == "ACCEPT":
            status = "VERIFIED"
        elif action == "REJECT":
            status = "REJECTED"
        elif action == "FLAG_AMBIGUOUS":
            status = "AMBIGUOUS"
        elif action == "REQUEST_SECOND_REVIEW":
            status = "NEEDS_SECOND_REVIEW"
        elif action == "UPDATE_ANNOTATION":
            status = "VERIFIED"
        else:
            status = "PENDING"

        event = AnnotationEvent(
            asset_id=asset_id,
            reviewer_id=reviewer_id,
            action=action,
            review_status=status,
            old_value=old_value,
            new_value=new_value,
            review_notes=review_notes,
        )

        # Append to file
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.dict()) + "\n")

        self.events.append(event)
        logger.info("Recorded audit event %s for asset %s [Action: %s, Status: %s]",
                    event.event_id, asset_id, action, status)
        return event

    def get_latest_asset_status(self, asset_id: str) -> str:
        """Computes current asset review status by inspecting latest event."""
        matching = [e for e in self.events if e.asset_id == asset_id]
        if not matching:
            return "PENDING"
        return matching[-1].review_status

    def get_status_summary(self) -> Dict[str, int]:
        """Returns counts for all assets across review states."""
        latest_states: Dict[str, str] = {}
        for e in self.events:
            latest_states[e.asset_id] = e.review_status

        summary = {s: 0 for s in VALID_STATES}
        for st in latest_states.values():
            if st in summary:
                summary[st] += 1
        return summary
