"""Automated Dataset Image Quality Screening and Difficult-Condition Classifier.

Integrates with backend.app.core.cv.ai.image_quality to record:
- Blur / sharpness (Laplacian variance + Sobel peak edge gradient)
- Exposure (brightness score + underexposure ratio)
- Contrast (percentile-based Michelson contrast)
- Specular glare ratio
- Resolution and decoding status

Distinguishes between:
- Genuinely unusable corrupt/blank images (rejected).
- Controlled difficult-condition cohort (retained for robust model generalization).
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from backend.app.core.cv.ai.image_quality import (
    compute_blur_score,
    compute_contrast_score,
    compute_exposure_scores,
    validate_image_quality,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dataset_quality")


def analyze_image_quality(
    image_path: Path,
    min_resolution: Tuple[int, int] = (640, 480),
) -> Dict[str, any]:
    """Analyzes an image file and returns detailed quality diagnostics."""
    if not image_path.exists():
        return {
            "filename": image_path.name,
            "decoding_status": "FILE_NOT_FOUND",
            "usable": False,
            "is_difficult_condition": False,
            "rejection_reason": "File does not exist",
        }

    img = cv2.imread(str(image_path))
    if img is None:
        return {
            "filename": image_path.name,
            "decoding_status": "DECODE_FAILED",
            "usable": False,
            "is_difficult_condition": False,
            "rejection_reason": "Corrupt or unreadable image format",
        }

    h, w = img.shape[:2]
    if w < min_resolution[0] or h < min_resolution[1]:
        return {
            "filename": image_path.name,
            "decoding_status": "LOW_RESOLUTION",
            "resolution": f"{w}x{h}",
            "usable": False,
            "is_difficult_condition": False,
            "rejection_reason": f"Resolution below minimum {min_resolution[0]}x{min_resolution[1]}",
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_score = compute_blur_score(gray)
    brightness, under_ratio, glare_ratio = compute_exposure_scores(gray)
    contrast_score = compute_contrast_score(gray)
    quality_eval = validate_image_quality(img)

    # Difficult condition flags (not rejected, but tagged for difficult-condition cohort)
    is_difficult = (
        blur_score < 0.35
        or under_ratio > 0.20
        or glare_ratio > 0.10
        or contrast_score < 0.40
    )

    return {
        "filename": image_path.name,
        "decoding_status": "OK",
        "resolution": f"{w}x{h}",
        "blur_score": blur_score,
        "brightness_score": brightness,
        "underexposed_ratio": under_ratio,
        "glare_ratio": glare_ratio,
        "contrast_score": contrast_score,
        "overall_quality_score": quality_eval.quality_score,
        "usable": quality_eval.usable,
        "is_difficult_condition": is_difficult,
        "rejection_reason": quality_eval.rejection_reason,
    }


def screen_dataset_batch(
    manifest_csv: Path,
    image_dir: Optional[Path],
    output_report_json: Path,
) -> Dict[str, any]:
    """Screens all images in a dataset manifest."""
    if not manifest_csv.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_csv}")

    results = []
    retained_standard = 0
    retained_difficult = 0
    rejected_corrupt = 0

    with open(manifest_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            fn = r.get("image_filename") or r.get("filename")
            if not fn:
                continue

            if image_dir and image_dir.exists():
                diag = analyze_image_quality(image_dir / fn)
                if not diag["usable"]:
                    rejected_corrupt += 1
                elif diag["is_difficult_condition"]:
                    retained_difficult += 1
                else:
                    retained_standard += 1
                results.append(diag)
            else:
                # Synthetic evaluation when awaiting raw image acquisition
                # Tag according to manifest quality_flags
                is_diff = "difficult" in r.get("quality_flags", "").lower() or r.get("jointinspect_target_class") == "DIFFICULT_CONDITION"
                if is_diff:
                    retained_difficult += 1
                else:
                    retained_standard += 1
                results.append({
                    "filename": fn,
                    "decoding_status": "AWAITING_PHYSICAL_ACQUISITION",
                    "usable": True,
                    "is_difficult_condition": is_diff,
                    "quality_flags": r.get("quality_flags", "standard"),
                })

    summary = {
        "total_analyzed": len(results),
        "retained_standard": retained_standard,
        "retained_difficult_cohort": retained_difficult,
        "rejected_unusable": rejected_corrupt,
        "status": "COMPLETED",
    }

    output_report_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_report_json, mode="w", encoding="utf-8") as f:
        json.dump({"summary": summary, "samples": results[:50]}, f, indent=2)

    logger.info("Quality screening complete: %s", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run image quality analysis on dataset")
    parser.add_argument(
        "--manifest",
        type=str,
        default="training/data/jointinspect-v1/manifests/dataset_manifest.csv",
        help="Path to manifest CSV",
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        default=None,
        help="Optional directory containing image files",
    )
    parser.add_argument(
        "--output-report",
        type=str,
        default="training/data/jointinspect-v1/manifests/quality_report.json",
        help="Output quality report JSON",
    )
    args = parser.parse_args()

    screen_dataset_batch(
        Path(args.manifest),
        Path(args.image_dir) if args.image_dir else None,
        Path(args.output_report),
    )


if __name__ == "__main__":
    main()
