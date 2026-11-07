"""Original research-only audit of projected elliptical pipe-ring boundaries.

No external code, model weights, or footage is included. This module is not
used by production measurement and cannot determine an OPEN_JOINT defect,
physical millimetres, or engineering PASS. Nested projected rings can result
from ordinary sockets, liners, lateral connections or depth perspective.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class EllipseRing:
    center_xy: tuple[float, float]
    axes_px: tuple[float, float]
    angle_deg: float
    coverage: float
    rms_residual_px: float


@dataclass(frozen=True)
class EllipseAudit:
    method: str
    status: str
    inner_ring: Optional[EllipseRing]
    outer_ring: Optional[EllipseRing]
    projected_semiaxis_spacing_px: Optional[float]
    reason: str


def _reject(reason: str) -> EllipseAudit:
    return EllipseAudit(
        "roi_projected_ellipse_pair_v1", "INSUFFICIENT_EVIDENCE",
        None, None, None, reason,
    )


def _candidate(
    contour: np.ndarray,
    offset: tuple[int, int],
    shape: tuple[int, int],
    minimum_coverage: float,
) -> Optional[EllipseRing]:
    if len(contour) < 30:
        return None
    (cx, cy), (diam1, diam2), angle = cv2.fitEllipse(contour)
    if not all(np.isfinite(x) for x in (cx, cy, diam1, diam2, angle)):
        return None
    a, b = diam1 / 2.0, diam2 / 2.0
    h, w = shape
    if (min(a, b) < min(h, w) * 0.045 or
            max(a, b) > max(h, w) * 0.65 or
            max(a, b) / min(a, b) > 3.0):
        return None
    if not (0 <= cx < w and 0 <= cy < h):
        return None

    # Verify that observed contour points cover the fitted ellipse with
    # sufficiently small radial residual, rather than accepting arbitrary
    # compact contours. This does not establish joint identity.
    points = contour.reshape(-1, 2).astype(np.float64)
    theta = np.deg2rad(angle)
    dx, dy = points[:, 0] - cx, points[:, 1] - cy
    u = (np.cos(theta) * dx + np.sin(theta) * dy) / a
    v = (-np.sin(theta) * dx + np.cos(theta) * dy) / b
    radial = np.hypot(u, v)
    residual = np.abs(radial - 1.0) * min(a, b)
    rms = float(np.sqrt(np.mean(residual ** 2)))
    if rms > max(2.2, min(a, b) * 0.045):
        return None

    angular_bins = np.floor(
        (np.arctan2(v, u) + np.pi) / (2.0 * np.pi) * 36
    ).astype(int) % 36
    coverage = float(np.unique(angular_bins).size / 36.0)
    if coverage < minimum_coverage:
        return None

    return EllipseRing(
        center_xy=(round(float(cx + offset[0]), 2), round(float(cy + offset[1]), 2)),
        axes_px=(round(float(diam1), 2), round(float(diam2), 2)),
        angle_deg=round(float(angle), 2),
        coverage=round(coverage, 3),
        rms_residual_px=round(rms, 3),
    )


def audit_projected_pipe_rings(
    image_bgr: np.ndarray,
    roi_bbox: Optional[Tuple[int, int, int, int]],
    *,
    allow_partial: bool = False,
) -> EllipseAudit:
    """Find consistent nested projected ring outlines within a supplied ROI.

    Output is projected visual ring spacing in PIXELS, not axial joint opening.
    Optional partial arcs are unconfirmed evidence and MUST be corroborated
    in a separate frame before use by the research temporal audit.
    A ROI is mandatory. This method must not be used to authorize PASS or mm.
    """
    if image_bgr is None or image_bgr.size == 0 or image_bgr.ndim not in (2, 3):
        return _reject("invalid_image")
    if roi_bbox is None:
        return _reject("localized_joint_roi_required")
    try:
        x0, y0, x1, y1 = map(int, roi_bbox)
    except (TypeError, ValueError):
        return _reject("invalid_roi")
    h, w = image_bgr.shape[:2]
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h and
            x1 - x0 >= 64 and y1 - y0 >= 64):
        return _reject("invalid_roi")

    crop = image_bgr[y0:y1, x0:x1]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop.copy()
    gray = cv2.GaussianBlur(gray, (5, 5), 1)
    edges = cv2.Canny(gray, 40, 110, L2gradient=True)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    candidates: list[EllipseRing] = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:90]:
        try:
            candidate = _candidate(contour, (x0, y0), gray.shape, 0.42 if allow_partial else 0.69)
        except cv2.error:
            continue
        if candidate is not None:
            candidates.append(candidate)
    if len(candidates) < 2:
        return _reject("insufficient_supported_elliptical_boundaries")

    candidates.sort(key=lambda c: max(c.axes_px), reverse=True)
    best: Optional[tuple[float, EllipseRing, EllipseRing, float]] = None
    for index, outer in enumerate(candidates[:25]):
        outer_axes = np.asarray(outer.axes_px, dtype=float)
        outer_minor, outer_major = sorted(outer_axes)
        for inner in candidates[index + 1:]:
            inner_axes = np.asarray(inner.axes_px, dtype=float)
            inner_minor, inner_major = sorted(inner_axes)
            if not (0.40 < inner_minor / outer_minor < 0.92 and
                    0.40 < inner_major / outer_major < 0.92):
                continue
            if abs(inner_minor / inner_major - outer_minor / outer_major) > 0.15:
                continue
            center_offset = float(np.linalg.norm(
                np.asarray(outer.center_xy) - np.asarray(inner.center_xy)
            ))
            if center_offset > min(8.0, outer_minor * 0.12):
                continue
            # Rotation is not meaningful for nearly circular ellipses.
            if outer_major / outer_minor > 1.12:
                delta_angle = abs(
                    (outer.angle_deg - inner.angle_deg + 90.0) % 180.0 - 90.0
                )
                if delta_angle > 15.0:
                    continue
            spacing = float(np.median((outer_axes - inner_axes) / 2.0))
            if spacing < 4:
                continue
            score = (
                min(outer.coverage, inner.coverage)
                - 0.03 * (outer.rms_residual_px + inner.rms_residual_px)
                - center_offset / max(outer_minor, 1.0)
            )
            if best is None or score > best[0]:
                best = (score, inner, outer, spacing)
    if best is None:
        return _reject("no_consistent_nested_ellipse_pair")

    _, inner, outer, spacing = best
    is_partial = min(inner.coverage, outer.coverage) < 0.69
    return EllipseAudit(
        method="roi_projected_ellipse_pair_v1",
        status="PARTIAL_RING_CANDIDATE" if is_partial else "PROJECTED_RING_EVIDENCE",
        inner_ring=inner,
        outer_ring=outer,
        projected_semiaxis_spacing_px=round(spacing, 2),
        reason=("partial_ring_requires_independent_frame" if is_partial
                else "consistent_projected_ring_boundaries_not_axial_gap"),
    )
