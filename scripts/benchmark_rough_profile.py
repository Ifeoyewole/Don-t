"""Local-only rough-concrete width profile and visualization.

Usage (same JSON manifest as scripts.benchmark_fused_geometry):
  python -m scripts.benchmark_rough_profile \\
    --manifest inspection-test.json \\
    --report rough-profile.json \\
    --overlay rough-profile.jpg

The report contains image-space observations only; never millimetres,
an engineering result, or a classifier claim. An ROI from an inspector is
recommended. No footage is uploaded to the cloud or committed to Git.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import cv2

from backend.app.core.cv.experimental_rough_profile import (
    draw_rough_profile_overlay,
    profile_rough_seam,
)


def evaluate_manifest(manifest: dict, directory: Path) -> tuple[dict, list[tuple]]:
    geometry = manifest.get("geometry")
    if geometry not in ("VERTICAL_SEAM", "HORIZONTAL_SEAM"):
        raise ValueError("This benchmark supports VERTICAL_SEAM or HORIZONTAL_SEAM only.")
    frames = manifest.get("frames", [])
    if not isinstance(frames, list) or not (1 <= len(frames) <= 8):
        raise ValueError("Provide 1-8 frames with per-frame inspector ROI proposals.")
    entries = []
    overlays = []
    for item in frames:
        selected = next(
            (p for p in item.get("proposals", [])
             if p.get("geometry") == geometry and p.get("source") == "INSPECTOR"),
            None,
        )
        if selected is None:
            raise ValueError("Each frame needs an INSPECTOR ROI matching the selected geometry.")
        raw = Path(item["file"])
        path = raw if raw.is_absolute() else directory / raw
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Cannot open inspection image: {raw.name}")
        audit = profile_rough_seam(image, geometry, tuple(selected["bbox"]))
        entry = asdict(audit)
        entry["frame_id"] = str(item["frame_id"])
        entry["roi_source"] = "INSPECTOR"
        entries.append(entry)
        overlays.append((image, audit))
    return {
        "research_only": True,
        "physical_measurement_authorized": False,
        "units": "pixels_only",
        "geometry": geometry,
        "frames": entries,
        "warning": "Dark-band boundaries may be shadows or debris; field accuracy is not yet established.",
    }, overlays


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--overlay", type=Path, default=None, help="Annotated JPG/PNG for the first frame")
    args = parser.parse_args()
    report, overlays = evaluate_manifest(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        args.manifest.resolve().parent,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.overlay is not None:
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        annotated = draw_rough_profile_overlay(*overlays[0])
        if not cv2.imwrite(str(args.overlay), annotated):
            raise ValueError("Failed to write the requested overlay image.")
    for item in report["frames"]:
        print(f"{item['frame_id']}: {item['status']} | median={item['median_width_px']} px | coverage={item['coverage']:.1%}")
    print("Research pixel evidence only; no physical measurements authorized.")


if __name__ == "__main__":
    main()
