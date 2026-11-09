"""Opt-in, local Inspect View r5 + Meta SAM 2.1 + OpenCV research demo.

No package/checkpoint download, no cloud request, no production endpoint.
Requires explicit local SAM checkpoint and *independently verified* SHA-256;
Inspect View can be read from its existing local r5 loader or from a preview
JSON response whose image SHA-256 matches the exact supplied image bytes.

Example:
 python -m scripts.benchmark_inspect_view_sam2_fusion \\
   --image samples/pipe01.jpg --geometry VERTICAL_SEAM \\
   --roi 180 20 630 1060 --sam-checkpoint /path/sam2.1_hiera_tiny.pt \\
   --sam-sha256 YOUR_VERIFIED_SHA --inspect-view-local \\
   --report fusion-review.json --overlay fusion-review.jpg

Research output contains **no authoritative mm, engineering PASS or
commercial-license certification**, even if an official checkpoint is used.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from backend.app.core.cv.ai.research_inspect_view_sam2_fusion import (
    combine_inspect_view_and_sam2,
)
from backend.app.core.cv.ai.research_sam2_adapter import propose_sam2_mask
from backend.app.core.cv.ai.unified_vision_v1 import build_unified_result


def analyze_local_image(
    image_path: Path,
    *,
    geometry: str,
    bbox: tuple[int, int, int, int],
    checkpoint_path: Path | None,
    checkpoint_sha256: str | None,
    inspect_view_local: bool = False,
    inspect_view_json: Path | None = None,
    gemini_receipt_json: Path | None = None,
    sam2_predictor_factory: Callable | None = None,
    mask_output_path: Path | None = None,
) -> tuple[dict, np.ndarray | None]:
    if inspect_view_local and inspect_view_json is not None:
        raise ValueError("Choose one Inspect View source (local model OR matching JSON)")
    payload = image_path.read_bytes()
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError("Image exceeds 8MiB local research limit")
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0 or image.shape[0] * image.shape[1] > 16_000_000:
        raise ValueError("Unreadable image or dimensions exceed local limit")

    inspect_view = None
    if inspect_view_json is not None:
        inspect_view = json.loads(inspect_view_json.read_text(encoding="utf-8"))
        if (not isinstance(inspect_view, dict) or
                inspect_view.get("image_sha256") != hashlib.sha256(payload).hexdigest()):
            raise ValueError("Inspect View JSON must declare same uploaded image SHA-256")
    elif inspect_view_local:
        if not os.getenv("JOINTINSPECT_PREVIEW_MODEL_PATH"):
            raise ValueError("JOINTINSPECT_PREVIEW_MODEL_PATH required for local r5")
        from backend.app.api.v1.endpoints.engineering_preview import infer
        inspect_view = infer(payload)

    sam = propose_sam2_mask(
        image, bbox,
        enabled=checkpoint_path is not None and checkpoint_sha256 is not None,
        checkpoint_path=checkpoint_path,
        expected_sha256=checkpoint_sha256,
        predictor_factory=sam2_predictor_factory,
    )
    evidence = combine_inspect_view_and_sam2(
        image, geometry=geometry, inspect_view_payload=inspect_view, sam2_evidence=sam,
        frame_id=image_path.stem,
    )
    report = asdict(evidence)
    # One canonical, fail-closed decision for the same exact source image.
    # Keep component fields for audits, not for independent product answers.
    # Optional server-created receipt reuses the existing backend Gemini call.
    # Never invoke Vertex AI again from this GPU/CPU benchmark.
    gemini_receipt = None
    if gemini_receipt_json is not None:
        gemini_receipt = json.loads(gemini_receipt_json.read_text(encoding="utf-8"))
        if not isinstance(gemini_receipt, dict):
            raise ValueError("Gemini receipt must be a JSON object")
    report["unified_result"] = build_unified_result(
        report, inspect_view_payload=inspect_view,
        image_sha256=hashlib.sha256(payload).hexdigest(),
        gemini_receipt=gemini_receipt,
    )
    # Distinguish a rejected mask from a missing SAM runtime in cloud reports.
    report["sam2_reason"] = sam.reason
    report["commercial_production_permission_reported_for_inspect_view"] = True
    report["commercial_license_document_verified_by_tool"] = False
    report["physical_measurement_authorized"] = False
    report["note"] = (
        "Output-level model fusion is research evidence. Commercial permission "
        "is reported by the project owner, not established by this script. "
        "Mask pixels do not prove a pipe defect or millimetre gap."
    )
    if mask_output_path is not None:
        from scripts.cloud.research_runtime_diagnostics import write_verified_candidate_mask
        report['mask_artifact']=write_verified_candidate_mask(
            sam,image,mask_output_path,report['unified_result']['segmentation']['status']=='CANDIDATE_REVIEW')
    canvas = None
    if sam.status == "MASK_CANDIDATE_RESEARCH" and sam.mask is not None:
        canvas = image.copy()
        outlines, _ = cv2.findContours(sam.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, outlines, -1, (0, 215, 255), 2, cv2.LINE_AA)
        x0, y0, x1, y1 = bbox
        cv2.rectangle(canvas, (x0, y0), (x1, y1), (255, 195, 0), 2)
        cv2.putText(canvas, "SAM2 MASK / INSPECT VIEW ADVISORY / NO MM",
                    (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)
    return report, canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--geometry", required=True, choices=(
        "VERTICAL_SEAM", "HORIZONTAL_SEAM", "CIRCULAR_OPENING",
    ))
    parser.add_argument("--roi", type=int, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    parser.add_argument("--sam-checkpoint", type=Path, default=None)
    parser.add_argument("--sam-sha256", default=None)
    parser.add_argument("--inspect-view-local", action="store_true")
    parser.add_argument("--inspect-view-json", type=Path, default=None)
    parser.add_argument("--gemini-receipt-json", type=Path, default=None,
                        help="Optional server-created same-image Gemini semantic receipt; no new API call")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args()
    if (args.sam_checkpoint is None) != (args.sam_sha256 is None):
        parser.error("Both --sam-checkpoint and --sam-sha256 are required together")
    report, overlay = analyze_local_image(
        args.image, geometry=args.geometry, bbox=tuple(args.roi),
        checkpoint_path=args.sam_checkpoint,
        checkpoint_sha256=args.sam_sha256,
        inspect_view_local=args.inspect_view_local,
        inspect_view_json=args.inspect_view_json,
        gemini_receipt_json=args.gemini_receipt_json,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.overlay is not None and overlay is not None:
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.overlay), overlay):
            raise ValueError("Failed to write overlay")
    print(f"Fusion evidence: {report['status']} / CV: {report['cv_status']}")
    print("Review only; no automated commercial approval or physical mm.")


if __name__ == "__main__":
    main()
