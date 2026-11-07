"""Run paired research comparisons; NEVER promote candidates into production.

Usage:
python scripts/benchmark_shadow_geometry.py --manifest local.json --report /tmp/geometry-comparison.json

Example local.json (use ONLY footage you are permitted to evaluate):
{
  "images": [
    {
      "file": "/absolute/path/to/frame.jpg",
      "joint_type": "VERTICAL_SEAM",
      "roi_bbox": [130, 80, 270, 390],
      "ground_truth_gap_px": 21.5,
      "asset_group": "original-video-001"
    }
  ]
}

A negative case uses ground_truth_gap_px: 0. Missing ground truth is
UNLABELLED, which can establish neither accuracy nor improvement. Avoid
training/test video-family leakage and never publish inspection images.
"""

import argparse
import json
import math
import statistics
from pathlib import Path

import cv2

from backend.app.core.cv.experimental_geometry import (
    audit_dark_seam,
    compare_seam_candidates,
)
from backend.app.core.cv.seam_detector import measure_seam_gap
from backend.app.schemas.domain import JointType


def benchmark_manifest(manifest: dict) -> dict:
    cases = manifest.get("images")
    if not isinstance(cases, list) or len(cases) > 1000:
        raise ValueError("Expected an images array with at most 1000 entries")
    rows = []
    for row in cases:
        path = Path(row["file"])
        kind = JointType(row["joint_type"])
        if kind not in (JointType.VERTICAL_SEAM, JointType.HORIZONTAL_SEAM):
            raise ValueError("Benchmark supports seam geometry only")
        roi = tuple(row["roi_bbox"])
        if len(roi) != 4:
            raise ValueError("Each benchmark image needs a four-coordinate ROI")
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not load one input image ({path.name})")
        try:
            baseline = measure_seam_gap(image, joint_type=kind, pipe_diameter_mm=None, roi_bbox=roi)
            baseline_px = baseline.mean_gap_px
        except (ValueError, cv2.error):
            baseline_px = None
        audit = audit_dark_seam(image, kind.value, roi)
        shadow_px = audit.candidate_gap_px
        label = row.get("ground_truth_gap_px")
        if label is not None and (not isinstance(label, (float, int)) or not math.isfinite(label) or label < 0):
            raise ValueError("Ground truth gap must be a finite non-negative pixel measurement")
        rows.append({
            "asset_group": row.get("asset_group", "not_provided"),
            "ground_truth_gap_px": label,
            "production_baseline_px": baseline_px,
            "independent_shadow_px": shadow_px,
            "shadow_coverage": audit.coverage,
            "shadow_reason": audit.reason,
            "comparison": compare_seam_candidates(baseline_px, audit),
        })

    def metrics(method: str) -> dict:
        labelled_pos = [x for x in rows if x["ground_truth_gap_px"] is not None and x["ground_truth_gap_px"] > 0]
        labelled_neg = [x for x in rows if x["ground_truth_gap_px"] == 0]
        absolute_errors = [
            abs(x[method] - x["ground_truth_gap_px"])
            for x in labelled_pos if x[method] is not None
        ]
        return {
            "positive_labels": len(labelled_pos),
            "negative_labels": len(labelled_neg),
            "positive_coverage": sum(x[method] is not None for x in labelled_pos),
            "false_measurements_on_negatives": sum(x[method] is not None for x in labelled_neg),
            "mean_absolute_error_px_on_measurable_positives": (
                round(statistics.mean(absolute_errors), 3) if absolute_errors else None
            ),
            "note": "Pixel error only; no physical calibration or engineering accuracy claim.",
        }

    distinct_groups = {
        x["asset_group"] for x in rows if x["asset_group"] != "not_provided"
    }
    return {
        "research_only": True,
        "units": "pixels_only",
        "case_count": len(rows),
        "video_family_groups": len(distinct_groups),
        "unlabelled_cases": sum(x["ground_truth_gap_px"] is None for x in rows),
        "baseline": metrics("production_baseline_px"),
        "shadow": metrics("independent_shadow_px"),
        "records": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = benchmark_manifest(payload)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Compared {result['case_count']} images. Report saved locally; no files were uploaded.")
    if result["unlabelled_cases"]:
        print("WARNING: Unlabelled samples cannot support an accuracy claim.")


if __name__ == "__main__":
    main()
