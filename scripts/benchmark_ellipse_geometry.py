"""Local, paired circle-vs-ellipse benchmark on permitted inspector-labelled images.

Usage:
  python scripts/benchmark_ellipse_geometry.py --manifest /tmp/rings.json --report /tmp/rings-report.json

Manifest:
{
  "images": [
    {
      "file": "/private/path/to/image.jpg",
      "roi_bbox": [100, 80, 500, 420],
      "asset_group": "video-001",
      "ring_pair_visible": true
    }
  ]
}

"ring_pair_visible" means two discernible, near-coaxial ring boundaries,
NOT an open-joint defect. Absence of ground truth is allowed but cannot
support an accuracy claim. Input images stay local; report contains no paths.
"""

import argparse
import json
from pathlib import Path

import cv2

from backend.app.core.cv.circular_detector import _find_concentric_circles
from backend.app.core.cv.experimental_ellipse import audit_projected_pipe_rings


def compare_images(manifest: dict) -> dict:
    images = manifest.get("images")
    if not isinstance(images, list) or not 0 < len(images) <= 500:
        raise ValueError("Expected 1-500 image entries")
    results = []
    for item in images:
        expected = item.get("ring_pair_visible")
        if expected is not None and not isinstance(expected, bool):
            raise ValueError("ring_pair_visible must be true, false or omitted")
        roi = item.get("roi_bbox")
        if not isinstance(roi, list) or len(roi) != 4:
            raise ValueError("Each example must define [x0,y0,x1,y1] roi_bbox")
        image = cv2.imread(str(Path(item["file"])))
        if image is None:
            raise ValueError("Could not read a local image from the benchmark manifest")
        x0, y0, x1, y1 = map(int, roi)
        h, w = image.shape[:2]
        if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
            raise ValueError("Invalid benchmark ROI")

        # Compare within the same inspection ROI. The baseline is strictly
        # a near-concentric circle finder; neither result is a defect label.
        gray_roi = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        baseline = _find_concentric_circles(gray_roi)
        ellipse = audit_projected_pipe_rings(image, (x0, y0, x1, y1))
        results.append({
            "asset_group": item.get("asset_group", "not_provided"),
            "ring_pair_visible": expected,
            "circle_pair_found": baseline is not None,
            "ellipse_pair_found": ellipse.status == "PROJECTED_RING_EVIDENCE",
            "ellipse_reason": ellipse.reason,
            "ellipse_min_boundary_coverage": (
                min(ellipse.inner_ring.coverage, ellipse.outer_ring.coverage)
                if ellipse.inner_ring is not None and ellipse.outer_ring is not None
                else None
            ),
        })

    def summary(key: str) -> dict:
        positives = [r for r in results if r["ring_pair_visible"] is True]
        negatives = [r for r in results if r["ring_pair_visible"] is False]
        return {
            "labelled_positives": len(positives),
            "labelled_negatives": len(negatives),
            "true_pair_detections": sum(bool(x[key]) for x in positives),
            "false_pair_detections": sum(bool(x[key]) for x in negatives),
            "unlabelled_found": sum(bool(x[key]) for x in results if x["ring_pair_visible"] is None),
        }

    return {
        "research_only": True,
        "unit": "projected_ring_presence_not_gap_mm",
        "total_images": len(results),
        "distinct_asset_groups": len({r["asset_group"] for r in results if r["asset_group"] != "not_provided"}),
        "circle_baseline": summary("circle_pair_found"),
        "ellipse_candidate": summary("ellipse_pair_found"),
        "results": results,
        "warning": "Neither nested image rings nor candidate spacing establish an open joint or axial physical gap.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = compare_images(json.loads(args.manifest.read_text(encoding="utf-8")))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Compared {result['total_images']} frames locally; no images uploaded.")
    print("No production detector promotion or field accuracy claim was made.")


if __name__ == "__main__":
    main()
