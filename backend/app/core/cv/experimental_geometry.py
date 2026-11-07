"""Independent *research-only* pipe geometry checks.

This is original JointInspect implementation. No third-party repository code,
pretrained weights or dataset are bundled. Not called by production measurement.
It reports pixel-space candidates for comparison, NEVER a physical measurement,
defect classification, calibration authority or engineering PASS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class GeometryAudit:
    method: str
    status: str  # EVIDENCE_CANDIDATE | INSUFFICIENT_EVIDENCE
    candidate_gap_px: Optional[float]
    coverage: float
    dispersion_px: Optional[float]
    reason: str


def _no_evidence(method: str, reason: str, coverage: float = 0.0) -> GeometryAudit:
    return GeometryAudit(method, "INSUFFICIENT_EVIDENCE", None, round(coverage, 3), None, reason)


def _validate_roi(
    image: np.ndarray, roi_bbox: Optional[Tuple[int, int, int, int]]
) -> Optional[Tuple[int, int, int, int]]:
    if roi_bbox is None:
        return None
    height, width = image.shape[:2]
    try:
        x0, y0, x1, y1 = [int(v) for v in roi_bbox]
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        return None
    if (x1 - x0) < 24 or (y1 - y0) < 30:
        return None
    return x0, y0, x1, y1


def audit_dark_seam(
    image_bgr: np.ndarray,
    joint_type: str,
    roi_bbox: Optional[Tuple[int, int, int, int]],
    *,
    sample_count: int = 48,
) -> GeometryAudit:
    """Check a localized dark seam independently of gradient peak pairing.

    A narrow dark region must be visibly bracketed by brighter surfaces along
    multiple scanlines. Consistency and geometric continuity are checked with
    robust linear fitting; huge or low-contrast dark regions are rejected.
    """
    method = "roi_dark_band_consistency_v1"
    if image_bgr is None or image_bgr.size == 0 or image_bgr.ndim not in (2, 3):
        return _no_evidence(method, "invalid_image")
    orientation = getattr(joint_type, "value", joint_type)
    if orientation not in ("VERTICAL_SEAM", "HORIZONTAL_SEAM"):
        return _no_evidence(method, "seam_orientation_required")
    roi = _validate_roi(image_bgr, roi_bbox)
    if roi is None:
        return _no_evidence(method, "localized_joint_roi_required")
    if sample_count < 12 or sample_count > 120:
        return _no_evidence(method, "invalid_scanline_count")

    x0, y0, x1, y1 = roi
    image = image_bgr[y0:y1, x0:x1]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    vertical = orientation == "VERTICAL_SEAM"
    axis_length = gray.shape[1] if vertical else gray.shape[0]
    traverse_length = gray.shape[0] if vertical else gray.shape[1]
    max_band = min(int(axis_length * 0.34), axis_length - 12)
    if max_band < 3:
        return _no_evidence(method, "roi_too_narrow")

    positions = np.linspace(
        int(traverse_length * 0.06), int(traverse_length * 0.94),
        sample_count, dtype=int,
    )
    tracked = []
    for pos in positions:
        p = gray[pos, :] if vertical else gray[:, pos]
        profile = p.astype(np.float64)
        dark, bright = np.percentile(profile, [5, 80])
        if bright - dark < 24:
            continue
        binary = (profile < (0.52 * dark + 0.48 * bright)).astype(np.int8)
        changes = np.diff(np.pad(binary, (1, 1)))
        starts = np.flatnonzero(changes == 1)
        ends = np.flatnonzero(changes == -1)
        candidates = []
        for start, end in zip(starts, ends):
            band_width = int(end - start)
            if not (3 <= band_width <= max_band) or start < 6 or end > axis_length - 6:
                continue
            flank_left = float(np.median(profile[start - 6:start - 1]))
            flank_right = float(np.median(profile[end + 1:end + 6]))
            mid = float(np.median(profile[start:end]))
            contrast = min(flank_left - mid, flank_right - mid)
            if contrast < 19:
                continue
            center = 0.5 * (start + end)
            center_penalty = 0.10 * abs(center - axis_length * 0.5)
            candidates.append((contrast - center_penalty, center, band_width))
        if candidates:
            _, center, band_width = max(candidates, key=lambda c: c[0])
            tracked.append((float(pos), center, float(band_width)))

    initial_coverage = len(tracked) / float(sample_count)
    if len(tracked) < 8 or initial_coverage < 0.55:
        return _no_evidence(method, "insufficient_two_sided_contrast", initial_coverage)

    observations = np.asarray(tracked, dtype=np.float64)
    positions = observations[:, 0]
    centers = observations[:, 1]
    widths = observations[:, 2]
    # Iteratively reweighted linear trend fit (no external implementation).
    inliers = np.ones(len(tracked), dtype=bool)
    for _ in range(3):
        if inliers.sum() < 8:
            return _no_evidence(method, "noncontinuous_seam", initial_coverage)
        slope, intercept = np.polyfit(positions[inliers], centers[inliers], 1)
        residuals = np.abs(centers - (slope * positions + intercept))
        center_tol = max(2.5, axis_length * 0.035)
        new_inliers = residuals <= center_tol
        if np.array_equal(inliers, new_inliers):
            break
        inliers = new_inliers

    widths_used = widths[inliers]
    robust_width = float(np.median(widths_used)) if widths_used.size else 0.0
    width_spread = float(np.median(np.abs(widths_used - robust_width))) if widths_used.size else 0.0
    final_coverage = float(inliers.sum()) / float(sample_count)
    if final_coverage < 0.55 or robust_width <= 0:
        return _no_evidence(method, "inconsistent_edge_tracking", final_coverage)
    if width_spread > max(3.0, robust_width * 0.20):
        return _no_evidence(method, "unstable_width_across_scanlines", final_coverage)

    return GeometryAudit(
        method=method,
        status="EVIDENCE_CANDIDATE",
        candidate_gap_px=round(robust_width, 2),
        coverage=round(final_coverage, 3),
        dispersion_px=round(width_spread, 2),
        reason="two_sided_dark_band_with_consistent_boundaries",
    )


def compare_seam_candidates(
    primary_gap_px: Optional[float], audit: GeometryAudit
) -> str:
    """Assess agreement only; NEVER authorizes a physical measurement or PASS."""
    if (
        primary_gap_px is None
        or not np.isfinite(primary_gap_px)
        or primary_gap_px <= 0
        or audit.status != "EVIDENCE_CANDIDATE"
        or audit.candidate_gap_px is None
    ):
        return "UNVERIFIABLE"
    alternate = audit.candidate_gap_px
    discrepancy = abs(float(primary_gap_px) - alternate)
    if discrepancy > max(3.0, 0.20 * max(alternate, float(primary_gap_px))):
        return "DISAGREEMENT_REVIEW"
    return "CONSISTENT_PIXEL_CANDIDATES"
