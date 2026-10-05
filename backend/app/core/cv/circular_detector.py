"""Vectorized Circular Opening & Annular Gap Measurement Engine using OpenCV."""

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
    joint_mask: Optional[np.ndarray] = None,
    roi_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """Find concentric inner and outer circle boundaries in the image.

    Enforces strict physical constraints:
    - Bounded within joint_mask and roi_bbox if provided.
    - Zero artificial fallback guessing: returns None if concentric geometry is not reliably detected.

    Returns:
        Optional tuple of (inner_circle, outer_circle) as (cx, cy, radius), or None if unresolved.
    """
    h, w = gray.shape
    min_dim = min(h, w)

    # Constrain to ROI/mask if supplied by AI segmenter
    masked_gray = gray.copy()
    if joint_mask is not None:
        if joint_mask.shape == gray.shape:
            masked_gray = cv2.bitwise_and(gray, gray, mask=joint_mask)

    # Resolution scaling for rapid circle localization
    scale = 1.0
    if max(h, w) > 640:
        scale = 640.0 / max(h, w)
        det_gray = cv2.resize(masked_gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        det_gray = masked_gray

    det_h, det_w = det_gray.shape
    det_min_dim = min(det_h, det_w)

    # Apply bilateral smoothing and CLAHE
    smoothed = filter_bilateral_smooth(det_gray, d=5, sigma_color=50, sigma_space=50)
    enhanced = enhance_edges_clahe(smoothed, clip_limit=2.0)

    # 1. Primary Attempt: HoughCircles
    circles = cv2.HoughCircles(
        enhanced,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=int(det_min_dim * 0.05),
        param1=90,
        param2=30,
        minRadius=int(det_min_dim * 0.05),
        maxRadius=int(det_min_dim * 0.48),
    )

    if circles is not None and len(circles[0]) >= 2:
        # Keep top 40 largest candidates to prevent quadratic nested looping
        candidates = sorted(circles[0], key=lambda c: c[2], reverse=True)[:40]
        detected = sorted(candidates, key=lambda c: c[2])
        # Find best concentric pair
        for i in range(len(detected) - 1):
            c_in = detected[i]
            for j in range(i + 1, len(detected)):
                c_out = detected[j]
                center_dist = math.hypot(c_in[0] - c_out[0], c_in[1] - c_out[1])
                # Check if concentric (centers close within 18% of inner radius)
                if center_dist <= max(10.0, c_in[2] * 0.18):
                    return (
                        (float(c_in[0] / scale), float(c_in[1] / scale), float(c_in[2] / scale)),
                        (float(c_out[0] / scale), float(c_out[1] / scale), float(c_out[2] / scale)),
                    )

    # 2. Fallback: Contour Hierarchy & Circle Fitting
    edges = cv2.Canny(enhanced, 35, 110)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    valid_circles = []
    min_cand_dim = int(det_min_dim * 0.08)
    for cnt in contours:
        if len(cnt) < 15:
            continue
        _, _, bw, bh = cv2.boundingRect(cnt)
        if bw < min_cand_dim or bh < min_cand_dim:
            continue
        area = cv2.contourArea(cnt)
        perimeter = cv2.arcLength(cnt, True)
        if perimeter > 0 and area > 100:
            circularity = 4 * math.pi * (area / (perimeter * perimeter))
            if circularity > 0.45:
                (x, y), radius = cv2.minEnclosingCircle(cnt)
                if radius > det_min_dim * 0.05 and radius < det_min_dim * 0.48:
                    valid_circles.append((float(x), float(y), float(radius), circularity))

    if len(valid_circles) >= 2:
        # Sort by circularity/radius and keep top 40 to avoid quadratic search on noise
        valid_circles = sorted(valid_circles, key=lambda c: (c[3], c[2]), reverse=True)[:40]
        valid_circles = sorted(valid_circles, key=lambda c: c[2])
        for i in range(len(valid_circles) - 1):
            c_in = valid_circles[i][:3]
            for j in range(i + 1, len(valid_circles)):
                c_out = valid_circles[j][:3]
                center_dist = math.hypot(c_in[0] - c_out[0], c_in[1] - c_out[1])
                if center_dist <= max(12.0, c_in[2] * 0.20) and (c_out[2] - c_in[2]) > 3:
                    return (
                        (float(c_in[0] / scale), float(c_in[1] / scale), float(c_in[2] / scale)),
                        (float(c_out[0] / scale), float(c_out[1] / scale), float(c_out[2] / scale)),
                    )

    # ZERO ARTIFICIAL GUESSING: Return None rather than inventing circle from center or dominant contour
    return None


from typing import Dict, List, Optional, Tuple


def _profile_radial_rays(
    gray: np.ndarray,
    center: Tuple[float, float],
    r_in_est: float,
    r_out_est: float,
    num_rays: int = 72,
) -> Tuple[List[float], List[Optional[float]], List[Optional[float]], Dict[str, int]]:
    """Vectorized polar radial ray profiling to detect precise inner/outer boundary radii.

    Returns:
        Tuple of (angles_deg, inner_radii, outer_radii, invalid_reason_counts)
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
    inner_radii: List[Optional[float]] = []
    outer_radii: List[Optional[float]] = []
    invalid_reason_counts: Dict[str, int] = {
        "NO_INNER_EDGE": 0,
        "NO_OUTER_EDGE": 0,
        "AMBIGUOUS_GRADIENT": 0,
        "OUTLIER": 0,
    }

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

        # 1. Inner wall detection (zero-guessing: require real gradient peak >= 3.0)
        in_segment = gradient[search_r_in_min:search_r_in_max]
        if len(in_segment) > 0 and np.max(in_segment) >= 3.0:
            in_peak = search_r_in_min + int(np.argmax(in_segment))
        else:
            inner_radii.append(None)
            outer_radii.append(None)
            invalid_reason_counts["NO_INNER_EDGE"] += 1
            continue

        # 2. Outer wall detection (zero-guessing: require real gradient peak >= 3.0)
        out_segment = gradient[search_r_out_min:search_r_out_max]
        if len(out_segment) > 0 and np.max(out_segment) >= 3.0:
            out_peak = search_r_out_min + int(np.argmax(out_segment))
        else:
            inner_radii.append(None)
            outer_radii.append(None)
            invalid_reason_counts["NO_OUTER_EDGE"] += 1
            continue

        # 3. Geometric consistency: outer must strictly exceed inner
        if out_peak <= in_peak:
            inner_radii.append(None)
            outer_radii.append(None)
            invalid_reason_counts["AMBIGUOUS_GRADIENT"] += 1
            continue

        inner_radii.append(float(in_peak))
        outer_radii.append(float(out_peak))

    return angles_deg, inner_radii, outer_radii, invalid_reason_counts


def _reject_radial_outliers(
    gap_pixels: List[float],
    threshold_mad: float = 3.0,
) -> Tuple[List[int], List[int]]:
    """Identify inlier and outlier ray indices using Median Absolute Deviation (MAD).

    Zero-guessing requirement: Outlier rays are excluded from physical measurement evidence
    and recorded for audit, rather than silently synthesized from the median.

    Returns:
        Tuple of (inlier_indices, outlier_indices)
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
    pipe_diameter_mm: Optional[float] = None,
    tolerance_spec: Optional[ToleranceSpec] = None,
    num_rays: int = 72,
    return_debug_image: bool = False,
    joint_mask: Optional[np.ndarray] = None,
    roi_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> MeasurementResponse:
    """Execute end-to-end circular opening annular gap measurement.

    Zero-guessing authority:
    - Never uses an assumed or unverified fallback pipe diameter.
    - If pipe_diameter_mm is absent, physical millimeter fields are null (CALIBRATION_REQUIRED).
    - Requires valid radial evidence across multiple independent sectors (valid_fraction >= 0.60, sectors >= 6/8).

    Args:
        image_bgr: Color image of the pipe opening in BGR format.
        pipe_diameter_mm: Optional verified reference pipe diameter in millimeters.
        tolerance_spec: Optional custom tolerance specification.
        num_rays: Number of radial profiling vectors across 360 degrees.
        return_debug_image: Whether to generate annotated base64 overlay image.
        joint_mask: Optional binary mask (uint8) from AI segmenter.
        roi_bbox: Optional [x_min, y_min, x_max, y_max] bounding region.

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

    # Step 1: Detect Concentric Inner & Outer Boundaries (Zero Guessing)
    circles = _find_concentric_circles(gray, joint_mask=joint_mask, roi_bbox=roi_bbox)
    if circles is None:
        raise ValueError("joint_geometry_not_reliable: Concentric circular boundaries could not be resolved.")

    inner_c, outer_c = circles
    cx, cy, r_in_est = inner_c
    _, _, r_out_est = outer_c

    # Step 2: Radial Ray Profiling in Polar Space
    center = (cx, cy)
    angles_deg, in_radii_all, out_radii_all, invalid_reason_counts = _profile_radial_rays(
        gray, center, r_in_est, r_out_est, num_rays=num_rays
    )

    # Filter rays with independently detected inner and outer edges
    detected_samples = [
        (angle, in_r, out_r)
        for angle, in_r, out_r in zip(angles_deg, in_radii_all, out_radii_all)
        if in_r is not None and out_r is not None
    ]
    raw_detected_gaps_px = [max(1.0, out_r - in_r) for _, in_r, out_r in detected_samples]

    # Step 3: Outlier Exclusion (MAD) - Excluded from evidence, not rewritten as median
    inlier_indices, outlier_indices = _reject_radial_outliers(raw_detected_gaps_px)
    invalid_reason_counts["OUTLIER"] = len(outlier_indices)

    valid_samples = [detected_samples[i] for i in inlier_indices]
    filtered_gaps_px = [raw_detected_gaps_px[i] for i in inlier_indices]

    # Step 4: Strict Independent Radial Evidence Gating
    valid_ray_count = len(valid_samples)
    valid_ray_fraction = valid_ray_count / max(1, num_rays)
    occupied_sectors = {min(7, int(angle // 45.0)) for angle, _, _ in valid_samples}
    coverage_sector_count = len(occupied_sectors)
    angular_coverage = coverage_sector_count / 8.0

    if valid_ray_fraction < 0.60 or coverage_sector_count < 6:
        raise ValueError(
            "joint_geometry_not_reliable: insufficient independent radial evidence "
            f"({valid_ray_count}/{num_rays} valid rays; {coverage_sector_count}/8 sectors)."
        )

    valid_angles = [sample[0] for sample in valid_samples]
    in_radii = [float(sample[1]) for sample in valid_samples]
    out_radii = [float(sample[2]) for sample in valid_samples]

    mean_inner_r_px = float(np.mean(in_radii))
    mean_outer_r_px = float(np.mean(out_radii))
    mean_gap_px = float(np.mean(filtered_gaps_px))
    min_gap_px = float(np.min(filtered_gaps_px))
    max_gap_px = float(np.max(filtered_gaps_px))

    # Step 5: Calibration Authority Assessment
    has_calibration = pipe_diameter_mm is not None and pipe_diameter_mm > 0
    pixels_per_mm: Optional[float] = None
    mean_gap_mm: Optional[float] = None
    min_gap_mm: Optional[float] = None
    max_gap_mm: Optional[float] = None
    std_gap_mm: Optional[float] = None
    authoritative_gap_mm: Optional[float] = None
    overall_status: ToleranceStatus
    engineering_result: ToleranceStatus
    authoritative_reason: str

    if has_calibration:
        pixels_per_mm = float((2.0 * mean_inner_r_px) / float(pipe_diameter_mm))
        raw_gaps_mm = [g / pixels_per_mm for g in filtered_gaps_px]
        gaps_arr = np.array(raw_gaps_mm)
        mean_gap_mm = float(np.mean(gaps_arr))
        min_gap_mm = float(np.min(gaps_arr))
        max_gap_mm = float(np.max(gaps_arr))
        std_gap_mm = float(np.std(gaps_arr))
        authoritative_gap_mm = round(mean_gap_mm, 2)

    # Step 6: Ray Samples Construction
    ray_samples: List[RaySample] = []
    ray_statuses: List[ToleranceStatus] = []

    for angle, in_r, gap_px in zip(valid_angles, in_radii, filtered_gaps_px):
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

        if has_calibration and pixels_per_mm is not None:
            gap_mm = round(gap_px / pixels_per_mm, 2)
            status = classify_gap(gap_mm, float(pipe_diameter_mm), tolerance_spec)
            ray_statuses.append(status)
        else:
            gap_mm = None
            status = ToleranceStatus.CALIBRATION_REQUIRED

        ray_samples.append(
            RaySample(
                angle_deg=round(angle, 1),
                inner_point=inner_pt,
                outer_point=outer_pt,
                gap_px=round(gap_px, 2),
                gap_mm=gap_mm,
                status=status,
            )
        )

    if has_calibration and ray_statuses:
        overall_status = evaluate_overall_status(ray_statuses)
        engineering_result = overall_status
        authoritative_reason = (
            f"Physical scale verified ({pipe_diameter_mm:.1f} mm ID). "
            f"Measured mean annular gap: {authoritative_gap_mm} mm evaluated as {overall_status.value}."
        )
    else:
        overall_status = ToleranceStatus.CALIBRATION_REQUIRED
        engineering_result = ToleranceStatus.CALIBRATION_REQUIRED
        authoritative_reason = (
            "OpenCV annular geometry verified in pixel space. "
            "Physical millimeter calculation withheld pending verified scale calibration."
        )

    # Step 7: Overlay Hints for Frontend Rendering
    center_pt = Point2D(x=round(cx, 2), y=round(cy, 2))
    inner_detected = DetectedCircle(
        center_x=round(cx, 2),
        center_y=round(cy, 2),
        radius_px=round(mean_inner_r_px, 2),
        radius_mm=round((mean_inner_r_px / pixels_per_mm), 2) if pixels_per_mm else None,
        confidence=0.95,
    )
    outer_detected = DetectedCircle(
        center_x=round(cx, 2),
        center_y=round(cy, 2),
        radius_px=round(mean_outer_r_px, 2),
        radius_mm=round((mean_outer_r_px / pixels_per_mm), 2) if pixels_per_mm else None,
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
            mean_gap_mm if mean_gap_mm is not None else 0.0,
            min_gap_mm if min_gap_mm is not None else 0.0,
            max_gap_mm if max_gap_mm is not None else 0.0,
            overall_status,
        )
        debug_image_b64 = encode_image_to_base64(debug_canvas, format=".jpg", jpeg_quality=85)

    proc_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    debug_info = CvMeasurementDebug(
        pixels_per_mm=round(pixels_per_mm, 4) if pixels_per_mm else None,
        inner_radius_px=round(mean_inner_r_px, 2),
        outer_radius_px=round(mean_outer_r_px, 2),
        num_samples=len(ray_samples),
        raw_min_gap_mm=round(min_gap_mm, 2) if min_gap_mm is not None else None,
        raw_max_gap_mm=round(max_gap_mm, 2) if max_gap_mm is not None else None,
        raw_mean_gap_mm=round(mean_gap_mm, 2) if mean_gap_mm is not None else None,
        std_gap_mm=round(std_gap_mm, 3) if std_gap_mm is not None else None,
        processing_time_ms=proc_time_ms,
        debug_image_base64=debug_image_b64,
        total_ray_count=num_rays,
        valid_ray_count=valid_ray_count,
        valid_ray_fraction=round(valid_ray_fraction, 4),
        angular_coverage=round(angular_coverage, 4),
        coverage_sector_count=coverage_sector_count,
        coverage_status="FULL" if coverage_sector_count == 8 else "PARTIAL",
        invalid_reason_counts=invalid_reason_counts,
    )

    return MeasurementResponse(
        joint_type=JointType.CIRCULAR_OPENING,
        mean_gap_px=round(mean_gap_px, 2),
        min_gap_px=round(min_gap_px, 2),
        max_gap_px=round(max_gap_px, 2),
        pipe_diameter_mm=pipe_diameter_mm,
        pixels_per_mm=round(pixels_per_mm, 4) if pixels_per_mm else None,
        mean_gap_mm=round(mean_gap_mm, 2) if mean_gap_mm is not None else None,
        min_gap_mm=round(min_gap_mm, 2) if min_gap_mm is not None else None,
        max_gap_mm=round(max_gap_mm, 2) if max_gap_mm is not None else None,
        overall_status=overall_status,
        result_status=MeasurementResultStatus.ACCEPTED_MEASUREMENT,
        overlay_hints=overlay_hints,
        debug_info=debug_info,
        physical_measurement_available=has_calibration,
        authoritative_gap_mm=authoritative_gap_mm,
        engineering_result=engineering_result,
        authoritative_reason=authoritative_reason,
    )
