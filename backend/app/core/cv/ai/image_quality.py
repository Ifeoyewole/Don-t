"""Pre-measurement image quality gate for pipe joint inspection.

Validates input suitability across:
- Blur / sharpness (Laplacian variance & gradient frequency energy)
- Illumination / exposure (underexposure, highlight clipping)
- Contrast (Michelson contrast & luminance standard deviation)
- Glare / specular water reflection saturation
"""

from typing import Optional, Tuple
import cv2
import numpy as np
from pydantic import BaseModel, Field


class ImageQualityResult(BaseModel):
    """Detailed diagnostic metrics for image usability validation."""
    usable: bool = Field(..., description="True if image meets minimum quality standards for reliable measurement")
    quality_score: float = Field(..., description="Fused overall quality score (0.0 to 1.0)")
    blur_score: float = Field(..., description="Sharpness metric (0.0=severely blurred, 1.0=crisp edges)")
    brightness_score: float = Field(..., description="Illumination adequacy score (0.0=extreme dark/bright, 1.0=balanced)")
    contrast_score: float = Field(..., description="Luminance dynamic range score (0.0=flat/washed out, 1.0=high contrast)")
    glare_ratio: float = Field(..., description="Fraction of image area saturated by specular highlight/glare (0.0 to 1.0)")
    rejection_reason: Optional[str] = Field(None, description="Explanation if image is deemed unusable")


def compute_blur_score(gray: np.ndarray) -> float:
    """Compute normalized sharpness score using modified Laplacian variance and peak edge gradient."""
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = float(laplacian.var())

    # Also compute edge gradient sharpness to handle localized sharp seams
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1)
    peak_grad = float(np.percentile(np.hypot(gx, gy), 99.8))

    # Variance-based score
    var_score = np.clip((variance - 15.0) / 200.0, 0.0, 1.0)
    # Peak gradient score (peak_grad > 150 is very sharp edge)
    grad_score = np.clip((peak_grad - 45.0) / 250.0, 0.0, 1.0)

    score = max(var_score, grad_score * 0.90)
    return round(float(score), 3)


def compute_exposure_scores(gray: np.ndarray) -> Tuple[float, float, float]:
    """Compute brightness score, underexposure ratio, and overexposure glare ratio.

    Returns:
        Tuple of (brightness_score, underexposed_ratio, glare_ratio)
    """
    total_pixels = float(gray.size)
    if total_pixels == 0:
        return 0.0, 1.0, 1.0

    mean_val = float(np.mean(gray))
    # Ideal CCTV pipe joint mean luminance is ~80 to 160 (out of 255)
    if mean_val < 30.0:
        brightness_score = max(0.0, mean_val / 30.0 * 0.4)
    elif mean_val > 210.0:
        brightness_score = max(0.0, (255.0 - mean_val) / 45.0 * 0.4)
    else:
        # Distance from optimal midpoint 120
        dist = abs(mean_val - 120.0)
        brightness_score = max(0.4, 1.0 - (dist / 110.0) * 0.5)

    under_ratio = float(np.count_nonzero(gray < 25)) / total_pixels
    glare_ratio = float(np.count_nonzero(gray > 245)) / total_pixels

    return round(float(brightness_score), 3), round(under_ratio, 3), round(glare_ratio, 3)


def compute_contrast_score(gray: np.ndarray) -> float:
    """Compute normalized Michelson contrast score using 1st and 99th percentiles."""
    p1 = float(np.percentile(gray, 1))
    p99 = float(np.percentile(gray, 99))
    denom = p99 + p1
    if denom < 1e-4:
        return 0.0
    michelson = (p99 - p1) / denom
    score = np.clip(michelson / 0.70, 0.0, 1.0)
    return round(float(score), 3)


def validate_image_quality(
    image_bgr: np.ndarray,
    min_quality_threshold: float = 0.45,
    min_blur_threshold: float = 0.15,
    max_glare_ratio: float = 0.25,
) -> ImageQualityResult:
    """Evaluate whether an inspection image is suitable for reliable CV measurement.

    Args:
        image_bgr: Input color image in BGR format.
        min_quality_threshold: Overall fused threshold below which image is rejected.
        min_blur_threshold: Minimum allowable sharpness score.
        max_glare_ratio: Maximum allowable specular glare saturation percentage.

    Returns:
        ImageQualityResult with detailed metrics and usability determination.
    """
    if image_bgr is None or image_bgr.size == 0:
        return ImageQualityResult(
            usable=False,
            quality_score=0.0,
            blur_score=0.0,
            brightness_score=0.0,
            contrast_score=0.0,
            glare_ratio=1.0,
            rejection_reason="Empty or unreadable image buffer.",
        )

    if len(image_bgr.shape) == 3:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr.copy()

    blur_score = compute_blur_score(gray)
    brightness_score, under_ratio, glare_ratio = compute_exposure_scores(gray)
    contrast_score = compute_contrast_score(gray)

    # Weighted fused quality score
    # Sharpness (0.40) + Exposure (0.30) + Contrast (0.30)
    fused_score = (0.40 * blur_score) + (0.30 * brightness_score) + (0.30 * contrast_score)
    # Penalize excessive glare
    if glare_ratio > 0.15:
        fused_score = max(0.0, fused_score - (glare_ratio - 0.15) * 1.5)

    fused_score = round(float(np.clip(fused_score, 0.0, 1.0)), 3)

    # Check hard rejection criteria
    usable = True
    rejection_reason: Optional[str] = None

    if blur_score < min_blur_threshold:
        usable = False
        rejection_reason = f"Image is too blurry for sub-pixel measurement (blur score {blur_score} < {min_blur_threshold})."
    elif glare_ratio > max_glare_ratio:
        usable = False
        rejection_reason = f"Excessive water reflection / torch glare obscures pipe interface ({glare_ratio * 100:.1f}% area saturated)."
    elif under_ratio > 0.70:
        usable = False
        rejection_reason = "Image is underexposed / too dark; pipe joint boundary cannot be distinguished."
    elif fused_score < min_quality_threshold:
        usable = False
        rejection_reason = f"Overall image quality ({fused_score}) is below reliable threshold ({min_quality_threshold})."

    return ImageQualityResult(
        usable=usable,
        quality_score=fused_score,
        blur_score=blur_score,
        brightness_score=brightness_score,
        contrast_score=contrast_score,
        glare_ratio=glare_ratio,
        rejection_reason=rejection_reason,
    )
