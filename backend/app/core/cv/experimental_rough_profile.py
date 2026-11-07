"""Original research-only rough-boundary seam profiling.

Tracks *image-intensity* left/right dark-band boundaries at multiple local
cross-sections, preserves accepted/rejected samples, and draws a review overlay.
A dark band may be a shadow, cavity, stain, crack or missing concrete, NOT a
verified joint opening. The result is PIXELS ONLY and cannot authorize PASS,
FAIL, a defect classification, or physical mm.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class BoundarySample:
    scan_position: int
    left_point: Optional[tuple[int, int]]
    right_point: Optional[tuple[int, int]]
    width_px: Optional[float]
    contrast: Optional[float]
    reason: str


@dataclass(frozen=True)
class RoughWidthProfile:
    method: str
    status: str
    geometry: str
    roi_bbox: Optional[tuple[int, int, int, int]]
    sampled_rows: int
    supported_rows: int
    coverage: float
    median_width_px: Optional[float]
    min_width_px: Optional[float]
    max_width_px: Optional[float]
    p95_width_px: Optional[float]
    width_mad_px: Optional[float]
    rejected_reasons: dict[str, int]
    samples: tuple[BoundarySample, ...]
    note: str = "Dark-band image boundaries; not verified physical joint edges or millimetres."


def _reject(
    geometry: str, roi: Optional[tuple[int, int, int, int]], reason: str,
) -> RoughWidthProfile:
    return RoughWidthProfile(
        "rough_dark_boundary_profile_v1", "REVIEW_REQUIRED", geometry, roi,
        0, 0, 0.0, None, None, None, None, None, {reason: 1}, (),
    )


def profile_rough_seam(
    image_bgr: np.ndarray,
    geometry: str,
    roi_bbox: Optional[Tuple[int, int, int, int]],
    *,
    sample_count: int = 80,
) -> RoughWidthProfile:
    """Trace a dark opening across jagged material-like boundaries in an ROI.

    Samples one-dimensional, lightly smoothed intensity profiles across the
    seam, finds two-sided dark-band contrast and then checks global centerline
    consistency. This intentionally DOES NOT claim material-edge segmentation.
    """
    orientation = getattr(geometry, "value", geometry)
    if orientation not in {"VERTICAL_SEAM", "HORIZONTAL_SEAM"}:
        return _reject(str(orientation), None, "seam_geometry_required")
    if not isinstance(image_bgr, np.ndarray) or image_bgr.size == 0 or image_bgr.ndim not in (2, 3):
        return _reject(orientation, None, "invalid_image")
    if roi_bbox is None:
        return _reject(orientation, None, "inspector_or_validated_roi_required")
    try:
        box = tuple(int(x) for x in roi_bbox)
        if len(box) != 4 or any(int(v) != v for v in roi_bbox):
            raise ValueError
        x0, y0, x1, y1 = box
        height, width = image_bgr.shape[:2]
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError
        if x1 - x0 < 40 or y1 - y0 < 40:
            raise ValueError
    except (TypeError, ValueError):
        return _reject(orientation, None, "invalid_or_small_roi")
    if sample_count < 16 or sample_count > 160:
        return _reject(orientation, box, "invalid_sample_count")

    crop = image_bgr[y0:y1, x0:x1]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    vertical = orientation == "VERTICAL_SEAM"
    scan = gray if vertical else gray.T
    traverse, axis = scan.shape
    positions = np.linspace(
        int(0.05 * traverse), int(0.95 * traverse), sample_count, dtype=int
    )
    per_row: list[list[tuple[float, float, float, int, int]]] = []
    preliminary: list[str] = []

    for scan_pos in positions:
        profile = np.median(
            scan[max(scan_pos - 2, 0):min(scan_pos + 3, traverse), :],
            axis=0,
        ).astype(np.float32)
        profile = cv2.GaussianBlur(profile[np.newaxis, :], (9, 1), 0).ravel()
        dark, bright = np.percentile(profile, (5, 80))
        if bright - dark < 18:
            per_row.append([])
            preliminary.append("low_contrast")
            continue
        threshold = dark + 0.52 * (bright - dark)
        inside = np.pad((profile < threshold).astype(np.int8), (1, 1))
        changes = np.diff(inside)
        starts = np.flatnonzero(changes == 1)
        ends = np.flatnonzero(changes == -1)
        candidates = []
        for start, end in zip(starts, ends):
            band_width = int(end - start)
            if not (4 <= band_width <= int(axis * 0.65)):
                continue
            if start < 8 or end > axis - 8:
                continue
            # The candidate must be darker than BOTH neighbouring surfaces,
            # not merely an edge on one side of a large shadow.
            left = float(np.median(profile[start - 8:start - 2]))
            right = float(np.median(profile[end + 2:end + 8]))
            middle = float(np.median(profile[start:end]))
            contrast = min(left - middle, right - middle)
            if contrast < 16:
                continue
            candidates.append(((start + end) / 2.0, float(band_width), contrast, int(start), int(end)))
        per_row.append(candidates)
        preliminary.append("candidate" if candidates else "no_two_sided_band")

    # Majority-center consensus resists highly contrasted unrelated texture
    # and avoids selecting the largest dark region in one single row.
    all_candidates = [c for row in per_row for c in row]
    if not all_candidates:
        return RoughWidthProfile(
            "rough_dark_boundary_profile_v1", "REVIEW_REQUIRED", orientation,
            box, sample_count, 0, 0.0, None, None, None, None, None,
            dict(Counter(preliminary)), (),
        )
    centers = np.array([c[0] for c in all_candidates])
    weights = np.array([c[2] for c in all_candidates])
    hist, bounds = np.histogram(centers, bins=max(12, min(40, axis // 15)), range=(0, axis), weights=weights)
    index = int(np.argmax(hist))
    seed_center = float((bounds[index] + bounds[index + 1]) / 2.0)

    samples: list[BoundarySample] = []
    rejected = Counter()
    raw_widths: list[float] = []
    raw_centers: list[float] = []
    for pos, row, note in zip(positions, per_row, preliminary):
        eligible = [c for c in row if abs(c[0] - seed_center) <= 0.17 * axis]
        if not eligible:
            reason = "off_consensus_center" if row else note
            rejected[reason] += 1
            samples.append(BoundarySample(
                int(pos + (y0 if vertical else x0)), None, None, None, None, reason,
            ))
            continue
        center, band_width, contrast, left, right = max(
            eligible, key=lambda c: c[2] - 0.2 * abs(c[0] - seed_center)
        )
        if vertical:
            left_xy = (int(x0 + left), int(y0 + pos))
            right_xy = (int(x0 + right), int(y0 + pos))
        else:
            left_xy = (int(x0 + pos), int(y0 + left))
            right_xy = (int(x0 + pos), int(y0 + right))
        samples.append(BoundarySample(
            int(pos + (y0 if vertical else x0)),
            left_xy, right_xy, round(band_width, 2), round(contrast, 2),
            "two_sided_dark_band_candidate",
        ))
        raw_widths.append(band_width)
        raw_centers.append(center)

    coverage = len(raw_widths) / float(sample_count)
    if not raw_widths:
        return RoughWidthProfile(
            "rough_dark_boundary_profile_v1", "REVIEW_REQUIRED", orientation, box,
            sample_count, 0, 0.0, None, None, None, None, None,
            dict(rejected), tuple(samples),
        )
    w = np.asarray(raw_widths, dtype=np.float64)
    median = float(np.median(w))
    mad = float(np.median(np.abs(w - median)))
    center_spread = float(np.percentile(raw_centers, 90) - np.percentile(raw_centers, 10))
    # A supported dark-band profile is *still* unconfirmed physical geometry.
    status = (
        "PIXEL_PROFILE_CANDIDATE"
        if coverage >= 0.60 and len(w) >= 16 and center_spread <= axis * 0.25
        else "REVIEW_REQUIRED"
    )
    if status == "REVIEW_REQUIRED":
        rejected["insufficient_or_unstable_centerline_coverage"] += 1
    return RoughWidthProfile(
        method="rough_dark_boundary_profile_v1",
        status=status,
        geometry=orientation,
        roi_bbox=box,
        sampled_rows=sample_count,
        supported_rows=len(w),
        coverage=round(coverage, 3),
        median_width_px=round(median, 2),
        min_width_px=round(float(np.min(w)), 2),
        max_width_px=round(float(np.max(w)), 2),
        p95_width_px=round(float(np.percentile(w, 95)), 2),
        width_mad_px=round(mad, 2),
        rejected_reasons=dict(rejected),
        samples=tuple(samples),
    )


def draw_rough_profile_overlay(image_bgr: np.ndarray, audit: RoughWidthProfile) -> np.ndarray:
    """Annotate an image copy with measured line segments; never forge pixels."""
    if image_bgr.ndim == 2:
        canvas = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)
    else:
        canvas = image_bgr.copy()
    if audit.roi_bbox is not None:
        x0, y0, x1, y1 = audit.roi_bbox
        cv2.rectangle(canvas, (x0, y0), (x1, y1), (0, 225, 240), 2)
    valid = [s for s in audit.samples if s.left_point is not None and s.right_point is not None]
    skip = max(1, len(valid) // 28)
    for sample in valid[::skip]:
        cv2.line(canvas, sample.left_point, sample.right_point, (0, 220, 255), 2, cv2.LINE_AA)
        cv2.circle(canvas, sample.left_point, 3, (255, 80, 40), -1)
        cv2.circle(canvas, sample.right_point, 3, (60, 255, 60), -1)
    for item, color in (([s.left_point for s in valid], (255, 80, 40)), ([s.right_point for s in valid], (60, 255, 60))):
        if len(item) >= 2:
            cv2.polylines(canvas, [np.array(item, dtype=np.int32)], False, color, 2, cv2.LINE_AA)
    caption = f"RESEARCH PIXELS ONLY | {audit.status} | median={audit.median_width_px} px | support={audit.coverage:.0%}"
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], min(canvas.shape[0], 38)), (18, 23, 30), -1)
    cv2.putText(canvas, caption[:85], (7, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas
