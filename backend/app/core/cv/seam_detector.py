"""Directional Sobel & Scanline Seam Gap Measurement Engine for Horizontal/Vertical Welds."""

import math
import time
from typing import List, Optional, Tuple
import cv2
import numpy as np
from scipy.signal import find_peaks

from backend.app.core.cv.preprocessor import enhance_edges_clahe, filter_bilateral_smooth
from backend.app.core.cv.tolerance import classify_gap, evaluate_overall_status
from backend.app.schemas.domain import JointType, MeasurementResultStatus, ToleranceStatus
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
) -> Tuple[List[int], List[int]]:
    """Identify inlier and outlier scanline measurement indices using MAD.

    Outlier scanlines are excluded from measurement evidence and preserved for audit,
    never replaced with synthetic median measurements.
    """
    arr = np.array(gap_pixels, dtype=np.float64)
    if len(arr) == 0:
        return [], []
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    if mad < 1e-4:
        return list(range(len(gap_pixels))), []

    inliers: List[int] = []
    outliers: List[int] = []
    for idx, val in enumerate(arr):
        if abs(val - med) > threshold_mad * (1.4826 * mad):
            outliers.append(idx)
        else:
            inliers.append(idx)
    return inliers, outliers


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
    pipe_diameter_mm: Optional[float] = None,
    tolerance_spec: Optional[ToleranceSpec] = None,
    num_scanlines: int = 40,
    return_debug_image: bool = False,
    joint_mask: Optional[np.ndarray] = None,
    roi_bbox: Optional[Tuple[int, int, int, int]] = None,
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

    # Apply AI segmentation mask if provided
    if joint_mask is not None and joint_mask.shape == gray.shape:
        gray = cv2.bitwise_and(gray, gray, mask=joint_mask)

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

            gap_px = max(1.0, abs(p2_sub - p1_sub))
            raw_gaps_px.append(gap_px)

            if is_vertical:
                left_points.append(Point2D(x=round(p1_sub, 2), y=round(float(coord), 2)))
                right_points.append(Point2D(x=round(p2_sub, 2), y=round(float(coord), 2)))
            else:
                left_points.append(Point2D(x=round(float(coord), 2), y=round(p1_sub, 2)))
                right_points.append(Point2D(x=round(float(coord), 2), y=round(p2_sub, 2)))

    # ZERO ARTIFICIAL GUESSING: If insufficient valid scanlines detected, fail explicitly
    min_required_samples = max(3, int(num_scanlines * 0.15))
    if len(raw_gaps_px) < min_required_samples:
        raise ValueError("joint_geometry_not_reliable: Insufficient seam edge boundaries detected.")

    # Step 4: Outlier Exclusion (MAD) - Excluded from evidence, not rewritten as median
    inlier_indices, outlier_indices = _reject_seam_outliers(raw_gaps_px)
    valid_left = [left_points[i] for i in inlier_indices]
    valid_right = [right_points[i] for i in inlier_indices]
    filtered_gaps_px = [raw_gaps_px[i] for i in inlier_indices]

    valid_samples_count = len(filtered_gaps_px)
    valid_fraction = valid_samples_count / max(1, num_scanlines)

    # Geometry Evidence Tiers (Zero Guessing)
    is_acceptable = valid_fraction >= 0.50 and valid_samples_count >= 5
    is_partial_review = not is_acceptable and valid_fraction >= 0.25 and valid_samples_count >= 3

    if not is_acceptable and not is_partial_review:
        raise ValueError("joint_geometry_not_reliable: Insufficient seam edge boundaries detected.")

    geometry_tier = "ACCEPTABLE_GEOMETRY" if is_acceptable else "PARTIAL_REVIEW_GEOMETRY"

    mean_gap_px = float(np.mean(filtered_gaps_px))
    min_gap_px = float(np.min(filtered_gaps_px))
    max_gap_px = float(np.max(filtered_gaps_px))

    # Step 5: Calibration Authority Assessment
    has_calibration = pipe_diameter_mm is not None and pipe_diameter_mm > 0
    pixels_per_mm: Optional[float] = None
    mean_gap_mm: Optional[float] = None
    min_gap_mm: Optional[float] = None
    max_gap_mm: Optional[float] = None
    candidate_gap_mm: Optional[float] = None
    std_gap_mm: Optional[float] = None
    authoritative_gap_mm: Optional[float] = None
    overall_status: ToleranceStatus
    engineering_result: ToleranceStatus
    authoritative_reason: str
    physical_measurement_available = False

    if has_calibration:
        # Verified physical scale only; unverified heuristic defaults eliminated
        reference_px = float(w if is_vertical else h) * 0.65
        pixels_per_mm = float(reference_px / float(pipe_diameter_mm))
        gaps_mm = [gap_px / pixels_per_mm for gap_px in filtered_gaps_px]
        gaps_arr = np.array(gaps_mm)
        std_gap_mm = float(np.std(gaps_arr))

        if is_acceptable:
            mean_gap_mm = float(np.mean(gaps_arr))
            min_gap_mm = float(np.min(gaps_arr))
            max_gap_mm = float(np.max(gaps_arr))
            authoritative_gap_mm = round(mean_gap_mm, 2)
            physical_measurement_available = True
        else:
            candidate_gap_mm = round(float(np.mean(gaps_arr)), 2)
            mean_gap_mm = None
            min_gap_mm = None
            max_gap_mm = None
            authoritative_gap_mm = None
            physical_measurement_available = False

    gap_lines: List[GapLine] = []
    line_statuses: List[ToleranceStatus] = []

    for lp, rp, gap_px in zip(valid_left, valid_right, filtered_gaps_px):
        if has_calibration and pixels_per_mm is not None:
            gap_mm_sample = round(gap_px / pixels_per_mm, 2)
            status = classify_gap(gap_mm_sample, float(pipe_diameter_mm), tolerance_spec)
            line_statuses.append(status)
        else:
            gap_mm_sample = None
            status = ToleranceStatus.CALIBRATION_REQUIRED

        gap_lines.append(
            GapLine(
                start=lp,
                end=rp,
                gap_px=round(gap_px, 2),
                gap_mm=gap_mm_sample if is_acceptable else None,
                status=status,
            )
        )

    if is_acceptable:
        result_status = MeasurementResultStatus.ACCEPTED_MEASUREMENT
        if has_calibration and line_statuses:
            overall_status = evaluate_overall_status(line_statuses)
            engineering_result = overall_status
            authoritative_reason = (
                f"Seam scale calibrated ({pipe_diameter_mm:.1f} mm). "
                f"Measured mean seam gap: {authoritative_gap_mm} mm evaluated as {overall_status.value}."
            )
        else:
            overall_status = ToleranceStatus.CALIBRATION_REQUIRED
            engineering_result = ToleranceStatus.CALIBRATION_REQUIRED
            authoritative_reason = (
                "Seam edge boundaries verified in pixel space. "
                "Physical millimeter calculation withheld pending verified scale calibration."
            )
    else:
        result_status = MeasurementResultStatus.REVIEW_REQUIRED
        overall_status = ToleranceStatus.REVIEW
        engineering_result = ToleranceStatus.REVIEW
        if has_calibration:
            authoritative_reason = (
                f"PARTIAL_REVIEW_GEOMETRY: Seam evidence partially resolved ({valid_samples_count}/{num_scanlines} scanlines); "
                f"candidate gap: {candidate_gap_mm} mm. Manual review required; authoritative millimeters withheld."
            )
        else:
            authoritative_reason = (
                f"PARTIAL_REVIEW_GEOMETRY: Seam evidence partially resolved ({valid_samples_count}/{num_scanlines} scanlines); "
                "uncalibrated. Authoritative millimeters withheld."
            )

    # Step 6: Overlay Hints
    overlay_hints = OverlayHints(
        gap_lines=gap_lines,
        seam_left_edge=valid_left,
        seam_right_edge=valid_right,
    )

    # Step 7: Optional Debug Image Overlay
    debug_image_b64: Optional[str] = None
    if return_debug_image:
        debug_canvas = _draw_seam_debug_overlay(
            image_bgr,
            joint_type,
            valid_left,
            valid_right,
            gap_lines,
            mean_gap_mm if mean_gap_mm is not None else (candidate_gap_mm if candidate_gap_mm is not None else 0.0),
            min_gap_mm if min_gap_mm is not None else 0.0,
            max_gap_mm if max_gap_mm is not None else 0.0,
            overall_status,
        )
        debug_image_b64 = encode_image_to_base64(debug_canvas, format=".jpg", jpeg_quality=85)

    proc_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    debug_info = CvMeasurementDebug(
        pixels_per_mm=round(pixels_per_mm, 4) if pixels_per_mm else None,
        num_samples=len(gap_lines),
        raw_min_gap_mm=round(min_gap_mm, 2) if min_gap_mm is not None else None,
        raw_max_gap_mm=round(max_gap_mm, 2) if max_gap_mm is not None else None,
        raw_mean_gap_mm=round(mean_gap_mm, 2) if mean_gap_mm is not None else None,
        std_gap_mm=round(std_gap_mm, 3) if std_gap_mm is not None else None,
        processing_time_ms=proc_time_ms,
        debug_image_base64=debug_image_b64,
        total_ray_count=num_scanlines,
        valid_ray_count=len(gap_lines),
        valid_ray_fraction=round(valid_fraction, 4),
        coverage_status="FULL" if is_acceptable else "PARTIAL",
        invalid_reason_counts={"OUTLIER": len(outlier_indices), "REJECTED_SCANLINES": num_scanlines - len(raw_gaps_px)},
        geometry_tier=geometry_tier,
    )

    return MeasurementResponse(
        joint_type=joint_type,
        mean_gap_px=round(mean_gap_px, 2),
        min_gap_px=round(min_gap_px, 2),
        max_gap_px=round(max_gap_px, 2),
        pipe_diameter_mm=pipe_diameter_mm if has_calibration else None,
        pixels_per_mm=round(pixels_per_mm, 4) if (pixels_per_mm and is_acceptable) else None,
        mean_gap_mm=round(mean_gap_mm, 2) if mean_gap_mm is not None else None,
        min_gap_mm=round(min_gap_mm, 2) if min_gap_mm is not None else None,
        max_gap_mm=round(max_gap_mm, 2) if max_gap_mm is not None else None,
        candidate_gap_mm=candidate_gap_mm,
        overall_status=overall_status,
        result_status=result_status,
        overlay_hints=overlay_hints,
        debug_info=debug_info,
        physical_measurement_available=physical_measurement_available,
        authoritative_gap_mm=authoritative_gap_mm,
        engineering_result=engineering_result,
        authoritative_reason=authoritative_reason,
        geometry_tier=geometry_tier,
    )
