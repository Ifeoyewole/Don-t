"""Separate research inference path for non-joint CCTV visual tasks.

A manually selected ROI must refer to an object/feature, not a fictitious
pipe-joint seam. Loads no checkpoints itself: reuse the worker's already
loaded r5 preview model and SAM2 predictor via the existing adapters.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Mapping

import cv2
import numpy as np

from backend.app.core.cv.ai.research_sam2_adapter import propose_sam2_mask
from backend.app.core.cv.ai.unified_task_decision import (
    NONJOINT_TASKS, build_nonjoint_research_result,
)


def mask_matches_source_pixels(sam: Any, image_bgr: np.ndarray) -> bool:
    """Same decoded BGR frame, valid mask dimensions and exact bounding box."""
    if (sam.status != "MASK_CANDIDATE_RESEARCH"
            or not isinstance(sam.mask, np.ndarray)
            or sam.mask.shape != image_bgr.shape[:2]
            or sam.image_sha256 != hashlib.sha256(
                np.ascontiguousarray(image_bgr).tobytes()
            ).hexdigest()):
        return False
    ys, xs = np.where(sam.mask > 0)
    if len(xs) < 50:
        return False
    box = (int(xs.min()), int(ys.min()),
           int(xs.max()) + 1, int(ys.max()) + 1)
    return sam.mask_bbox == box


def analyze_nonjoint_image(
    image_path: Path, *,
    task_type: str,
    bbox: tuple[int, int, int, int],
    checkpoint_path: Path,
    checkpoint_sha256: str,
    sam2_predictor_factory: Callable,
    verified_gemini_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], np.ndarray | None]:
    """One frame / one task-specific report, without joint geometry functions."""
    if task_type not in NONJOINT_TASKS:
        raise ValueError("Use the existing joint geometry runner for joint frames")
    payload = image_path.read_bytes()
    if not payload or len(payload) > 8 * 1024 * 1024:
        raise ValueError("Frame exceeds 8 MiB research limit")
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if (image is None or image.size == 0
            or image.shape[0] * image.shape[1] > 16_000_000):
        raise ValueError("Invalid decoded frame")
    height, width = image.shape[:2]
    if (not isinstance(bbox, tuple) or len(bbox) != 4
            or any(type(value) is not int for value in bbox)
            or not (0 <= bbox[0] < bbox[2] <= width
                    and 0 <= bbox[1] < bbox[3] <= height)):
        raise ValueError("ROI must be inside the original frame")

    from backend.app.api.v1.endpoints.engineering_preview import infer
    preview = infer(payload)  # Existing r5 cached weights; no new model.
    sam = propose_sam2_mask(
        image, bbox,
        enabled=True,
        checkpoint_path=checkpoint_path,
        expected_sha256=checkpoint_sha256,
        predictor_factory=sam2_predictor_factory,
    )
    pixels_verified = mask_matches_source_pixels(sam, image)
    unified = build_nonjoint_research_result(
        task_type=task_type,
        image_sha256=hashlib.sha256(payload).hexdigest(),
        inspect_view_payload=preview,
        sam2_status=sam.status,
        sam2_bbox=sam.mask_bbox,
        sam2_quality=sam.mask_quality_score,
        mask_pixel_verified=pixels_verified,
        verified_gemini_receipt=verified_gemini_receipt,
    )
    report = {
        "status": "TASK_AWARE_RESEARCH_REVIEW",
        "task_type": task_type,
        "sam2_status": sam.status,
        "sam2_reason": sam.reason,
        "sam2_mask_pixels_verified": pixels_verified,
        "inspect_view_ready": preview.get("model_ready") is True,
        "inspect_view_version": preview.get("model_version"),
        "cv_status": "NOT_APPLICABLE_FOR_TASK",
        "cv_pixel_candidate": None,
        "physical_measurement_authorized": False,
        "unified_result": unified,
    }
    overlay = None
    if pixels_verified and unified["segmentation"]["status"] == "CANDIDATE_REVIEW":
        overlay = image.copy()
        contours, _ = cv2.findContours(
            sam.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours, -1, (0, 215, 255), 2, cv2.LINE_AA)
        cv2.rectangle(overlay, (bbox[0], bbox[1]), (bbox[2], bbox[3]),
                      (255, 195, 0), 2)
        cv2.putText(overlay, f"{task_type} / SAM2 CANDIDATE / NO MM",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (255, 255, 255), 2, cv2.LINE_AA)
    return report, overlay
