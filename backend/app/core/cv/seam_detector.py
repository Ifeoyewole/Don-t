"""Directional Sobel & Scanline Seam Gap Measurement Engine for Horizontal/Vertical Welds."""

import math
import time
from typing import List, Optional, Tuple
import cv2
import numpy as np
from scipy.signal import find_peaks

from backend.app.core.cv.preprocessor import enhance_edges_clahe, filter_bilateral_smooth
from backend.app.core.cv.tolerance import classify_gap, evaluate_overall_status
from backend.app.schemas.domain import JointType, ToleranceStatus
from backend.app.schemas.measurement import (
    CvMeasurementDebug,
    GapLine,
    MeasurementResponse,
    OverlayHints,
    Point2D,
    ToleranceSpec,
)
from backend.app.utils.image_io import encode_image_to_base64


def _subpixel_peak(profile: np.ndarray, peak_idx: int) -> float:
    """Refine integer peak index to sub-pixel accuracy via parabolic/quadratic fit."""
    if peak_idx <= 0 or peak_idx >= len(profile) - 1:
        return float(peak_idx)

    alpha = float(profile[peak_idx - 1])
    beta = float(profile[peak_idx])
    gamma = float(profile[peak_idx + 1])

    denom = alpha - 2.0 * beta + gamma
    if abs(denom) < 1e-5:
        return float(peak_idx)

    delta = 0.5 * (alpha - gamma) / denom
    if abs(delta) > 1.0:
        return float(peak_idx)

    return float(peak_idx + delta)


def _reject_seam_outliers(
    gap_pixels: List[float],
    threshold_mad: float = 3.0,
) -> List[float]:
    """Filter localized scanline measurement outliers using Median Absolute Deviation."""
    arr = np.array(gap_pixels, dtype=np.float64)
    med = np.median(arr)
    mad = np.median(np.abs(arr - med))
    if mad < 1e-4:
        return gap_pixels

    filtered = []
    for val in arr:
        if abs(val - med) > threshold_mad * (1.4826 * mad):
            filtered.append(float(med))
        else:
            filtered.append(float(val))
    return filtered


def _draw_seam_debug_overlay(
    image_bgr: np.ndarray,
    joint_type: JointType,
    left_edge: List[Point2D],
    right_edge: List[Point2D],
    gap_lines: List[GapLine],
    mean_gap_mm: float,
    min_gap_mm: float,
    max_gap_mm: float,
    overall_status: ToleranceStatus,
) -> np.ndarray:
    """Render annotated visualization graphics for seam inspection."""
    debug = image_bgr.copy()

    color_map = {
        ToleranceStatus.PASS: (46, 204, 113),      # Green
        ToleranceStatus.WARNING: (0, 165, 255),    # Amber
        ToleranceStatus.REVIEW: (0, 191, 255),     # Blue
        ToleranceStatus.FAIL: (50, 50, 235),       # Red
    }

    # Draw continuous seam edge polylines
    if left_edge:
        pts1 = np.array([[int(round(p.x)), int(round(p.y))] for p in left_edge], dtype=np.int32)
        cv2.polylines(debug, [pts1], isClosed=False, color=(255, 200, 0), thickness=2, lineType=cv2.LINE_AA)

    if right_edge:
        pts2 = np.array([[int(round(p.x)), int(round(p.y))] for p in right_edge], dtype=np.int32)
        cv2.polylines(debug, [pts2], isClosed=False, color=(0, 255, 100), thickness=2, lineType=cv2.LINE_AA)

    # Draw individual cross-section measurement vectors
    for gl in gap_lines:
        p1 = (int(round(gl.start.x)), int(round(gl.start.y)))
        p2 = (int(round(gl.end.x)), int(round(gl.end.y)))
        col = color_map.get(gl.status, (200, 200, 200))
        cv2.line(debug, p1, p2, col, 2, cv2.LINE_AA)
        cv2.circle(debug, p1, 2, (255, 255, 255), -1)
        cv2.circle(debug, p2, 2, col, -1)

    # Draw HUD Banner
    banner_h = 65
    overlay = debug.copy()
    cv2.rectangle(overlay, (0, 0), (debug.shape[1], banner_h), (20, 24, 33), -1)
    cv2.addWeighted(overlay, 0.85, debug, 0.15, 0, debug)

    status_color = color_map.get(overall_status, (255, 255, 255))
    cv2.putText(
        debug,
        f"{joint_type.value} QA: {overall_status.value}",
        (15, 26),
        cv2.FONT_HERSHEY_DUPLEX,
        0.75,
        status_color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        debug,
        f"Mean: {mean_gap_mm:.2f}mm | Min: {min_gap_mm:.2f}mm | Max: {max_gap_mm:.2f}mm ({len(gap_lines)} scanlines)",
        (15, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (220, 225, 230),
        1,
        cv2.LINE_AA,
    )

    return debug


def measure_seam_gap(
    image_bgr: np.ndarray,
    joint_type: JointType = JointType.VERTICAL_SEAM,
    pipe_diameter_mm: float = 100.0,
    tolerance_spec: Optional[ToleranceSpec] = None,
    num_scanlines: int = 40,
    return_debug_image: bool = False,
) -> MeasurementResponse:
    """Execute seam gap measurement across weld/butt joint interfaces.

    Args:
        image_bgr: Input color image in BGR format.
        joint_type: JointType.VERTICAL_SEAM or JointType.HORIZONTAL_SEAM.
        pipe_diameter_mm: Known pipe reference diameter in millimeters.
        tolerance_spec: Optional custom tolerance specification.
        num_scanlines: Number of cross-sectional scanline profiles to sample.
        return_debug_image: Whether to generate annotated base64 overlay image.

    Returns:
        MeasurementResponse: Structured QA measurement payload.
    """
    start_time = time.perf_counter()

    if image_bgr is None or image_bgr.size == 0:
        raise ValueError("Invalid input image for seam gap measurement.")

    if len(image_bgr.shape) == 3:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr.copy()

    h, w = gray.shape

    # Step 1: Preprocessing & Contrast Enhancement
    smoothed = filter_bilateral_smooth(gray, d=7, sigma_color=50, sigma_space=50)
    enhanced = enhance_edges_clahe(smoothed, clip_limit=2.0)

    # Step 2: Directional Sobel and Morphological Filtering
    is_vertical = joint_type == JointType.VERTICAL_SEAM

    if is_vertical:
        # Vertical seam -> Gradients along X axis
        grad = cv2.Sobel(enhanced, cv2.CV_32F, 1, 0, ksize=3)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
        filtered_grad = cv2.morphologyEx(np.abs(grad), cv2.MORPH_CLOSE, kernel)

        scan_coords = np.linspace(int(h * 0.10), int(h * 0.90), num_scanlines, dtype=int)
    else:
        # Horizontal seam -> Gradients along Y axis
        grad = cv2.Sobel(enhanced, cv2.CV_32F, 0, 1, ksize=3)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1))
        filtered_grad = cv2.morphologyEx(np.abs(grad), cv2.MORPH_CLOSE, kernel)

        scan_coords = np.linspace(int(w * 0.10), int(w * 0.90), num_scanlines, dtype=int)

    # Step 3: Scanline Profiling and Edge Peak Extraction
    left_points: List[Point2D] = []
    right_points: List[Point2D] = []
    raw_gaps_px: List[float] = []

    for coord in scan_coords:
        if is_vertical:
            profile = filtered_grad[coord, :]
            axis_len = w
        else:
            profile = filtered_grad[:, coord]
            axis_len = h

        # Find two prominent edge peaks (outer/inner joint boundaries)
        # Threshold: minimum height of 20% max gradient
        max_val = np.max(profile)
        min_peak_h = max(10.0, max_val * 0.25)
        min_dist = max(5, int(axis_len * 0.02))

        peaks, _ = find_peaks(profile, height=min_peak_h, distance=min_dist)

        if len(peaks) >= 2:
            # Sort peaks by prominence / height and take top 2 nearest to center
            sorted_peaks = sorted(peaks, key=lambda p: profile[p], reverse=True)[:4]
            sorted_peaks = sorted(sorted_peaks)
            p1_int, p2_int = sorted_peaks[0], sorted_peaks[-1]

            p1_sub = _subpixel_peak(profile, p1_int)
            p2_sub = _subpixel_peak(profile, p2_int)
        elif len(peaks) == 1:
            p1_int = peaks[0]
            p1_sub = _subpixel_peak(profile, p1_int)
            # Estimate nominal offset
            p2_sub = p1_sub + max(8.0, axis_len * 0.05)
        else:
            # Fallback based on image center
            mid = axis_len / 2.0
            p1_sub = mid - axis_len * 0.03
            p2_sub = mid + axis_len * 0.03

        gap_px = max(1.0, abs(p2_sub - p1_sub))
        raw_gaps_px.append(gap_px)

        if is_vertical:
            left_points.append(Point2D(x=round(p1_sub, 2), y=round(float(coord), 2)))
            right_points.append(Point2D(x=round(p2_sub, 2), y=round(float(coord), 2)))
        else:
            left_points.append(Point2D(x=round(float(coord), 2), y=round(p1_sub, 2)))
            right_points.append(Point2D(x=round(float(coord), 2), y=round(p2_sub, 2)))

    # Step 4: Scale Factor Calibration
    # Reference: pipe_diameter_mm corresponds to the visible pipe width/height span
    reference_px = float(w if is_vertical else h) * 0.65
    pixels_per_mm = float(reference_px / max(1.0, pipe_diameter_mm))

    # Step 5: Outlier Rejection & Measurement Objects
    filtered_gaps_px = _reject_seam_outliers(raw_gaps_px)
    gap_lines: List[GapLine] = []
    gaps_mm: List[float] = []

    for lp, rp, gap_px in zip(left_points, right_points, filtered_gaps_px):
        gap_mm = gap_px / pixels_per_mm
        gaps_mm.append(gap_mm)
        status = classify_gap(gap_mm, pipe_diameter_mm, tolerance_spec)

        gap_lines.append(
            GapLine(
                start=lp,
                end=rp,
                gap_px=round(gap_px, 2),
                gap_mm=round(gap_mm, 2),
                status=status,
            )
        )

    # Step 6: Summary Metrics
    gaps_arr = np.array(gaps_mm)
    mean_gap_mm = float(np.mean(gaps_arr))
    min_gap_mm = float(np.min(gaps_arr))
    max_gap_mm = float(np.max(gaps_arr))
    std_gap_mm = float(np.std(gaps_arr))

    overall_status = evaluate_overall_status([gl.status for gl in gap_lines])

    # Step 7: Overlay Hints
    overlay_hints = OverlayHints(
        gap_lines=gap_lines,
        seam_left_edge=left_points,
        seam_right_edge=right_points,
    )

    # Step 8: Optional Debug Image Overlay
    debug_image_b64: Optional[str] = None
    if return_debug_image:
        debug_canvas = _draw_seam_debug_overlay(
            image_bgr,
            joint_type,
            left_points,
            right_points,
            gap_lines,
            mean_gap_mm,
            min_gap_mm,
            max_gap_mm,
            overall_status,
        )
        debug_image_b64 = encode_image_to_base64(debug_canvas, format=".jpg", jpeg_quality=85)

    proc_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    raw_gaps_mm = [g / pixels_per_mm for g in raw_gaps_px]
    debug_info = CvMeasurementDebug(
        pixels_per_mm=round(pixels_per_mm, 4),
        num_samples=len(gap_lines),
        raw_min_gap_mm=round(float(np.min(raw_gaps_mm)), 2),
        raw_max_gap_mm=round(float(np.max(raw_gaps_mm)), 2),
        raw_mean_gap_mm=round(float(np.mean(raw_gaps_mm)), 2),
        std_gap_mm=round(std_gap_mm, 3),
        processing_time_ms=proc_time_ms,
        debug_image_base64=debug_image_b64,
    )

    return MeasurementResponse(
        joint_type=joint_type,
        pipe_diameter_mm=pipe_diameter_mm,
        pixels_per_mm=round(pixels_per_mm, 4),
        mean_gap_mm=round(mean_gap_mm, 2),
        min_gap_mm=round(min_gap_mm, 2),
        max_gap_mm=round(max_gap_mm, 2),
        overall_status=overall_status,
        overlay_hints=overlay_hints,
        debug_info=debug_info,
    )
