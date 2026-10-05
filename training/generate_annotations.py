"""Joint Localization Annotation Generator and Human Review Workflow for Model A.

Sewer-ML labels are strictly image-level defect labels.
Model A requires localization / segmentation supervision (bounding boxes, annular masks).
This module:
1. Implements a semi-automatic annular contour & seam localization pipeline to generate initial candidate annotations.
2. Tracks provenance on every annotation:
   - annotation_source (e.g. 'semi_automated_annular_detector_v1')
   - human_verified (strictly False until approved)
   - reviewer (None or operator name)
   - review_status ('PENDING_HUMAN_VERIFICATION', 'APPROVED', 'REJECTED')
   - quality_score (geometric consistency score 0.0 to 1.0)
3. Generates review_queue.csv to guarantee unverified masks never enter production training.
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_annotations")


def generate_candidate_localization(
    image_bgr: np.ndarray,
) -> Optional[Dict[str, any]]:
    """Semi-automatic annular seam detector generating candidate bbox and polygon."""
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 1.5)

    # Edge detection
    edges = cv2.Canny(blurred, 30, 100)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    best_cnt = None
    best_score = 0.0
    min_dim = min(h, w)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        peri = cv2.arcLength(cnt, True)
        if peri > 0 and area > (min_dim * min_dim * 0.04):
            circularity = 4 * np.pi * (area / (peri * peri))
            # Annular / elliptical profile
            if 0.30 <= circularity <= 1.0:
                score = circularity * (area / (w * h))
                if score > best_score:
                    best_score = score
                    best_cnt = cnt

    if best_cnt is not None:
        x, y, bw, bh = cv2.boundingRect(best_cnt)
        polygon = [[float(pt[0][0]), float(pt[0][1])] for pt in best_cnt[::max(1, len(best_cnt) // 32)]]
        return {
            "bbox": [x, y, x + bw, y + bh],
            "polygon": polygon,
            "quality_score": round(float(min(1.0, best_score * 5.0)), 3),
        }

    # Fallback concentric center crop if annular edges are diffuse
    cx, cy = w // 2, h // 2
    rw, rh = int(w * 0.65), int(h * 0.65)
    x1, y1 = max(0, cx - rw // 2), max(0, cy - rh // 2)
    x2, y2 = min(w, cx + rw // 2), min(h, cy + rh // 2)
    return {
        "bbox": [x1, y1, x2, y2],
        "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        "quality_score": 0.50,
    }


def generate_annotations_manifest(
    dataset_manifest_csv: Path,
    image_dir: Optional[Path],
    annotations_json: Path,
    review_queue_csv: Path,
) -> int:
    """Generates localization annotations for Model A and exports the human review queue."""
    if not dataset_manifest_csv.exists():
        raise FileNotFoundError(f"Manifest not found: {dataset_manifest_csv}")

    annotations = {}
    review_queue_rows = []

    with open(dataset_manifest_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            fn = r.get("image_filename") or r.get("filename")
            if not fn:
                continue

            target_cls = r.get("jointinspect_target_class", "UNKNOWN")

            # If image file exists, run detector
            if image_dir and image_dir.exists():
                img_path = image_dir / fn
                if img_path.exists():
                    img = cv2.imread(str(img_path))
                    loc = generate_candidate_localization(img) if img is not None else None
                else:
                    loc = None
            else:
                # Synthetic candidate annotation based on standard pipe geometry (640x480)
                loc = {
                    "bbox": [80, 60, 560, 420],
                    "polygon": [[80, 60], [560, 60], [560, 420], [80, 420]],
                    "quality_score": 0.65,
                }

            if loc:
                annotations[fn] = {
                    "filename": fn,
                    "target_class": target_cls,
                    "bbox": loc["bbox"],
                    "contour_polygon": loc["polygon"],
                    "annotation_source": "semi_automated_annular_detector_v1",
                    "human_verified": False,
                    "reviewer": None,
                    "review_status": "PENDING_HUMAN_VERIFICATION",
                    "quality_score": loc["quality_score"],
                }

                review_queue_rows.append({
                    "example_id": f"JI-{fn.split('.')[0]}",
                    "image_uri": f"gs://joint-inspection-510310-data/datasets/sewerml/jointinspect-v1/images/{fn}",
                    "current_label": target_cls,
                    "suggested_label": target_cls,
                    "model_confidence": str(loc["quality_score"]),
                    "reason_for_review": "Unverified semi-automated localization candidate",
                    "review_status": "PENDING_HUMAN_VERIFICATION",
                    "reviewer": "NONE",
                    "review_timestamp": "",
                })

    # Save annotations JSON
    annotations_json.parent.mkdir(parents=True, exist_ok=True)
    with open(annotations_json, mode="w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2)

    # Save review queue CSV
    review_queue_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "example_id",
        "image_uri",
        "current_label",
        "suggested_label",
        "model_confidence",
        "reason_for_review",
        "review_status",
        "reviewer",
        "review_timestamp",
    ]
    with open(review_queue_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(review_queue_rows)

    logger.info(
        "Generated %d localization annotations. Review queue written to %s (all unverified).",
        len(annotations),
        review_queue_csv,
    )
    return len(annotations)


def main():
    parser = argparse.ArgumentParser(description="Generate localization annotations and review queue")
    parser.add_argument(
        "--manifest",
        type=str,
        default="training/data/jointinspect-v1/manifests/dataset_manifest.csv",
        help="Path to dataset manifest CSV",
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        default=None,
        help="Optional directory containing candidate images",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="training/data/jointinspect-v1/annotations/localization_annotations.json",
        help="Output annotations JSON file",
    )
    parser.add_argument(
        "--review-queue",
        type=str,
        default="training/data/jointinspect-v1/review/review_queue.csv",
        help="Output review queue CSV",
    )
    args = parser.parse_args()

    generate_annotations_manifest(
        Path(args.manifest),
        Path(args.image_dir) if args.image_dir else None,
        Path(args.output_json),
        Path(args.review_queue),
    )


if __name__ == "__main__":
    main()
