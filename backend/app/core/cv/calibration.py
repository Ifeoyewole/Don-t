"""Camera calibration, lens distortion rectification, and physical scale engine."""

import math
from typing import Dict, Optional, Tuple
import cv2
import numpy as np

from backend.app.schemas.calibration import CameraProfile


class CameraCalibrator:
    """Manages camera profiles and performs optical lens rectification."""

    def __init__(self):
        self._profiles: Dict[str, CameraProfile] = {}
        self._init_default_profiles()

    def _init_default_profiles(self) -> None:
        """Register default CCTV crawler and reframed wide-angle profiles."""
        # Standard sewer crawler pan-and-tilt CCTV camera
        self._profiles["CCTV-STANDARD-01"] = CameraProfile(
            camera_id="CCTV-STANDARD-01",
            resolution=(1920, 1080),
            focal_length=(1420.0, 1418.0),
            principal_point=(960.0, 540.0),
            distortion_coeffs=[-0.12, 0.025, 0.0005, -0.0002, 0.0],
            tilt_angle_deg=0.0,
            description="Standard pan-tilt CCTV crawler camera with mild barrel distortion",
        )

        # GoPro MAX 360 reframed perspective crop (wide field of view with barrel distortion)
        self._profiles["GOPRO-MAX-REFRAMED"] = CameraProfile(
            camera_id="GOPRO-MAX-REFRAMED",
            resolution=(1920, 1080),
            focal_length=(1120.0, 1115.0),
            principal_point=(960.0, 540.0),
            distortion_coeffs=[-0.18, 0.04, 0.001, -0.0005, 0.0],
            tilt_angle_deg=10.0,
            description="GoPro MAX 5.6K reframed perspective export with wide-angle distortion",
        )

    def register_profile(self, profile: CameraProfile) -> None:
        """Register or update a camera profile."""
        self._profiles[profile.camera_id] = profile

    def get_profile(self, camera_id: str) -> Optional[CameraProfile]:
        """Fetch camera profile by identifier."""
        return self._profiles.get(camera_id)

    def undistort_image(
        self,
        image_bgr: np.ndarray,
        camera_id_or_profile: Optional[str | CameraProfile] = None,
    ) -> np.ndarray:
        """Rectify radial and tangential lens distortion.

        Args:
            image_bgr: Input color image in BGR format.
            camera_id_or_profile: CameraProfile instance or registered camera_id string.

        Returns:
            np.ndarray: Lens-rectified BGR image.
        """
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        profile: Optional[CameraProfile] = None
        if isinstance(camera_id_or_profile, CameraProfile):
            profile = camera_id_or_profile
        elif isinstance(camera_id_or_profile, str):
            profile = self.get_profile(camera_id_or_profile)

        if profile is None:
            # No calibration profile provided: return unrectified image
            return image_bgr

        fx, fy = profile.focal_length
        cx, cy = profile.principal_point
        camera_matrix = np.array([
            [fx, 0.0, cx],
            [0.0, fy, cy],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

        dist_coeffs = np.array(profile.distortion_coeffs, dtype=np.float64)

        # Perform OpenCV undistort
        undistorted = cv2.undistort(image_bgr, camera_matrix, dist_coeffs)
        return undistorted

    def compute_calibrated_scale(
        self,
        outer_radius_px: float,
        pipe_diameter_mm: float,
        tilt_angle_deg: float = 0.0,
    ) -> Tuple[float, float]:
        """Calculate spatial scaling factor (pixels_per_mm and mm_per_pixel).

        Compensates for perspective foreshortening if the camera views the pipe at an off-axis angle.

        Args:
            outer_radius_px: Measured outer radius of pipe opening in pixels.
            pipe_diameter_mm: Known reference pipe diameter in millimeters.
            tilt_angle_deg: Off-axis camera tilt angle in degrees.

        Returns:
            Tuple of (pixels_per_mm, mm_per_pixel)
        """
        if pipe_diameter_mm <= 0.0 or outer_radius_px <= 0.0:
            return 1.0, 1.0

        # Major axis diameter in pixels
        detected_diameter_px = 2.0 * outer_radius_px

        # Perspective compensation factor
        # When viewed off-axis, the apparent vertical axis is foreshortened by cos(tilt)
        rad = math.radians(min(60.0, max(0.0, tilt_angle_deg)))
        cos_tilt = max(0.5, math.cos(rad))

        # True circular diameter is preserved along the transverse horizontal axis
        effective_diameter_px = detected_diameter_px / cos_tilt

        pixels_per_mm = float(effective_diameter_px / pipe_diameter_mm)
        mm_per_pixel = 1.0 / max(1e-4, pixels_per_mm)

        return round(pixels_per_mm, 4), round(mm_per_pixel, 5)


# Global singleton instance
camera_calibrator = CameraCalibrator()
