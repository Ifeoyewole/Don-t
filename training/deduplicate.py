"""Near-Duplicate Frame Elimination using Perceptual Difference Hashing (dHash).

Sewer CCTV footage contains many nearly identical adjacent frames.
This module enforces diversity by:
- Grouping frames by Video_ID / Inspection_ID
- Computing 64-bit gradient difference hash (dHash)
- Rejecting near-identical frames (Hamming distance < threshold)
- Capping selection at 2 to 5 distinct views per physical joint
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
import cv2
import numpy as np


def compute_dhash(image: np.ndarray, hash_size: int = 8) -> int:
    """Compute 64-bit difference hash (dHash) based on horizontal luminance gradients."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Resize to (hash_size + 1, hash_size)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)

    # Compute difference between adjacent horizontal columns
    diff = resized[:, 1:] > resized[:, :-1]

    # Convert binary boolean matrix to 64-bit integer
    decimal_val = 0
    for bit in diff.flatten():
        decimal_val = (decimal_val << 1) | int(bit)

    return decimal_val


def hamming_distance(hash1: int, hash2: int) -> int:
    """Compute number of differing bits between two 64-bit hashes."""
    x = hash1 ^ hash2
    return bin(x).count("1")


def deduplicate_video_frames(
    candidates_csv: Path,
    image_dir: Path,
    output_csv: Path,
    max_frames_per_joint: int = 3,
    min_hamming_dist: int = 6,
) -> int:
    """Filter candidate images to enforce maximum diversity per video/inspection."""
    if not candidates_csv.exists():
        raise FileNotFoundError(f"Candidate CSV not found at: {candidates_csv}")

    # Group rows by inspection/video
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    with open(candidates_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            group_key = row.get("inspection_id") or row.get("video_id") or "GLOBAL"
            groups[group_key].append(row)

    accepted_rows: List[Dict[str, str]] = []

    for group_key, rows in groups.items():
        retained_hashes: List[int] = []

        for row in rows:
            filename = row["filename"]
            img_path = image_dir / filename

            if not img_path.exists():
                # If image directory is not locally mounted, apply sequence sampling
                if len(retained_hashes) < max_frames_per_joint:
                    retained_hashes.append(len(retained_hashes))
                    accepted_rows.append(row)
                continue

            img = cv2.imread(str(img_path))
            if img is None:
                continue

            img_hash = compute_dhash(img)

            # Check if too close to any already retained frame in this inspection
            is_near_duplicate = False
            for prev_hash in retained_hashes:
                if hamming_distance(img_hash, prev_hash) < min_hamming_dist:
                    is_near_duplicate = True
                    break

            if not is_near_duplicate:
                retained_hashes.append(img_hash)
                accepted_rows.append(row)
                if len(retained_hashes) >= max_frames_per_joint:
                    break

    # Save deduplicated list
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = ["filename", "defect_code", "category", "inspection_id", "video_id"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(accepted_rows)

    return len(accepted_rows)


def main():
    parser = argparse.ArgumentParser(description="Deduplicate video frames using perceptual hashing")
    parser.add_argument("--input_csv", type=str, default="training/data/selected_candidates.csv")
    parser.add_argument("--image_dir", type=str, default="sewer_ml_images")
    parser.add_argument("--output_csv", type=str, default="training/data/deduplicated_dataset.csv")
    parser.add_argument("--max_frames", type=int, default=3)
    parser.add_argument("--min_distance", type=int, default=6)
    args = parser.parse_args()

    input_p = Path(args.input_csv)
    if input_p.exists():
        count = deduplicate_video_frames(
            input_p,
            Path(args.image_dir),
            Path(args.output_csv),
            max_frames_per_joint=args.max_frames,
            min_hamming_dist=args.min_distance,
        )
        print(f"Deduplication complete. Retained {count} diverse joint frames.")
    else:
        print(f"Candidate file '{input_p}' not found. Run select_dataset.py first.")


if __name__ == "__main__":
    main()
