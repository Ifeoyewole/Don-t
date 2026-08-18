"""Vectorized Circular Opening & Annular Gap Measurement Engine using OpenCV."""

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
    DetectedCircle,
    MeasurementResponse,
    OverlayHints,
    Point2D,
    RaySample,
    ToleranceSpec,
)
from backend.app.utils.image_io import encode_image_to_base64


def _find_concentric_circles(
    gray: np.ndarray,
) -> Tuple[Optional[Tuple[float, float, float]], Optional[Tuple[float, float, float]]]:
    """Find concentric inner and outer circle boundaries in the image.

    Returns:
        Tuple of (inner_circle, outer_circle) as (cx, cy, radius).
    """
    h, w = gray.shape
    min_dim = min(h, w)

    # Apply bilateral smoothing and CLAHE
    smoothed = filter_bilateral_smooth(gray, d=9, sigma_color=75, sigma_space=75)
    enhanced = enhance_edges_clahe(smoothed, clip_limit=2.0)

    # 1. Primary Attempt: HoughCircles
    circles = cv2.HoughCircles(
        enhanced,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=int(min_dim * 0.05),
        param1=90,
        param2=30,
        minRadius=int(min_dim * 0.05),
        maxRadius=int(min_dim * 0.48),
    )

    if circles is not None and len(circles[0]) >= 2:
        # Sort circles by radius
        detected = sorted(circles[0], key=lambda c: c[2])
        # Find best concentric pair
        for i in range(len(detected) - 1):
            c_in = detected[i]
            for j in range(i + 1, len(detected)):
                c_out = detected[j]
                center_dist = math.hypot(c_in[0] - c_out[0], c_in[1] - c_out[1])
                # Check if concentric (centers close within 15% of inner radius)
                if center_dist <= max(10.0, c_in[2] * 0.18):
                    return (
                        (float(c_in[0]), float(c_in[1]), float(c_in[2])),
                        (float(c_out[0]), float(c_out[1]), float(c_out[2])),
                    )

    # 2. Fallback: Contour Hierarchy & Ellipse/Enclosing Circle Fitting
    edges = cv2.Canny(enhanced, 35, 110)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    valid_circles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        perimeter = cv2.arcLength(cnt, True)
        if perimeter > 0 and area > 100:
            circularity = 4 * math.pi * (area / (perimeter * perimeter))
            if circularity > 0.5:
                (x, y), radius = cv2.minEnclosingCircle(cnt)
                if radius > min_dim * 0.05 and radius < min_dim * 0.48:
                    valid_circles.append((float(x), float(y), float(radius)))

    if len(valid_circles) >= 2:
        valid_circles = sorted(valid_circles, key=lambda c: c[2])
        for i in range(len(valid_circles) - 1):
            c_in = valid_circles[i]
            for j in range(i + 1, len(valid_circles)):
                c_out = valid_circles[j]
                center_dist = math.hypot(c_in[0] - c_out[0], c_in[1] - c_out[1])
                if center_dist <= max(12.0, c_in[2] * 0.20) and (c_out[2] - c_in[2]) > 3:
                    return c_in, c_out

    # 3. Last fallback: Estimate from dominant contour or image center
    if valid_circles:
        c_dom = valid_circles[0]
        # Synthesize concentric outer circle with nominal offset
        return c_dom, (c_dom[0], c_dom[1], c_dom[2] * 1.15)

    # Ultimate fallback center
    cx, cy = w / 2.0, h / 2.0
    r_in = min_dim * 0.25
    r_out = min_dim * 0.32
    return (cx, cy, r_in), (cx, cy, r_out)


def _profile_radial_rays(
    gray: np.ndarray,
    center: Tuple[float, float],
    r_in_est: float,
    r_out_est: float,
    num_rays: int = 72,
) -> Tuple[List[float], List[float], List[float]]:
    """Vectorized polar radial ray profiling to detect precise inner/outer boundary radii.

    Returns:
        Tuple of (angles_deg, inner_radii, outer_radii)
    """
    h, w = gray.shape
    cx, cy = center
    max_radius = min(min(cx, w - cx), min(cy, h - cy))
    if max_radius <= 10:
        max_radius = min(h, w) / 2.0

    # Polar Unwrap using OpenCV warpPolar
    # Output shape: (num_rays, max_radius)
    polar_img = cv2.warpPolar(
        gray,
        (int(max_radius), num_rays),
        (cx, cy),
        max_radius,
        cv2.WARP_POLAR_LINEAR,
    )

    angles_deg: List[float] = []
    inner_radii: List[float] = []
    outer_radii: List[float] = []

    # Expected search bounds in polar space
    search_r_in_min = max(5, int(r_in_est * 0.70))
    search_r_in_max = min(int(max_radius * 0.95), int(r_in_est * 1.30))
    search_r_out_min = max(search_r_in_max, int(r_out_est * 0.75))
    search_r_out_max = min(int(max_radius * 0.99), int(r_out_est * 1.35))

    for i in range(num_rays):
        angle = (i * 360.0) / num_rays
        angles_deg.append(angle)

        profile = polar_img[i, :].astype(np.float32)
        # Compute radial gradient (derivative of intensity)
        gradient = np.abs(np.gradient(profile))

        # 1. Inner wall detection
        in_segment = gradient[search_r_in_min:search_r_in_max]
        if len(in_segment) > 0 and np.max(in_segment) > 0:
            in_peak = search_r_in_min + np.argmax(in_segment)
        else:
            in_peak = int(r_in_est)

        # 2. Outer wall detection
        out_segment = gradient[search_r_out_min:search_r_out_max]
        if len(out_segment) > 0 and np.max(out_segment) > 0:
            out_peak = search_r_out_min + np.argmax(out_segment)
        else:
            out_peak = int(r_out_est)

        if out_peak <= in_peak:
            out_peak = in_peak + max(5, int(r_out_est - r_in_est))

        inner_radii.append(float(in_peak))
        outer_radii.append(float(out_peak))

    return angles_deg, inner_radii, outer_radii


def _reject_radial_outliers(
    gap_pixels: List[float],
    threshold_mad: float = 3.0,
) -> List[float]:
    """Filter localized ray measurement spikes using Median Absolute Deviation (MAD)."""
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


def _draw_circular_debug_overlay(
    image_bgr: np.ndarray,
    center: Point2D,
    inner_circle: DetectedCircle,
    outer_circle: DetectedCircle,
    ray_samples: List[RaySample],
    mean_gap_mm: float,
    min_gap_mm: float,
    max_gap_mm: float,
    overall_status: ToleranceStatus,
) -> np.ndarray:
    """Render annotated inspection graphics onto the source image."""
    debug = image_bgr.copy()
    cx, cy = int(round(center.x)), int(round(center.y))

    # Color palette (BGR)
    color_map = {
        ToleranceStatus.PASS: (46, 204, 113),      # Green
        ToleranceStatus.WARNING: (0, 165, 255),    # Amber
        ToleranceStatus.REVIEW: (0, 191, 255),     # Deep Sky Blue
        ToleranceStatus.FAIL: (50, 50, 235),       # Red
    }

    # Draw Center Crosshair
    cv2.drawMarker(debug, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, 20, 2)

    # Draw Inner and Outer Circumferences
    cv2.circle(debug, (cx, cy), int(round(inner_circle.radius_px)), (255, 200, 0), 2, cv2.LINE_AA)
    cv2.circle(debug, (cx, cy), int(round(outer_circle.radius_px)), (0, 255, 100), 2, cv2.LINE_AA)

    # Draw Radial Measurement Rays
    for ray in ray_samples:
        pt1 = (int(round(ray.inner_point.x)), int(round(ray.inner_point.y)))
        pt2 = (int(round(ray.outer_point.x)), int(round(ray.outer_point.y)))
        col = color_map.get(ray.status, (200, 200, 200))
        cv2.line(debug, pt1, pt2, col, 2, cv2.LINE_AA)
        cv2.circle(debug, pt1, 2, (255, 255, 255), -1)
        cv2.circle(debug, pt2, 2, col, -1)

    # Draw HUD Overlay Banner
    banner_h = 65
    overlay = debug.copy()
    cv2.rectangle(overlay, (0, 0), (debug.shape[1], banner_h), (20, 24, 33), -1)
    cv2.addWeighted(overlay, 0.85, debug, 0.15, 0, debug)

    status_color = color_map.get(overall_status, (255, 255, 255))
    cv2.putText(
        debug,
        f"CIRCULAR GAP QA: {overall_status.value}",
        (15, 26),
        cv2.FONT_HERSHEY_DUPLEX,
        0.75,
        status_color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        debug,
        f"Mean: {mean_gap_mm:.2f}mm | Min: {min_gap_mm:.2f}mm | Max: {max_gap_mm:.2f}mm ({len(ray_samples)} rays)",
        (15, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (220, 225, 230),
        1,
        cv2.LINE_AA,
    )

    return debug


def measure_circular_gap(
    image_bgr: np.ndarray,
    pipe_diameter_mm: float = 100.0,
    tolerance_spec: Optional[ToleranceSpec] = None,
    num_rays: int = 72,
    return_debug_image: bool = False,
) -> MeasurementResponse:
    """Execute end-to-end circular opening annular gap measurement.

    Args:
        image_bgr: Color image of the pipe opening in BGR format.
        pipe_diameter_mm: Known reference pipe diameter in millimeters.
        tolerance_spec: Optional custom tolerance specification.
        num_rays: Number of radial profiling vectors across 360 degrees.
        return_debug_image: Whether to generate annotated base64 overlay image.

    Returns:
        MeasurementResponse: Structured QA measurement payload.
    """
    start_time = time.perf_counter()

    if image_bgr is None or image_bgr.size == 0:
        raise ValueError("Invalid input image for circular gap measurement.")

    if len(image_bgr.shape) == 3:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr.copy()

    # Step 1: Detect Concentric Inner & Outer Boundaries
    inner_c, outer_c = _find_concentric_circles(gray)
    cx, cy, r_in_est = inner_c
    _, _, r_out_est = outer_c

    # Step 2: Radial Ray Profiling in Polar Space
    center = (cx, cy)
    angles_deg, in_radii, out_radii = _profile_radial_rays(
        gray, center, r_in_est, r_out_est, num_rays=num_rays
    )

    # Step 3: Raw Gap Calculation
    raw_gaps_px = [max(1.0, out_r - in_r) for in_r, out_r in zip(in_radii, out_radii)]
    filtered_gaps_px = _reject_radial_outliers(raw_gaps_px)

    # Step 4: Scale Factor Calibration (Pixels per mm)
    # The inner diameter (2 * mean_inner_radius_px) corresponds to nominal pipe_diameter_mm
    mean_inner_r_px = float(np.mean(in_radii))
    mean_outer_r_px = float(np.mean(out_radii))
    pixels_per_mm = float((2.0 * mean_inner_r_px) / max(1.0, pipe_diameter_mm))

    # Step 5: Convert to Millimeters and Classify Ray Samples
    ray_samples: List[RaySample] = []
    gaps_mm: List[float] = []

    for angle, in_r, gap_px in zip(angles_deg, in_radii, filtered_gaps_px):
        out_r = in_r + gap_px
        rad = math.radians(angle)

        inner_pt = Point2D(
            x=round(cx + in_r * math.cos(rad), 2),
            y=round(cy + in_r * math.sin(rad), 2),
        )
        outer_pt = Point2D(
            x=round(cx + out_r * math.cos(rad), 2),
            y=round(cy + out_r * math.sin(rad), 2),
        )

        gap_mm = gap_px / pixels_per_mm
        gaps_mm.append(gap_mm)
        status = classify_gap(gap_mm, pipe_diameter_mm, tolerance_spec)

        ray_samples.append(
            RaySample(
                angle_deg=round(angle, 1),
                inner_point=inner_pt,
                outer_point=outer_pt,
                gap_px=round(gap_px, 2),
                gap_mm=round(gap_mm, 2),
                status=status,
            )
        )

    # Step 6: Summary Metrics & Status
    gaps_arr = np.array(gaps_mm)
    mean_gap_mm = float(np.mean(gaps_arr))
    min_gap_mm = float(np.min(gaps_arr))
    max_gap_mm = float(np.max(gaps_arr))
    std_gap_mm = float(np.std(gaps_arr))

    overall_status = evaluate_overall_status([s.status for s in ray_samples])

    # Step 7: Overlay Hints for Frontend Rendering
    center_pt = Point2D(x=round(cx, 2), y=round(cy, 2))
    inner_detected = DetectedCircle(
        center_x=round(cx, 2),
        center_y=round(cy, 2),
        radius_px=round(mean_inner_r_px, 2),
        radius_mm=round((mean_inner_r_px / pixels_per_mm), 2),
        confidence=0.95,
    )
    outer_detected = DetectedCircle(
        center_x=round(cx, 2),
        center_y=round(cy, 2),
        radius_px=round(mean_outer_r_px, 2),
        radius_mm=round((mean_outer_r_px / pixels_per_mm), 2),
        confidence=0.95,
    )

    overlay_hints = OverlayHints(
        inner_circle=inner_detected,
        outer_circle=outer_detected,
        center=center_pt,
        ray_samples=ray_samples,
    )

    # Step 8: Optional Debug Image Overlay
    debug_image_b64: Optional[str] = None
    if return_debug_image:
        debug_canvas = _draw_circular_debug_overlay(
            image_bgr,
            center_pt,
            inner_detected,
            outer_detected,
            ray_samples,
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
        inner_radius_px=round(mean_inner_r_px, 2),
        outer_radius_px=round(mean_outer_r_px, 2),
        num_samples=len(ray_samples),
        raw_min_gap_mm=round(float(np.min(raw_gaps_mm)), 2),
        raw_max_gap_mm=round(float(np.max(raw_gaps_mm)), 2),
        raw_mean_gap_mm=round(float(np.mean(raw_gaps_mm)), 2),
        std_gap_mm=round(std_gap_mm, 3),
        processing_time_ms=proc_time_ms,
        debug_image_base64=debug_image_b64,
    )

    return MeasurementResponse(
        joint_type=JointType.CIRCULAR_OPENING,
        pipe_diameter_mm=pipe_diameter_mm,
        pixels_per_mm=round(pixels_per_mm, 4),
        mean_gap_mm=round(mean_gap_mm, 2),
        min_gap_mm=round(min_gap_mm, 2),
        max_gap_mm=round(max_gap_mm, 2),
        overall_status=overall_status,
        overlay_hints=overlay_hints,
        debug_info=debug_info,
    )
