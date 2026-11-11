"""Research conversion through existing server authority; no nominal scaling."""
import math
import cv2
import numpy as np

from backend.app.core.cv.calibration_authority import get_verified_calibration
from backend.app.schemas.domain import CalibrationSource


UNAVAILABLE = 'Measurement unavailable — calibration or reliable joint boundaries required'


def calibrated_gap(evidence, *, image_sha256, dimensions, context, geometry):
    unavailable = {'physical_gap_mm': None, 'calibration_authority_verified': False,
                   'calibration_status': 'UNVERIFIED', 'measurement_message': UNAVAILABLE}
    if evidence.get('gap_estimate_px') is None or evidence.get('status') != 'VISIBLE_GAP_PIXEL_CANDIDATE':
        return dict(unavailable, reason='RELIABLE_OPPOSING_EDGES_REQUIRED')
    if geometry == 'CIRCULAR_OPENING':
        return dict(unavailable, reason='PROJECTED_RADIAL_SPACING_REQUIRES_INDEPENDENT_AXIAL_DEPTH_MODEL')
    try:
        source = CalibrationSource(context.get('calibration_source'))
        if source.value not in ('PHYSICAL_REFERENCE', 'TEST_RIG', 'CAMERA_CALIBRATION'):
            return dict(unavailable, reason='NOMINAL_METADATA_IS_NOT_PHYSICAL_SCALE')
        reference = get_verified_calibration(reference_id=context.get('calibration_reference_id'),
            project_id=context.get('project_id'), camera_id=context.get('camera_id'),
            pipe_diameter_mm=context.get('pipe_diameter_mm'), source=source, joint_type=geometry)
        if not reference or not reference.joint_plane_verified or reference.measurement_direction != 'AXIAL_JOINT_GAP':
            return dict(unavailable, reason='VERIFIED_JOINT_PLANE_AND_DIRECTION_REQUIRED')
        pixels_per_mm = reference.scale_for_image(image_sha256, *dimensions)
        if not pixels_per_mm:
            return dict(unavailable, reason='REFERENCE_IMAGE_HASH_OR_RESOLUTION_MISMATCH')
        pairs = evidence.get('edge_pairs', [])
        if len(pairs) < 16:
            return dict(unavailable, reason='INSUFFICIENT_EDGE_PAIRS')
        points = np.asarray([[p['a'], p['b']] for p in pairs], np.float64)
        if not np.isfinite(points).all(): raise ValueError('Nonfinite points')
        if not reference.image_is_rectified:
            matrix = np.asarray(reference.camera_matrix, np.float64)
            distortion = np.asarray(reference.distortion_coefficients, np.float64)
            if (matrix.shape != (3, 3) or not np.isfinite(matrix).all()
                    or distortion.size not in (4, 5, 8, 12, 14) or not np.isfinite(distortion).all()):
                return dict(unavailable, reason='VERIFIED_CAMERA_DISTORTION_MODEL_REQUIRED')
            points = cv2.undistortPoints(points.reshape(-1, 1, 2), matrix, distortion, P=matrix).reshape(-1, 2, 2)
        if reference.plane_homography is not None:
            transform = np.asarray(reference.plane_homography, np.float64)
            if transform.shape != (3, 3) or not np.isfinite(transform).all() or abs(np.linalg.det(transform)) < 1e-9:
                raise ValueError('Invalid plane transform')
            homogeneous = np.column_stack((points.reshape(-1, 2), np.ones(points.size//2)))@transform.T
            if np.any(np.abs(homogeneous[:, 2]) < 1e-8): raise ValueError('Projection singularity')
            points = (homogeneous[:, :2]/homogeneous[:, 2:]).reshape(-1, 2, 2)
        elif not reference.image_is_rectified:
            return dict(unavailable, reason='VERIFIED_JOINT_PLANE_RECTIFICATION_REQUIRED')
        widths = np.linalg.norm(points[:, 1]-points[:, 0], axis=1)/pixels_per_mm
        median = float(np.median(widths)); mad = float(np.median(np.abs(widths-median)))
        if not np.isfinite(widths).all() or median <= 0 or mad/median > .15:
            return dict(unavailable, reason='RECTIFIED_PHYSICAL_EDGE_PAIRS_UNSTABLE')
        uncertainty = reference.scale_uncertainty_fraction
        if uncertainty is not None and (type(uncertainty) not in (int, float) or not math.isfinite(uncertainty) or not 0 <= uncertainty < 1):
            return dict(unavailable, reason='INVALID_SERVER_CALIBRATION_UNCERTAINTY')
        return {'physical_gap_mm': median, 'calibration_authority_verified': True,
                'calibration_status': 'VERIFIED_IMAGE_JOINT_PLANE',
                'calibration_reference_id': reference.reference_id,
                'repeatability_mad_mm': mad,
                'calibration_uncertainty_mm': median*uncertainty if uncertainty is not None else None,
                'measurement_message': 'Calibrated research gap estimate in mm; engineering review required',
                'engineering_acceptance': False}
    except (ValueError, TypeError, cv2.error, OverflowError):
        return dict(unavailable, reason='CALIBRATION_OR_RECTIFICATION_INVALID')
