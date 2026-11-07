"""Research-only calibration-fit diagnostics.

This does NOT issue, persist, sign, or verify calibration references and is not
connected to the production calibration authority. It evaluates whether image
points of a known calibration target agree with an already estimated camera
model. Nominal pipe diameter alone is never a sufficient input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np


@dataclass(frozen=True)
class CalibrationFitReview:
    status: str  # REPROJECTION_EVIDENCE | REVIEW_REQUIRED
    rms_px: float | None
    worst_view_rms_px: float | None
    views_used: int
    reason: str


def review_reprojection_fit(
    object_points: Sequence[np.ndarray],
    image_points: Sequence[np.ndarray],
    rotation_vectors: Sequence[np.ndarray],
    translation_vectors: Sequence[np.ndarray],
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
    *,
    max_rms_px: float = 1.5,
    min_views: int = 5,
) -> CalibrationFitReview:
    """Compare independently provided target observations with a camera model.

    The caller must first obtain multi-view target measurements of KNOWN real
    geometry (e.g., checkerboard or ChArUco). This only assesses reprojection;
    it cannot establish millimetre scale for a different scene by itself.
    """
    def reject(reason: str) -> CalibrationFitReview:
        return CalibrationFitReview("REVIEW_REQUIRED", None, None, 0, reason)

    if not np.isfinite(max_rms_px) or not (0.1 <= max_rms_px <= 10.0):
        return reject("invalid_reprojection_threshold")
    count = len(object_points)
    if count < min_views or any(
        len(values) != count
        for values in (image_points, rotation_vectors, translation_vectors)
    ):
        return reject("insufficient_matching_calibration_views")
    matrix = np.asarray(camera_matrix, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        return reject("invalid_camera_intrinsics")
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0 or abs(matrix[2, 2] - 1) > 1e-6:
        return reject("invalid_focal_lengths")
    try:
        distortion = np.asarray(distortion_coefficients, dtype=np.float64)
        if not np.isfinite(distortion).all():
            return reject("invalid_distortion")
        errors_sq: list[float] = []
        per_view: list[float] = []
        for points_3d, points_2d, rotation, translation in zip(
            object_points, image_points, rotation_vectors, translation_vectors
        ):
            observed3d = np.asarray(points_3d, dtype=np.float64).reshape(-1, 3)
            observed2d = np.asarray(points_2d, dtype=np.float64).reshape(-1, 2)
            if len(observed3d) < 6 or len(observed3d) != len(observed2d):
                return reject("insufficient_target_correspondences")
            if not (np.isfinite(observed3d).all() and np.isfinite(observed2d).all()):
                return reject("nonfinite_calibration_coordinates")
            predicted, _ = cv2.projectPoints(
                observed3d, rotation, translation, matrix, distortion
            )
            residuals_sq = np.sum(
                (predicted.reshape(-1, 2) - observed2d) ** 2, axis=1
            )
            errors_sq.extend(residuals_sq.tolist())
            per_view.append(float(np.sqrt(np.mean(residuals_sq))))
    except (cv2.error, TypeError, ValueError):
        return reject("invalid_calibration_correspondences")

    rms = float(np.sqrt(np.mean(errors_sq)))
    worst = max(per_view)
    if not (np.isfinite(rms) and np.isfinite(worst)):
        return reject("nonfinite_reprojection_error")
    status = "REPROJECTION_EVIDENCE" if rms <= max_rms_px and worst <= 2 * max_rms_px else "REVIEW_REQUIRED"
    return CalibrationFitReview(
        status=status,
        rms_px=round(rms, 3),
        worst_view_rms_px=round(worst, 3),
        views_used=count,
        reason=("reprojection_error_within_research_threshold" if status == "REPROJECTION_EVIDENCE"
                else "reprojection_error_above_threshold"),
    )
