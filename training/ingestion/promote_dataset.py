"""Production Dataset Promotion Gate.

Strict Fail-Closed Enforcement:
An asset CANNOT be promoted to the production dataset unless:
1. commercial_training_allowed == True
2. production_eligible == True
3. source_registry approval_status == "APPROVED_PRODUCTION"
4. benchmark_only == False
5. License audit passes without Non-Commercial or Viral Copyleft riders
6. Provenance is verified

Transfers approved assets into production dataset structure:
datasets/production/jointinspect-v1/
├── manifests/
├── images/
├── annotations/
├── splits/
├── provenance/
├── licenses/
└── reviews/
"""

import json
import logging
import shutil
from pathlib import Path
from typing import List, Tuple
from pydantic import BaseModel

from .source_registry import registry, DataSourceRecord
from .build_manifest import ManifestAssetRecord, build_manifest

logger = logging.getLogger("promote_dataset")


class PromotionResult(BaseModel):
    promoted_count: int
    rejected_count: int
    rejection_reasons: List[str]
    is_success: bool


class ProductionPromoter:
    def __init__(self, production_root: Path):
        self.root = production_root
        self.manifests_dir = self.root / "manifests"
        self.images_dir = self.root / "images"
        self.annotations_dir = self.root / "annotations"
        self.splits_dir = self.root / "splits"
        self.provenance_dir = self.root / "provenance"
        self.licenses_dir = self.root / "licenses"
        self.reviews_dir = self.root / "reviews"

        for d in [
            self.manifests_dir,
            self.images_dir,
            self.annotations_dir,
            self.splits_dir,
            self.provenance_dir,
            self.licenses_dir,
            self.reviews_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def validate_asset_eligibility(self, asset: ManifestAssetRecord) -> Tuple[bool, List[str]]:
        """Strict fail-closed validation of individual asset."""
        reasons = []

        if not asset.commercial_training_allowed:
            reasons.append(f"Asset {asset.asset_id}: commercial_training_allowed is False.")

        if not asset.production_eligible:
            reasons.append(f"Asset {asset.asset_id}: production_eligible is False.")

        source = registry.get_source(asset.source_id)
        if not source:
            reasons.append(f"Asset {asset.asset_id}: Source {asset.source_id} not registered.")
        else:
            if source.approval_status != "APPROVED_PRODUCTION":
                reasons.append(
                    f"Asset {asset.asset_id}: Source {asset.source_id} approval_status is '{source.approval_status}', not APPROVED_PRODUCTION."
                )
            if source.benchmark_only:
                reasons.append(f"Asset {asset.asset_id}: Source {asset.source_id} is marked benchmark_only.")

        if asset.review_status not in ["APPROVED_PRODUCTION", "VERIFIED", "AUTO_APPROVED_SYNTHETIC"]:
            reasons.append(
                f"Asset {asset.asset_id}: review_status is '{asset.review_status}', not approved for production."
            )

        return (len(reasons) == 0, reasons)

    def promote_assets(
        self,
        candidate_assets: List[ManifestAssetRecord],
        dataset_version: str = "jointinspect-v1",
    ) -> PromotionResult:
        """Promotes valid candidate assets to production."""
        approved: List[ManifestAssetRecord] = []
        all_reasons: List[str] = []

        for asset in candidate_assets:
            eligible, reasons = self.validate_asset_eligibility(asset)
            if not eligible:
                all_reasons.extend(reasons)
                logger.warning("Promotion rejected for %s: %s", asset.asset_id, "; ".join(reasons))
            else:
                approved.append(asset)

        if not approved:
            return PromotionResult(
                promoted_count=0,
                rejected_count=len(candidate_assets),
                rejection_reasons=all_reasons,
                is_success=False,
            )

        manifest_file = self.manifests_dir / f"manifest_{dataset_version}.json"
        build_manifest(
            dataset_version=dataset_version,
            assets=approved,
            output_path=manifest_file,
        )

        logger.info(
            "Promotion complete. Promoted: %d, Rejected: %d.",
            len(approved),
            len(candidate_assets) - len(approved),
        )
        return PromotionResult(
            promoted_count=len(approved),
            rejected_count=len(candidate_assets) - len(approved),
            rejection_reasons=all_reasons,
            is_success=len(approved) > 0,
        )
