"""Convert reviewed CSV rows into a strict Unified Vision research batch manifest.

Rows are eligible ONLY after a human changes review_status to
READY_FOR_RESEARCH and fills the exact GCS URI, inspector ROI, geometry and
source-family columns. No network or images accessed; no labels inferred.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from backend.app.core.cv.ai.unified_batch_manifest import validate_batch_manifest


def convert_worklist(
    rows: list[dict[str, str]],
    *,
    manifest_id: str,
    limit: int = 100,
) -> dict:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Limit must be 1–100")
    frames = []
    for index, row in enumerate(rows):
        if row.get("review_status") != "READY_FOR_RESEARCH":
            continue
        if len(frames) >= limit:
            raise ValueError("Worklist contains more ready frames than requested limit")
        sha = row.get("image_sha256", "").strip()
        uri = row.get("image_uri_TO_VERIFY", "").strip()
        family = row.get("source_family_TO_VERIFY", "").strip()
        if not uri or not family or family.upper().startswith("UNVERIFIED"):
            raise ValueError(f"Row {index + 1}: verified GCS path and source family required")
        try:
            roi = [int(row[f"roi_{name}"].strip()) for name in ("x0", "y0", "x1", "y1")]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Row {index + 1}: fill all four integer ROI coordinates") from None
        geometry = row.get("geometry_TO_REVIEW", "").strip()
        frame = {
            "frame_id": "frame_" + sha[:24],
            "image_uri": uri, "image_sha256": sha,
            "geometry": geometry, "roi": roi,
            "source_family": family,
            "source_id": f"{row.get('dataset_name', '')}:{row.get('source_media_id', '')}",
            "rights_status": row.get("rights_review", "").strip(),
            "annotation_status": row.get("annotation_review", "").strip(),
        }
        if row.get("source_labels"):
            frame["source_label"] = row["source_labels"][:128]
        if frame["annotation_status"] == "REVIEWED_GROUND_TRUTH":
            frame["reviewed_label"] = row.get("reviewed_ground_truth_label", "").strip()
            frame["review_id"] = row.get("review_id", "").strip()
        frames.append(frame)
    return validate_batch_manifest({
        "schema_version": "1.0", "manifest_id": manifest_id, "frames": frames,
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worklist", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    with args.worklist.open("r", encoding="utf-8-sig", newline="") as fh:
        records = list(csv.DictReader(fh))
    manifest = convert_worklist(
        records, manifest_id=args.manifest_id, limit=args.limit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(args.out),
                      "reviewed_roi_frame_count": len(manifest["frames"]),
                      "model_or_dataset_rights_not_promoted": True}))


if __name__ == "__main__":
    main()
