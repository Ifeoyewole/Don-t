"""Sewer-ML Dataset Selection and Multi-Stage Normal Joint Filtering Tool.

Filters official Sewer-ML annotations CSV to curate a balanced 5,000 image Pipe Joint Dataset:
- 1,750 Displaced joints (FS)
- 1,250 Normal healthy joints (via annular feature candidate filter + review)
- 700 Cracks/breaks/deformation (RB, DE)
- 350 Intruding sealing material (IS)
- 350 Hard negative distractors (RO, AF, BE, FO)
- 600 Difficult-condition samples
"""

import argparse
import csv
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import cv2
import numpy as np


OFFICIAL_SEWER_ML_MAPPING = {
    "FS": "displaced_joint",
    "RB": "cracks_breaks",
    "DE": "deformation",
    "IS": "intruding_seal",
    "RO": "distractor_roots",
    "AF": "distractor_settled_deposits",
    "BE": "distractor_attached_deposits",
    "FO": "distractor_obstacle",
}


def filter_sewer_ml_csv(
    csv_path: Path,
    image_dir: Path,
    output_csv: Path,
    target_counts: Dict[str, int],
) -> Dict[str, int]:
    """Parse Sewer-ML annotations CSV and select candidate samples per target class."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Sewer-ML annotations CSV not found at: {csv_path}")

    counts: Dict[str, int] = {k: 0 for k in target_counts}
    selected_rows: List[Dict[str, str]] = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("Filename") or row.get("filename") or row.get("image_name")
            defect_code = row.get("DefectCode") or row.get("defect_code") or row.get("Defect")

            if not filename or not defect_code:
                continue

            # Map defect code to dataset target category
            matched_category = None
            if defect_code == "FS":
                matched_category = "displaced_joint"
            elif defect_code in ("RB", "DE"):
                matched_category = "cracks_deformation"
            elif defect_code == "IS":
                matched_category = "intruding_seal"
            elif defect_code in ("RO", "AF", "BE", "FO"):
                matched_category = "hard_negatives"

            if matched_category and counts[matched_category] < target_counts.get(matched_category, 0):
                img_path = image_dir / filename
                if img_path.exists() or not image_dir.exists():
                    selected_rows.append({
                        "filename": filename,
                        "defect_code": defect_code,
                        "category": matched_category,
                        "inspection_id": row.get("Inspection_ID", "UNKNOWN"),
                        "video_id": row.get("Video_ID", "UNKNOWN"),
                    })
                    counts[matched_category] += 1

    # Write selected candidate list
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "defect_code", "category", "inspection_id", "video_id"])
        writer.writeheader()
        writer.writerows(selected_rows)

    return counts


def filter_healthy_joint_candidates(
    normal_image_paths: List[Path],
    output_dir: Path,
    target_count: int = 1250,
) -> List[Path]:
    """Multi-stage funnel to ensure normal Sewer-ML images actually contain visible joints.

    A plain Sewer-ML normal image often shows a featureless pipe wall with NO joint visible.
    This stage applies an annular edge & circularity filter to select images with true visible joints,
    saving candidate thumbnails for human verification review.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    verified_candidates: List[Path] = []

    for img_path in normal_image_paths:
        if len(verified_candidates) >= target_count:
            break

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        min_dim = min(h, w)

        # Look for circular/annular joint contours
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.2)
        edges = cv2.Canny(blurred, 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        has_annular_feature = False
        for cnt in contours:
            area = cv2.contourArea(cnt)
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0 and area > (min_dim * min_dim * 0.05):
                circularity = 4 * np.pi * (area / (perimeter * perimeter))
                if circularity > 0.40:
                    has_annular_feature = True
                    break

        if has_annular_feature:
            verified_candidates.append(img_path)
            # Save thumbnail for inspector review
            thumb = cv2.resize(img, (256, 256))
            cv2.imwrite(str(output_dir / f"cand_{img_path.name}"), thumb)

    return verified_candidates


def main():
    parser = argparse.ArgumentParser(description="Filter Sewer-ML images for Pipe Joint Dataset")
    parser.add_argument("--csv", type=str, default="SewerML_annotations.csv", help="Path to Sewer-ML CSV")
    parser.add_argument("--image_dir", type=str, default="sewer_ml_images", help="Directory containing Sewer-ML images")
    parser.add_argument("--output", type=str, default="training/data/selected_candidates.csv", help="Output CSV path")
    args = parser.parse_args()

    targets = {
        "displaced_joint": 1750,
        "cracks_deformation": 700,
        "intruding_seal": 350,
        "hard_negatives": 350,
    }

    print("Filtering Sewer-ML metadata...")
    csv_path = Path(args.csv)
    if csv_path.exists():
        counts = filter_sewer_ml_csv(csv_path, Path(args.image_dir), Path(args.output), targets)
        print(f"Selection complete: {counts}")
    else:
        print(f"Note: Sewer-ML CSV '{csv_path}' not present locally. Ready to run when dataset is mounted.")


if __name__ == "__main__":
    main()
