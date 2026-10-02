"""Quarantine Layer Management.

Ensures no raw, unverified, or third-party datasets directly contaminate production training.
All external and partner assets enter quarantine staging first.

GCS Layout / Local Staging:
datasets/
├── quarantine/
├── production/
│   └── jointinspect-v1/
├── synthetic/
│   └── jointinspect-synthetic-v1/
├── owned-real/
├── partner-data/
└── benchmarks/
    └── sewerml/
        └── permission-pending/
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from .validate_license import audit_license
from .validate_provenance import audit_provenance

logger = logging.getLogger("quarantine")


class QuarantineItem(BaseModel):
    item_id: str
    source_id: str
    original_uri: str
    quarantine_path: str
    ingested_at: str
    license_name: str
    license_ok: bool
    provenance_ok: bool
    quarantine_status: str  # "QUARANTINED", "REJECTED", "APPROVED_PENDING_PROMOTION", "BENCHMARK_ISOLATED"
    rejection_reasons: List[str]
    notes: str


class QuarantineManager:
    def __init__(self, quarantine_root: Path):
        self.root = quarantine_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_file = self.root / "quarantine_index.json"
        self.items: Dict[str, QuarantineItem] = {}
        self.load()

    def load(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for raw in data.get("quarantined_items", []):
                    item = QuarantineItem(**raw)
                    self.items[item.item_id] = item
            except Exception as e:
                logger.error("Failed to load quarantine index: %s", e)

    def save(self):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "total_quarantined": len(self.items),
                    "quarantined_items": [i.dict() for i in self.items.values()],
                },
                f,
                indent=2,
            )

    def stage_asset(
        self,
        item_id: str,
        source_id: str,
        original_uri: str,
        license_name: str,
        provider: str,
        source_url: Optional[str] = None,
        license_text: str = "",
        is_synthetic: bool = False,
        is_owned: bool = False,
        is_direct_partner: bool = False,
        is_benchmark_only: bool = False,
    ) -> QuarantineItem:
        """Stages an asset in quarantine and executes automatic safety & provenance checks."""
        # Run license audit
        lic_result = audit_license(license_name, license_text)

        # Run provenance audit
        prov_result = audit_provenance(
            source_url=source_url,
            provider=provider,
            license_name=license_name,
            is_direct_partner=is_direct_partner,
            is_synthetic=is_synthetic,
            is_owned=is_owned,
        )

        rejection_reasons = []
        if not lic_result.is_commercial_valid and not is_benchmark_only:
            rejection_reasons.extend(lic_result.rejection_reasons)
        if not prov_result.is_provenance_verified and not is_benchmark_only:
            rejection_reasons.extend(prov_result.rejection_reasons)

        if is_benchmark_only:
            status = "BENCHMARK_ISOLATED"
        elif rejection_reasons:
            status = "REJECTED"
        else:
            status = "QUARANTINED"  # Needs manual review before promotion

        item_quarantine_dir = self.root / source_id / item_id
        item_quarantine_dir.mkdir(parents=True, exist_ok=True)

        item = QuarantineItem(
            item_id=item_id,
            source_id=source_id,
            original_uri=original_uri,
            quarantine_path=str(item_quarantine_dir),
            ingested_at=datetime.now(timezone.utc).isoformat(),
            license_name=license_name,
            license_ok=lic_result.is_commercial_valid,
            provenance_ok=prov_result.is_provenance_verified,
            quarantine_status=status,
            rejection_reasons=rejection_reasons,
            notes=prov_result.audit_notes,
        )

        self.items[item_id] = item
        self.save()
        logger.info("Asset %s staged in quarantine with status: %s", item_id, status)
        return item
