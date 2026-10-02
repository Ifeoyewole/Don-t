"""Data Source Registry Management & Invariant Enforcement.

Enforces:
- Schema validation for all registered data sources.
- Strict Fail-Closed Rule: Any source with approval_status == 'UNKNOWN_RIGHTS'
  automatically forces production_eligible = False and commercial_training_allowed = False.
- Strict isolation of BENCHMARK_ONLY sources.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("source_registry")

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data_sources" / "source_registry.json"


class DataSourceRecord(BaseModel):
    source_id: str
    name: str
    source_type: str
    source_url: Optional[str] = None
    provider: str
    license_name: str
    license_url: Optional[str] = None
    license_text_reference: str
    commercial_training_allowed: bool
    commercial_deployment_allowed: bool
    modification_allowed: bool
    redistribution_allowed: bool
    attribution_required: bool
    share_alike_required: bool
    provenance_verified: bool
    production_eligible: bool
    benchmark_only: bool
    rights_document_reference: Optional[str] = None
    approval_status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    notes: str = ""


class CommercialSourceRegistry:
    def __init__(self, registry_file: Path = REGISTRY_PATH):
        self.registry_file = registry_file
        self.sources: Dict[str, DataSourceRecord] = {}
        self.load()

    def load(self):
        if not self.registry_file.exists():
            raise FileNotFoundError(f"Source registry file not found: {self.registry_file}")

        with open(self.registry_file, mode="r", encoding="utf-8") as f:
            data = json.load(f)

        for raw_src in data.get("sources", []):
            # Invariant 1: UNKNOWN_RIGHTS must force production_eligible = False
            if raw_src.get("approval_status") == "UNKNOWN_RIGHTS":
                raw_src["production_eligible"] = False
                raw_src["commercial_training_allowed"] = False

            # Invariant 2: BENCHMARK_ONLY must force production_eligible = False
            if raw_src.get("benchmark_only") or raw_src.get("source_type") == "BENCHMARK_ONLY":
                raw_src["production_eligible"] = False
                raw_src["commercial_training_allowed"] = False

            record = DataSourceRecord(**raw_src)
            self.sources[record.source_id] = record

        logger.info("Loaded %d commercial data sources from registry.", len(self.sources))

    def get_source(self, source_id: str) -> Optional[DataSourceRecord]:
        return self.sources.get(source_id)

    def is_eligible_for_production_training(self, source_id: str) -> bool:
        src = self.get_source(source_id)
        if not src:
            return False
        return (
            src.production_eligible
            and src.commercial_training_allowed
            and src.approval_status == "APPROVED_PRODUCTION"
            and not src.benchmark_only
        )

    def list_production_eligible_sources(self) -> List[DataSourceRecord]:
        return [s for s in self.sources.values() if self.is_eligible_for_production_training(s.source_id)]

    def list_benchmark_sources(self) -> List[DataSourceRecord]:
        return [s for s in self.sources.values() if s.benchmark_only or s.source_type == "BENCHMARK_ONLY"]


registry = CommercialSourceRegistry()
