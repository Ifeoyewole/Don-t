"""Select a *human review worklist* from quarantined Roboflow registries.

Never constructs guessed GCS image paths, ROIs, adjudicated ground truth, or
commercial training authorization. This is not an executable GPU manifest.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

COLUMNS = (
    "review_status", "candidate_bucket", "dataset_name", "source",
    "source_image_path", "source_media_id", "source_labels", "image_sha256",
    "width", "height", "split", "duplicate_status",
    "image_uri_TO_VERIFY", "roi_x0", "roi_y0", "roi_x1", "roi_y1",
    "geometry_TO_REVIEW", "source_family_TO_VERIFY", "rights_review",
    "annotation_review", "reviewed_ground_truth_label", "review_id",
)


def _bucket(labels: list[str]) -> str:
    # Only candidate search buckets, NOT authoritative labels. E.g. Leak
    # may be staining rather than actual infiltration.
    words = {str(name).strip().lower() for name in labels}
    if words & {"joint offset", "offset joint"}:
        return "JOINT_DISPLACEMENT_CANDIDATE"
    if "utility intrusion" in words:
        return "PROTRUDING_LATERAL_CANDIDATE_UNVERIFIED"
    if "leak" in words:
        return "INFILTRATION_CANDIDATE_UNVERIFIED"
    if "normal" in words or "no defect" in words:
        return "NORMAL_CANDIDATE_UNVERIFIED"
    return "HARD_NEGATIVE_OR_OTHER_CANDIDATE"


def select_candidates(registries: list[dict[str, Any]], *, target: int = 80) -> list[dict[str, Any]]:
    if not 1 <= target <= 100:
        raise ValueError("Target must be between 1 and 100")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_sha = set()
    seen_dhash = set()
    for registry in registries:
        if not isinstance(registry, dict) or not isinstance(registry.get("records"), list):
            raise ValueError("Invalid Roboflow source registry")
        if registry.get("commercial_training_eligible") is not False:
            raise ValueError("This worklist builder accepts explicit quarantine source registries only")
        for r in registry["records"]:
            if not isinstance(r, dict):
                continue
            sha = r.get("sha256")
            dhash = r.get("dhash")
            if not isinstance(sha, str) or len(sha) != 64:
                continue
            # Both true exact duplicates and baseline/intra-source dHash
            # collisions are filtered. Near-duplicates still need review.
            if not str(r.get("duplicate_status", "")).startswith("NOT_EXACT_DUPLICATE"):
                continue
            if sha in seen_sha or (isinstance(dhash, str) and dhash in seen_dhash):
                continue
            seen_sha.add(sha)
            if isinstance(dhash, str):
                seen_dhash.add(dhash)
            labels = r.get("source_labels") or []
            if not isinstance(labels, list):
                continue
            bucket = _bucket(labels)
            groups[bucket].append({
                "review_status": "NEEDS_HUMAN_REVIEW",
                "candidate_bucket": bucket,
                "dataset_name": str(r.get("dataset_name", registry.get("dataset_name", ""))),
                "source": str(r.get("source", registry.get("source", ""))),
                "source_image_path": str(r.get("original_image_path", "")),
                "source_media_id": str(r.get("original_media_id", "")),
                "source_labels": "|".join(str(s) for s in labels),
                "image_sha256": sha,
                "width": r.get("width"), "height": r.get("height"),
                "split": r.get("split"),
                "duplicate_status": r.get("duplicate_status"),
                "image_uri_TO_VERIFY": "",
                "roi_x0": "", "roi_y0": "", "roi_x1": "", "roi_y1": "",
                "geometry_TO_REVIEW": "",
                "source_family_TO_VERIFY": "",
                "rights_review": "RESEARCH_QUARANTINE",
                "annotation_review": "UNVERIFIED_SOURCE_LABEL",
                "reviewed_ground_truth_label": "", "review_id": "",
            })
    # Intentionally do NOT select an "OPEN_JOINT" class from generic joint
    # labels: those need manual annotation from actual imagery.
    quotas = [
        ("JOINT_DISPLACEMENT_CANDIDATE", 20),
        ("PROTRUDING_LATERAL_CANDIDATE_UNVERIFIED", 20),
        ("INFILTRATION_CANDIDATE_UNVERIFIED", 10),
        ("NORMAL_CANDIDATE_UNVERIFIED", 15),
        ("HARD_NEGATIVE_OR_OTHER_CANDIDATE", 15),
    ]
    selected = []
    chosen = set()
    for category, count in quotas:
        for row in groups.get(category, [])[:min(count, target - len(selected))]:
            selected.append(row)
            chosen.add(row["image_sha256"])
        if len(selected) >= target:
            return selected
    # Backfill empty categories from genuine available samples, never by
    # inventing positives for an unsupported class.
    for category, _ in quotas:
        for row in groups.get(category, []):
            if len(selected) >= target:
                return selected
            if row["image_sha256"] not in chosen:
                chosen.add(row["image_sha256"])
                selected.append(row)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target", type=int, default=80)
    args = parser.parse_args()
    registries = []
    for path in args.registry:
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Registry exceeds allowed metadata-only limit")
        registries.append(json.loads(path.read_text(encoding="utf-8")))
    rows = select_candidates(registries, target=args.target)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    summary = Counter(r["candidate_bucket"] for r in rows)
    print(json.dumps({
        "review_worklist": str(args.out), "selected": len(rows),
        "candidate_counts": dict(summary),
        "all_images_require_manual_ROI_and_provenance_review": True,
        "automatic_training_or_accuracy_authorized": False,
    }, indent=2))


if __name__ == "__main__":
    main()
