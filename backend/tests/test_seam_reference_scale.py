"""Physical seam units require a measured scale, never nominal pipe diameter."""
import hashlib
from dataclasses import replace

import cv2
import numpy as np
import pytest

from backend.app.core.cv.calibration_authority import VerifiedCalibration
from backend.app.core.cv.seam_detector import measure_seam_gap
from backend.app.schemas.domain import CalibrationSource, JointType


def reference():
    return VerifiedCalibration(
        reference_id='FIELD-REF', project_id='project-A', source=CalibrationSource.PHYSICAL_REFERENCE,
        pipe_diameter_mm=300, camera_id='RIG-A', validated_joint_types=('VERTICAL_SEAM',),
        reference_length_mm=10, reference_span_px=40, image_sha256=hashlib.sha256(b'original').hexdigest(),
        image_width=400, image_height=400,
    )


def test_reference_is_bound_to_original_bytes_and_resolution():
    record = reference()
    assert record.scale_for_image(record.image_sha256, 400, 400) == 4
    assert record.scale_for_image('another-image', 400, 400) is None
    assert record.scale_for_image(record.image_sha256, 800, 400) is None
    assert record.scale_for_image(record.image_sha256, 400, 800) is None


@pytest.mark.parametrize('field,value', [('reference_span_px', 0), ('reference_length_mm', -1),
    ('reference_span_px', float('nan')), ('reference_length_mm', float('inf')), ('reference_span_px', 1000)])
def test_invalid_reference_never_establishes_scale(field, value):
    record = replace(reference(), **{field: value})
    assert record.scale_for_image(record.image_sha256, 400, 400) is None


@pytest.mark.parametrize('diameter', [150, 300, 900])
def test_known_seam_scale_is_independent_of_pipe_diameter(diameter):
    image = np.full((400, 400, 3), 160, dtype=np.uint8)
    image[:, 191:209] = 25
    image = cv2.GaussianBlur(image, (3, 3), .8)
    args = dict(image_bgr=image, joint_type=JointType.VERTICAL_SEAM, pipe_diameter_mm=diameter,
                num_scanlines=20, roi_bbox=(145, 0, 255, 400))
    unscaled = measure_seam_gap(**args)
    assert unscaled.mean_gap_px > 0
    assert unscaled.authoritative_gap_mm is None
    assert unscaled.pixels_per_mm is None
    scaled = measure_seam_gap(**args, calibrated_pixels_per_mm=4)
    assert scaled.pixels_per_mm == 4
    assert scaled.authoritative_gap_mm == pytest.approx(scaled.mean_gap_px / 4, abs=.02)
    assert 3 < scaled.authoritative_gap_mm < 6
