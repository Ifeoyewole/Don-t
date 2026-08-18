"""Image quality assessment and computer vision preprocessing pipeline."""

from typing import List, Tuple
import cv2
import numpy as np
from backend.app.schemas.domain import ExposureStatus
from backend.app.schemas.validation import PhotoQualityResult

# Default Quality Thresholds
DEFAULT_BLUR_THRESHOLD: float = 100.0
DEFAULT_MIN_BRIGHTNESS: float = 45.0
DEFAULT_MAX_BRIGHTNESS: float = 215.0
DEFAULT_GLARE_PIXEL_INTENSITY: int = 250
DEFAULT_MAX_GLARE_PERCENTAGE: float = 4.0


def validate_photo_quality(
    image_bgr: np.ndarray,
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD,
    min_brightness: float = DEFAULT_MIN_BRIGHTNESS,
    max_brightness: float = DEFAULT_MAX_BRIGHTNESS,
    glare_threshold_val: int = DEFAULT_GLARE_PIXEL_INTENSITY,
    max_glare_pct: float = DEFAULT_MAX_GLARE_PERCENTAGE,
) -> PhotoQualityResult:
    """Assess whether an input inspection image satisfies quality requirements for automated CV measurement.

    Evaluates:
    1. Sharpness / Blur via Laplacian variance.
    2. Exposure & Luminance uniformity.
    3. Specular Glare / Highlight saturation.

    Args:
        image_bgr: Input color image in BGR format.
        blur_threshold: Minimum Laplacian variance for acceptable focus.
        min_brightness: Lower bound on average luminance (0-255).
        max_brightness: Upper bound on average luminance (0-255).
        glare_threshold_val: Pixel intensity considered saturated highlight.
        max_glare_pct: Maximum allowed percentage of glare pixels before flagging.

    Returns:
        PhotoQualityResult: Structured quality metrics and user recommendations.
    """
    if image_bgr is None or image_bgr.size == 0:
        raise ValueError("Invalid image input for quality validation.")

    # Convert to Grayscale
    if len(image_bgr.shape) == 3:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr.copy()

    # 1. Blur Detection using Laplacian Variance
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = float(laplacian.var())
    is_blurry = blur_score < blur_threshold

    # 2. Exposure Assessment
    mean_brightness = float(np.mean(gray))
    if mean_brightness < min_brightness:
        exposure_status = ExposureStatus.UNDEREXPOSED
    elif mean_brightness > max_brightness:
        exposure_status = ExposureStatus.OVEREXPOSED
    else:
        exposure_status = ExposureStatus.OK

    # 3. Specular Glare Detection
    glare_mask = gray >= glare_threshold_val
    glare_pixel_count = int(np.count_nonzero(glare_mask))
    total_pixels = int(gray.size)
    glare_percentage = float((glare_pixel_count / total_pixels) * 100.0)
    glare_detected = glare_percentage > max_glare_pct

    # Generate Actionable Recommendations
    recommendations: List[str] = []
    if is_blurry:
        recommendations.append(
            f"Image is out of focus (sharpness score {blur_score:.1f} < {blur_threshold:.1f}). "
            "Hold camera steady or tap screen to refocus."
        )

    if exposure_status == ExposureStatus.UNDEREXPOSED:
        recommendations.append(
            f"Scene is underexposed (brightness {mean_brightness:.1f}/255). "
            "Turn on work lighting or device flashlight."
        )
    elif exposure_status == ExposureStatus.OVEREXPOSED:
        recommendations.append(
            f"Scene is overexposed (brightness {mean_brightness:.1f}/255). "
            "Reduce direct illumination or adjust camera exposure downward."
        )

    if glare_detected:
        recommendations.append(
            f"High specular glare detected ({glare_percentage:.1f}% saturated). "
            "Re-angle camera relative to light sources to eliminate hot-spots on metal surfaces."
        )

    is_acceptable = not is_blurry and exposure_status == ExposureStatus.OK and not glare_detected

    return PhotoQualityResult(
        blur_score=round(blur_score, 2),
        is_blurry=is_blurry,
        mean_brightness=round(mean_brightness, 2),
        exposure_status=exposure_status,
        glare_percentage=round(glare_percentage, 2),
        glare_detected=glare_detected,
        is_acceptable=is_acceptable,
        recommendations=recommendations,
    )


def filter_bilateral_smooth(
    image: np.ndarray,
    d: int = 9,
    sigma_color: float = 75.0,
    sigma_space: float = 75.0,
) -> np.ndarray:
    """Apply bilateral filtering to smooth surface texture while preserving sharp structural edges.

    Args:
        image: Grayscale or BGR image.
        d: Diameter of each pixel neighborhood.
        sigma_color: Filter sigma in color space.
        sigma_space: Filter sigma in coordinate space.

    Returns:
        np.ndarray: Smoothed image with crisp edge boundaries.
    """
    return cv2.bilateralFilter(image, d, sigma_color, sigma_space)


def enhance_edges_clahe(
    gray: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8),
) -> np.ndarray:
    """Enhance local contrast of metallic pipe edges using Contrast Limited Adaptive Histogram Equalization.

    Args:
        gray: Single-channel grayscale image.
        clip_limit: Threshold for contrast limiting.
        tile_grid_size: Size of local equalization grid.

    Returns:
        np.ndarray: Contrast-enhanced grayscale image.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(gray)


def prepare_edges(
    image_bgr: np.ndarray,
    blur_ksize: int = 5,
    canny_low: int = 40,
    canny_high: int = 120,
) -> Tuple[np.ndarray, np.ndarray]:
    """Execute complete preprocessing pipeline preparing grayscale and edge maps for detection.

    Args:
        image_bgr: Color input image.
        blur_ksize: Gaussian blur kernel size.
        canny_low: Lower Canny edge detection threshold.
        canny_high: Upper Canny edge detection threshold.

    Returns:
        Tuple[np.ndarray, np.ndarray]: (preprocessed_grayscale, binary_edge_map)
    """
    if len(image_bgr.shape) == 3:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr.copy()

    # Step 1: Bilateral smoothing
    smoothed = cv2.bilateralFilter(gray, 7, 50, 50)

    # Step 2: CLAHE local contrast
    enhanced = enhance_edges_clahe(smoothed, clip_limit=2.5)

    # Step 3: Canny edges
    edges = cv2.Canny(enhanced, canny_low, canny_high)

    return enhanced, edges
