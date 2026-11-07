"""Optional, opt-in SAM 2.1 promptable-mask adapter for JointInspect research.

This module does not vendor SAM 2 source/weights, install packages, contact
external services, or change production inference. It requires a locally
provided official publisher checkpoint whose SHA256 was recorded independently.
It returns advisory mask/ROI evidence, NEVER a physical gap, defect diagnosis,
engineering acceptance, or commercial release approval.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Callable, Optional, Protocol

import cv2
import numpy as np

from backend.app.core.cv.experimental_fusion import RoiProposal


OFFICIAL_MODEL_ID = "sam2.1_hiera_tiny"
OFFICIAL_CONFIG = "configs/sam2.1/sam2.1_hiera_t.yaml"


class ImagePredictor(Protocol):
    def set_image(self, image_rgb: np.ndarray) -> None: ...
    def predict(self, *, box: np.ndarray, multimask_output: bool) -> tuple: ...


@dataclass(frozen=True)
class Sam2MaskEvidence:
    status: str  # MASK_CANDIDATE_RESEARCH | REVIEW_REQUIRED | MODEL_UNAVAILABLE
    model_id: str
    prompt_bbox: tuple[int, int, int, int] | None
    mask_bbox: tuple[int, int, int, int] | None
    mask_quality_score: float | None
    mask: np.ndarray | None
    reason: str
    image_sha256: str | None = None

    def to_roi_proposal(self, geometry: str) -> RoiProposal | None:
        """Make an existing experimental-fusion ROI from the candidate mask."""
        if self.status != "MASK_CANDIDATE_RESEARCH" or self.mask_bbox is None:
            return None
        if self.mask_quality_score is None or self.mask_quality_score < 0.7:
            return None
        return RoiProposal(
            source="CV_MASK",
            bbox=self.mask_bbox,
            geometry=geometry,
            confidence=self.mask_quality_score,
        )


def _unavailable(reason: str) -> Sam2MaskEvidence:
    return Sam2MaskEvidence(
        "MODEL_UNAVAILABLE", OFFICIAL_MODEL_ID, None, None, None, None, reason,
    )


def _review(box: tuple[int, int, int, int], reason: str) -> Sam2MaskEvidence:
    return Sam2MaskEvidence(
        "REVIEW_REQUIRED", OFFICIAL_MODEL_ID, box, None, None, None, reason,
    )


def _verified_checkpoint(checkpoint: Path, expected_sha256: str) -> bool:
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        return False
    if any(ch not in "0123456789abcdef" for ch in expected_sha256.lower()):
        return False
    if not checkpoint.is_file():
        return False
    hasher = hashlib.sha256()
    try:
        with checkpoint.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest() == expected_sha256.lower()
    except OSError:
        return False


def _sam2_predictor(checkpoint: Path) -> ImagePredictor:
    # Optional dependency: only imported when explicitly running a local
    # research experiment with publisher-checkpoint provenance reviewed.
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    return SAM2ImagePredictor(
        build_sam2(OFFICIAL_CONFIG, str(checkpoint), device="cpu")
    )


def propose_sam2_mask(
    image_bgr: np.ndarray,
    prompt_bbox: tuple[int, int, int, int],
    *,
    enabled: bool = False,
    checkpoint_path: Path | None = None,
    expected_sha256: str | None = None,
    min_quality: float = 0.75,
    predictor_factory: Callable[[Path], ImagePredictor] | None = None,
) -> Sam2MaskEvidence:
    """Run SAM 2.1 Tiny on an explicit inspector ROI, optionally with a test stub.

    No auto-generated ROI or remote model download. This does not say the mask
    represents a pipe joint, or that the checkpoint has legal clearance.
    """
    if not enabled:
        return _unavailable("research_adapter_disabled")
    if checkpoint_path is None or not expected_sha256:
        return _unavailable("checkpoint_and_reviewed_sha256_required")
    checkpoint_path = Path(checkpoint_path)
    if not _verified_checkpoint(checkpoint_path, expected_sha256):
        return _unavailable("checkpoint_sha256_mismatch_or_unreadable")
    if not (isinstance(min_quality, (float, int)) and math.isfinite(min_quality)
            and 0.70 <= min_quality <= 1.0):
        return _unavailable("invalid_quality_threshold")
    if not isinstance(image_bgr, np.ndarray) or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        return _unavailable("expected_bgr_image")
    if image_bgr.dtype != np.uint8:
        return _unavailable("expected_uint8_image")

    h, w = image_bgr.shape[:2]
    try:
        if len(prompt_bbox) != 4 or any(type(v) is not int for v in prompt_bbox):
            raise ValueError
        x0, y0, x1, y1 = prompt_bbox
        if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
                and x1 - x0 >= 24 and y1 - y0 >= 24):
            raise ValueError
    except (TypeError, ValueError):
        return _unavailable("invalid_prompt_roi")

    try:
        predictor = (predictor_factory or _sam2_predictor)(checkpoint_path)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        predictor.set_image(image_rgb)
        masks, scores, _ = predictor.predict(
            box=np.asarray(prompt_bbox, dtype=np.float32),
            multimask_output=True,
        )
        quality = np.asarray(scores, dtype=np.float32).reshape(-1)
        proposals = np.asarray(masks)
        if proposals.ndim != 3 or proposals.shape[1:] != (h, w):
            return _review(prompt_bbox, "invalid_mask_shape")
        if proposals.shape[0] != len(quality) or not len(quality):
            return _review(prompt_bbox, "mask_score_count_mismatch")
        if not np.isfinite(quality).all() or np.any(quality < 0) or np.any(quality > 1):
            return _review(prompt_bbox, "nonfinite_or_invalid_mask_quality")
        if not np.isfinite(proposals).all():
            return _review(prompt_bbox, "nonfinite_mask_values")
        index = int(np.argmax(quality))
        score = float(quality[index])
        if score < min_quality:
            return _review(prompt_bbox, "mask_quality_below_threshold")

        mask = (proposals[index] > 0.5).astype(np.uint8) * 255
        foreground_y, foreground_x = np.where(mask != 0)
        area = len(foreground_y)
        if area < 50 or area > 0.75 * h * w:
            return _review(prompt_bbox, "unsupported_mask_area")
        mx0, my0 = int(foreground_x.min()), int(foreground_y.min())
        mx1, my1 = int(foreground_x.max()) + 1, int(foreground_y.max()) + 1
        if (mx1 - mx0 < 24 or my1 - my0 < 24):
            return _review(prompt_bbox, "mask_roi_too_small")
        # Guard against the model segmenting an unrelated wall outside the
        # operator's local box. No mask shape can prove physical joint identity.
        overlap = max(0, min(mx1, x1) - max(mx0, x0)) * max(
            0, min(my1, y1) - max(my0, y0)
        )
        if overlap / float((mx1 - mx0) * (my1 - my0)) < 0.25:
            return _review(prompt_bbox, "mask_does_not_overlap_prompt_region")

        return Sam2MaskEvidence(
            "MASK_CANDIDATE_RESEARCH",
            OFFICIAL_MODEL_ID,
            prompt_bbox,
            (mx0, my0, mx1, my1),
            round(score, 4),
            mask,
            "prompted_mask_not_defect_or_metric_measurement",
            hashlib.sha256(np.ascontiguousarray(image_bgr).tobytes()).hexdigest(),
        )
    except (ImportError, RuntimeError, ValueError, OSError, cv2.error):
        return _review(prompt_bbox, "sam2_dependency_or_inference_unavailable")
