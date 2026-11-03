
import numpy as np
import pytest

from backend.app.core.cv.ai.joint_segmenter import JointSegmenter
from backend.app.core.cv.calibration import CameraCalibrator


def test_undistort_scales_intrinsics_to_runtime_resolution(monkeypatch):
    calibrator = CameraCalibrator()
    image = np.zeros((540, 960, 3), dtype=np.uint8)
    captured = {}

    def fake_undistort(frame, camera_matrix, dist_coeffs):
        captured["matrix"] = camera_matrix.copy()
        return frame

    monkeypatch.setattr("backend.app.core.cv.calibration.cv2.undistort", fake_undistort)
    calibrator.undistort_image(image, "CCTV-STANDARD-01")

    matrix = captured["matrix"]
    assert matrix[0, 0] == pytest.approx(710.0)
    assert matrix[1, 1] == pytest.approx(709.0)
    assert matrix[0, 2] == pytest.approx(480.0)
    assert matrix[1, 2] == pytest.approx(270.0)


def test_invalid_scale_inputs_fail_closed():
    calibrator = CameraCalibrator()
    with pytest.raises(ValueError):
        calibrator.compute_calibrated_scale(0.0, 300.0)
    with pytest.raises(ValueError):
        calibrator.compute_calibrated_scale(150.0, 0.0)


class _FakeInput:
    name = "image"
    shape = [1, 3, 320, 320]


class _ValidSession:
    def get_inputs(self):
        return [_FakeInput()]

    def run(self, _names, feed):
        assert feed["image"].shape == (1, 3, 320, 320)
        return [np.array([0.95], dtype=np.float32), np.ones((1, 1, 320, 320), dtype=np.float32)]


class _MalformedSession:
    def get_inputs(self):
        return [_FakeInput()]

    def run(self, _names, _feed):
        return [np.array([0.95], dtype=np.float32)]


def test_segmenter_uses_model_input_shape_and_validates_outputs():
    segmenter = JointSegmenter()
    segmenter._session = _ValidSession()
    image = np.zeros((240, 400, 3), dtype=np.uint8)
    result = segmenter.segment_joint(image)
    assert result.detected is True
    assert result.confidence == pytest.approx(0.95)
    assert result.mask is not None
    assert result.mask.shape == (240, 400)


def test_segmenter_fails_closed_on_malformed_contract():
    segmenter = JointSegmenter()
    segmenter._session = _MalformedSession()
    image = np.zeros((240, 400, 3), dtype=np.uint8)
    result = segmenter.segment_joint(image)
    assert result.detected is False
    assert result.confidence == 0.0
    assert "must return confidence and mask" in (result.reason or "")
