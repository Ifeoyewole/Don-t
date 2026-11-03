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
    with pytest.raises(ValueError):
        calibrator.compute_calibrated_scale(np.nan, 300.0)
    with pytest.raises(ValueError):
        calibrator.compute_calibrated_scale(150.0, np.inf)
    with pytest.raises(ValueError):
        calibrator.compute_calibrated_scale(150.0, 300.0, np.nan)


def test_list_profiles_returns_deep_snapshot():
    calibrator = CameraCalibrator()
    snapshot = calibrator.list_profiles()
    original_first_coeff = snapshot[0].distortion_coeffs[0]

    snapshot[0].description = "mutated outside calibrator"
    snapshot[0].distortion_coeffs[0] = 999.0

    fresh = calibrator.list_profiles()
    assert fresh[0].description != "mutated outside calibrator"
    assert fresh[0].distortion_coeffs[0] == pytest.approx(original_first_coeff)


class _FakeInput:
    name = "image"
    shape = [1, 3, 320, 320]


class _SingleOutputSession:
    def get_inputs(self):
        return [_FakeInput()]

    def run(self, _names, feed):
        assert feed["image"].shape == (1, 3, 320, 320)
        mask = np.zeros((1, 1, 320, 320), dtype=np.float32)
        mask[:, :, 80:240, 100:220] = 0.9
        return [mask]


class _TwoOutputSession:
    def get_inputs(self):
        return [_FakeInput()]

    def run(self, _names, feed):
        assert feed["image"].shape == (1, 3, 320, 320)
        mask = np.zeros((1, 1, 320, 320), dtype=np.float32)
        mask[:, :, 80:240, 100:220] = 0.9
        return [np.array([0.95], dtype=np.float32), mask]


class _MalformedSession:
    def get_inputs(self):
        return [_FakeInput()]

    def run(self, _names, _feed):
        return [np.array([0.95], dtype=np.float32)]


def test_segmenter_accepts_exporter_single_mask_output():
    segmenter = JointSegmenter()
    segmenter._session = _SingleOutputSession()
    image = np.zeros((240, 400, 3), dtype=np.uint8)
    result = segmenter.segment_joint(image)
    assert result.detected is True
    assert result.confidence == pytest.approx(0.9)
    assert result.mask is not None
    assert result.mask.shape == (240, 400)
    assert result.bbox is not None


def test_segmenter_keeps_two_output_compatibility():
    segmenter = JointSegmenter()
    segmenter._session = _TwoOutputSession()
    image = np.zeros((240, 400, 3), dtype=np.uint8)
    result = segmenter.segment_joint(image)
    assert result.detected is True
    assert result.confidence == pytest.approx(0.95)
    assert result.mask is not None


def test_segmenter_fails_closed_on_malformed_single_output():
    segmenter = JointSegmenter()
    segmenter._session = _MalformedSession()
    image = np.zeros((240, 400, 3), dtype=np.uint8)
    result = segmenter.segment_joint(image)
    assert result.detected is False
    assert result.confidence == 0.0
    assert "Invalid segmenter mask output shape" in (result.reason or "")
