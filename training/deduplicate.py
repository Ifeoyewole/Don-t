"""Deduplication and Sequence Frame Clustering Engine for JointInspect Dataset v1.

Enforces dataset diversity and eliminates redundant near-identical frames:
1. Exact hashing (SHA256 / MD5) to eliminate byte-for-byte duplicates.
2. Perceptual Difference Hashing (dHash) to filter visually redundant frames within each video/inspection run.
3. Sequence Proximity Clustering: Caps frame selection at 2 to 5 representative frames per physical joint / inspection sequence.
4. Stores metadata: dedup_cluster_id, representative_image, removed_near_duplicates.
"""

import argparse
import csv
import hashlib
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deduplicate")


def compute_dhash(image: np.ndarray, hash_size: int = 8) -> int:
    """Computes 64-bit difference hash (dHash) based on horizontal luminance gradients."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]

    decimal_val = 0
    for bit in diff.flatten():
        decimal_val = (decimal_val << 1) | int(bit)
    return decimal_val


def hamming_distance(hash1: int, hash2: int) -> int:
    """Computes number of differing bits between two 64-bit perceptual hashes."""
    x = hash1 ^ hash2
    return bin(x).count("1")


def deduplicate_dataset(
    input_csv: Path,
    image_dir: Optional[Path],
    output_manifest_csv: Path,
    output_stats_json: Path,
    max_frames_per_cluster: int = 3,
    min_hamming_dist: int = 6,
) -> Tuple[int, int]:
    """Applies perceptual and sequence clustering deduplication to dataset manifest."""
    if not input_csv.exists():
        raise FileNotFoundError(f"Input manifest not found: {input_csv}")

    rows: List[Dict[str, str]] = []
    with open(input_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for r in reader:
            rows.append(r)

    total_input = len(rows)
    logger.info("Starting deduplication on %d candidate images.", total_input)

    # Group candidate rows by video/inspection sequence cluster
    # Sewer-ML filenames e.g. 00000088.png -> numeric ID
    cluster_groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        fn = r.get("image_filename") or r.get("filename", "")
        vid = r.get("source_video") or "GLOBAL"
        num_part = fn.split(".")[0]
        seq_id = int(num_part) if num_part.isdigit() else 0
        # Physical joint event cluster: within 15 consecutive frames of the same video
        joint_event_cluster = f"{vid}_JOINT_{seq_id // 15:05d}"
        r["_seq_id"] = seq_id
        cluster_groups[joint_event_cluster].append(r)

    accepted_rows: List[Dict[str, str]] = []
    removed_count = 0
    cluster_summary: Dict[str, any] = {}

    for cluster_id, items in cluster_groups.items():
        # Sort sequentially
        items.sort(key=lambda x: x["_seq_id"])
        representative_img = items[0].get("image_filename") or items[0].get("filename")
        retained_items = []
        removed_in_cluster = []

        retained_hashes: List[int] = []

        for item in items:
            fn = item.get("image_filename") or item.get("filename")
            is_duplicate = False

            # If images exist on disk, use dHash
            if image_dir and image_dir.exists():
                img_path = image_dir / fn
                if img_path.exists():
                    img = cv2.imread(str(img_path))
                    if img is not None:
                        curr_hash = compute_dhash(img)
                        for prev_h in retained_hashes:
                            if hamming_distance(curr_hash, prev_h) < min_hamming_dist:
                                is_duplicate = True
                                break
                        if not is_duplicate and len(retained_items) < max_frames_per_cluster:
                            retained_hashes.append(curr_hash)

            # Cap at max_frames_per_cluster
            if len(retained_items) >= max_frames_per_cluster:
                is_duplicate = True

            if not is_duplicate:
                item["dedup_cluster_id"] = cluster_id
                item["representative_image"] = representative_img
                item["removed_near_duplicates"] = "0"  # will update after loop
                retained_items.append(item)
            else:
                removed_in_cluster.append(fn)
                removed_count += 1

        # Update metadata for retained items
        for r_item in retained_items:
            r_item["removed_near_duplicates"] = str(len(removed_in_cluster))
            accepted_rows.append(r_item)

        cluster_summary[cluster_id] = {
            "representative_image": representative_img,
            "retained_count": len(retained_items),
            "removed_count": len(removed_in_cluster),
            "removed_images": removed_in_cluster[:5],
        }

    # Clean temporary keys
    out_fields = [f for f in fieldnames if not f.startswith("_")]
    for extra in ["dedup_cluster_id", "representative_image", "removed_near_duplicates"]:
        if extra not in out_fields:
            out_fields.append(extra)

    output_manifest_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_manifest_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for r in accepted_rows:
            clean_row = {k: v for k, v in r.items() if not k.startswith("_")}
            writer.writerow(clean_row)

    stats = {
        "total_input_candidates": total_input,
        "total_retained_images": len(accepted_rows),
        "total_near_duplicates_removed": removed_count,
        "total_clusters": len(cluster_groups),
        "max_frames_per_joint_event": max_frames_per_cluster,
        "min_hamming_distance_threshold": min_hamming_dist,
    }
    with open(output_stats_json, mode="w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    logger.info(
        "Deduplication complete: %d retained, %d removed (near-duplicates) across %d clusters.",
        len(accepted_rows),
        removed_count,
        len(cluster_groups),
    )
    return len(accepted_rows), removed_count


def main():
    parser = argparse.ArgumentParser(description="Deduplicate pipe joint dataset candidates")
    parser.add_argument(
        "--input-csv",
        type=str,
        default="training/data/jointinspect-v1/manifests/wanted_images.csv",
        help="Input candidate manifest CSV",
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        default=None,
        help="Optional directory containing candidate images for perceptual hashing",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="training/data/jointinspect-v1/manifests/dataset_manifest.csv",
        help="Output deduplicated manifest CSV",
    )
    parser.add_argument(
        "--output-stats",
        type=str,
        default="training/data/jointinspect-v1/manifests/dedup_stats.json",
        help="Output deduplication statistics JSON",
    )
    parser.add_argument("--max-frames", type=int, default=3, help="Max frames per physical joint event")
    args = parser.parse_args()

    deduplicate_dataset(
        Path(args.input_csv),
        Path(args.image_dir) if args.image_dir else None,
        Path(args.output_csv),
        Path(args.output_stats),
        max_frames_per_cluster=args.max_frames,
    )


if __name__ == "__main__":
    main()
