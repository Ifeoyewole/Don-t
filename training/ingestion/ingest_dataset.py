"""Commercial Dataset Ingestion Orchestrator.

CLI and programmatic pipeline coordinating:
1. Source verification via CommercialSourceRegistry
2. Static license & provenance validation
3. Cryptographic and perceptual hashing
4. Quarantine staging
5. Canonical annotation normalization
6. Candidate manifest building
7. Safe promotion to production datasets
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

from .source_registry import registry
from .validate_license import audit_license
from .validate_provenance import audit_provenance
from .hash_assets import compute_asset_hashes
from .normalize_annotations import create_normalized_annotation
from .quarantine import QuarantineManager
from .build_manifest import ManifestAssetRecord, build_manifest
from .promote_dataset import ProductionPromoter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_dataset")


def ingest_directory(
    source_id: str,
    input_dir: Path,
    quarantine_root: Path,
    production_root: Path,
    promote: bool = False,
) -> int:
    """Ingests image assets from a local directory under strict commercial provenance rules."""
    source = registry.get_source(source_id)
    if not source:
        logger.error("Source ID '%s' not registered in CommercialSourceRegistry! Ingestion aborted.", source_id)
        return 1

    logger.info("Ingesting assets for source: %s (%s)", source.name, source.source_id)
    logger.info("Source Type: %s | Approval Status: %s", source.source_type, source.approval_status)

    # 1. License & Provenance pre-flight
    lic_audit = audit_license(source.license_name)
    prov_audit = audit_provenance(
        source_url=source.source_url,
        provider=source.provider,
        license_name=source.license_name,
        is_synthetic=(source.source_type == "SYNTHETIC"),
        is_owned=(source.source_type in ["OWNED_REAL", "FIELD_DATA"]),
    )

    quarantine_mgr = QuarantineManager(quarantine_root)
    promoter = ProductionPromoter(production_root)

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    image_files = [f for f in input_dir.rglob("*") if f.suffix.lower() in image_extensions]
    logger.info("Discovered %d candidate image files in %s", len(image_files), input_dir)

    candidate_records: List[ManifestAssetRecord] = []

    for idx, img_path in enumerate(image_files):
        asset_id = f"JI-{source_id}-{idx+1:06d}"
        sha256_val, dhash_val = compute_asset_hashes(img_path)

        # Stage in quarantine
        q_item = quarantine_mgr.stage_asset(
            item_id=asset_id,
            source_id=source_id,
            original_uri=str(img_path),
            license_name=source.license_name,
            provider=source.provider,
            source_url=source.source_url,
            is_synthetic=(source.source_type == "SYNTHETIC"),
            is_owned=(source.source_type in ["OWNED_REAL", "FIELD_DATA"]),
            is_benchmark_only=source.benchmark_only,
        )

        review_status = (
            "AUTO_APPROVED_SYNTHETIC"
            if source.source_type == "SYNTHETIC" and source.approval_status == "APPROVED_PRODUCTION"
            else "PENDING"
        )

        record = ManifestAssetRecord(
            asset_id=asset_id,
            sha256=sha256_val,
            perceptual_hash=dhash_val,
            source_id=source_id,
            source_original_id=img_path.stem,
            original_filename=img_path.name,
            commercial_training_allowed=source.commercial_training_allowed and lic_audit.commercial_training_allowed,
            production_eligible=source.production_eligible and lic_audit.is_commercial_valid and prov_audit.is_provenance_verified,
            license=source.license_name,
            attribution_required=source.attribution_required,
            ingestion_timestamp=datetime.now(timezone.utc).isoformat(),
            source_video=None,
            source_inspection=None,
            annotation_status="PENDING",
            review_status=review_status,
            image_rel_path=str(img_path),
            condition_class="NORMAL_JOINT",
        )
        candidate_records.append(record)

    logger.info("Staged %d assets in quarantine.", len(candidate_records))

    if promote:
        logger.info("Attempting promotion to production dataset...")
        result = promoter.promote_assets(candidate_records)
        if not result.is_success:
            logger.warning("Promotion rejected: %s", result.rejection_reasons)
            return 2
        logger.info("Promotion successful! Promoted %d assets.", result.promoted_count)

    return 0


def main():
    parser = argparse.ArgumentParser(description="Commercial Dataset Ingestion Pipeline")
    parser.add_argument("--source-id", required=True, help="Registered source ID (e.g. SRC-SYN-001)")
    parser.add_argument("--input-dir", required=True, type=Path, help="Input directory containing raw images")
    parser.add_argument("--quarantine-dir", default=Path("data/quarantine"), type=Path, help="Quarantine directory")
    parser.add_argument("--production-dir", default=Path("data/production/jointinspect-v1"), type=Path, help="Production directory")
    parser.add_argument("--promote", action="store_true", help="Attempt promotion if eligible")

    args = parser.parse_args()
    code = ingest_directory(
        source_id=args.source_id,
        input_dir=args.input_dir,
        quarantine_root=args.quarantine_dir,
        production_root=args.production_dir,
        promote=args.promote,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
