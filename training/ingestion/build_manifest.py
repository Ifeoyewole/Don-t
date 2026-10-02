"""Production Dataset Manifest Builder.

Constructs immutable, cryptographically verifiable dataset manifests.
Every imported image receives the mandatory 15 metadata attributes:
- asset_id
- sha256
- perceptual_hash
- source_id
- source_original_id
- original_filename
- commercial_training_allowed
- production_eligible
- license
- attribution_required
- ingestion_timestamp
- source_video
- source_inspection
- annotation_status
- review_status
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .hash_assets import compute_sha256_bytes

logger = logging.getLogger("build_manifest")


class ManifestAssetRecord(BaseModel):
    asset_id: str
    sha256: str
    perceptual_hash: str
    source_id: str
    source_original_id: str
    original_filename: str
    commercial_training_allowed: bool
    production_eligible: bool
    license: str
    attribution_required: bool
    ingestion_timestamp: str
    source_video: Optional[str] = None
    source_inspection: Optional[str] = None
    annotation_status: str = "PENDING"  # PENDING, NORMALIZED, VERIFIED, REJECTED
    review_status: str = "PENDING"  # PENDING, APPROVED_PRODUCTION, REJECTED, NEEDS_SECOND_REVIEW
    # Additional canonical attributes
    image_rel_path: str
    mask_rel_path: Optional[str] = None
    condition_class: Optional[str] = None
    ground_truth_gap_mm: Optional[float] = None
    measurement_method: Optional[str] = None
    pipe_diameter_mm: Optional[float] = None
    dedup_cluster_id: Optional[str] = None


class DatasetManifest(BaseModel):
    dataset_version: str
    created_at: str
    image_count: int
    class_distribution: Dict[str, int]
    source_distribution: Dict[str, int]
    real_count: int
    synthetic_count: int
    licensed_public_count: int
    owned_count: int
    manifest_sha256: str = ""
    annotation_version: str
    split_version: str
    assets: List[ManifestAssetRecord] = Field(default_factory=list)


def build_manifest(
    dataset_version: str,
    assets: List[ManifestAssetRecord],
    annotation_version: str = "v1.0",
    split_version: str = "v1.0",
    output_path: Optional[Path] = None,
) -> DatasetManifest:
    """Builds and computes cryptographic hash for a canonical dataset manifest."""
    class_dist: Dict[str, int] = {}
    src_dist: Dict[str, int] = {}
    real_count = 0
    synthetic_count = 0
    licensed_public_count = 0
    owned_count = 0

    for a in assets:
        cls = a.condition_class or "UNKNOWN"
        class_dist[cls] = class_dist.get(cls, 0) + 1
        src_dist[a.source_id] = src_dist.get(a.source_id, 0) + 1

        if "SYN" in a.source_id.upper():
            synthetic_count += 1
        elif "OWN" in a.source_id.upper() or "FLD" in a.source_id.upper():
            owned_count += 1
            real_count += 1
        elif "PUB" in a.source_id.upper():
            licensed_public_count += 1
            real_count += 1
        else:
            real_count += 1

    manifest = DatasetManifest(
        dataset_version=dataset_version,
        created_at=datetime.now(timezone.utc).isoformat(),
        image_count=len(assets),
        class_distribution=class_dist,
        source_distribution=src_dist,
        real_count=real_count,
        synthetic_count=synthetic_count,
        licensed_public_count=licensed_public_count,
        owned_count=owned_count,
        annotation_version=annotation_version,
        split_version=split_version,
        assets=assets,
    )

    # Compute manifest SHA256 excluding manifest_sha256 itself
    raw_json = json.dumps(manifest.dict(exclude={"manifest_sha256"}), sort_keys=True).encode("utf-8")
    manifest.manifest_sha256 = compute_sha256_bytes(raw_json)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(manifest.dict(), indent=2))
        logger.info("Manifest saved to %s with SHA256: %s", output_path, manifest.manifest_sha256)

    return manifest
