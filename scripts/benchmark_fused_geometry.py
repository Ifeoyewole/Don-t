"""Run the research-only, per-frame geometry fusion on local permitted footage.

Manifest example (one video):
{
  "geometry": "CIRCULAR_OPENING",
  "frames": [
    {"frame_id":"001","sequence_id":"video-1","frame_index":1,
     "file":"/private/frame-001.jpg",
     "proposals":[{"source":"INSPECTOR","bbox":[60,40,580,450],
                   "geometry":"CIRCULAR_OPENING"}]},
    {"frame_id":"002","sequence_id":"video-1","frame_index":2,
     "file":"/private/frame-002.jpg",
     "proposals":[{"source":"GEMINI","confidence":0.89,
                   "bbox":[61,40,579,450],"geometry":"CIRCULAR_OPENING"}]}
  ]
}

The source names are just provenance annotations; this script does NOT
contact Gemini/Inspect View or auto-generate ROIs. Inputs must be supplied by
an operator or separate validated detection pipeline. Reports never include
image pixels, files, credentials, mm calibration or engineering decisions.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import cv2

from backend.app.core.cv.experimental_fusion import (
    FrameRequest,
    RoiProposal,
    audit_geometry_frames,
)


def evaluate_manifest(payload: dict) -> dict:
    frames = payload.get("frames")
    geometry = payload.get("geometry")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 8:
        raise ValueError("Manifest must contain between 1 and 8 local frames")
    requests = []
    for entry in frames:
        img = cv2.imread(str(Path(entry["file"])))
        if img is None:
            raise ValueError("One listed frame could not be loaded")
        proposals = []
        for p in entry.get("proposals", []):
            bbox = p.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError("Each ROI proposal must contain four coordinates")
            proposals.append(RoiProposal(
                source=str(p.get("source", "")),
                bbox=tuple(bbox),
                geometry=str(p.get("geometry", "")),
                confidence=p.get("confidence"),
            ))
        requests.append(FrameRequest(
            frame_id=str(entry["frame_id"]),
            frame_index=int(entry["frame_index"]),
            sequence_id=str(entry["sequence_id"]),
            image_bgr=img,
            proposals=proposals,
        ))
    audit = audit_geometry_frames(requests, geometry)
    result = asdict(audit)
    result["research_only"] = True
    result["physical_measurement_authorized"] = False
    result["note"] = (
        "Projected visual evidence is not an OPEN_JOINT classification or a "
        "physical axial gap; inspector-labelled field benchmarking required."
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Combined research evidence written locally. No files were uploaded.")
    print(f"Result: {result['status']} ({result['reason']}); no physical measurement authorized.")


if __name__ == "__main__":
    main()
