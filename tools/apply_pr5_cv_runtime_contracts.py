from pathlib import Path

ROOT = Path.cwd()


def patch(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected block not found in {path}: {old[:220]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')
    print('patched', path)


def write(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + '\n', encoding='utf-8')
    print('wrote', path)

# Scale camera intrinsics to the actual runtime image resolution before
# undistortion. Distortion coefficients remain dimensionless.
patch(
    'backend/app/core/cv/calibration.py',
    '''    def get_profile(self, camera_id: str) -> Optional[CameraProfile]:\n        """Fetch camera profile by identifier."""\n        return self._profiles.get(camera_id)\n''',
    '''    def get_profile(self, camera_id: str) -> Optional[CameraProfile]:\n        """Fetch camera profile by identifier."""\n        return self._profiles.get(camera_id)\n\n    def list_profiles(self) -> list[CameraProfile]:\n        """Return a snapshot of registered profiles without exposing mutable storage."""\n        return list(self._profiles.values())\n''',
)
patch(
    'backend/app/core/cv/calibration.py',
    '''        fx, fy = profile.focal_length\n        cx, cy = profile.principal_point\n        camera_matrix = np.array([\n            [fx, 0.0, cx],\n            [0.0, fy, cy],\n            [0.0, 0.0, 1.0],\n        ], dtype=np.float64)\n''',
    '''        fx, fy = profile.focal_length\n        cx, cy = profile.principal_point\n\n        profile_w, profile_h = profile.resolution\n        image_h, image_w = image_bgr.shape[:2]\n        if profile_w <= 0 or profile_h <= 0:\n            raise ValueError(f"Camera profile '{profile.camera_id}' has an invalid calibration resolution.")\n\n        scale_x = image_w / float(profile_w)\n        scale_y = image_h / float(profile_h)\n        fx *= scale_x\n        fy *= scale_y\n        cx *= scale_x\n        cy *= scale_y\n\n        camera_matrix = np.array([\n            [fx, 0.0, cx],\n            [0.0, fy, cy],\n            [0.0, 0.0, 1.0],\n        ], dtype=np.float64)\n''',
)
patch(
    'backend/app/core/cv/calibration.py',
    '''        if pipe_diameter_mm <= 0.0 or outer_radius_px <= 0.0:\n            return 1.0, 1.0\n''',
    '''        if pipe_diameter_mm <= 0.0 or outer_radius_px <= 0.0:\n            raise ValueError("Calibration scale requires positive pipe diameter and measured radius.")\n''',
)
patch(
    'backend/app/api/v1/endpoints/calibration.py',
    '    return list(camera_calibrator._profiles.values())\n',
    '    return camera_calibrator.list_profiles()\n',
)

# ONNX provider selection and output parsing are fail-closed and derived from the
# actual model metadata rather than assuming CUDA exists or every model is 640.
patch(
    'backend/app/core/cv/ai/joint_segmenter.py',
    '''                self._session = ort.InferenceSession(\n                    str(info.weights_path),\n                    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],\n                )\n''',
    '''                available = set(ort.get_available_providers())\n                providers = [\n                    provider\n                    for provider in ("CUDAExecutionProvider", "CPUExecutionProvider")\n                    if provider in available\n                ]\n                if not providers:\n                    self._session = None\n                    return\n                self._session = ort.InferenceSession(\n                    str(info.weights_path),\n                    providers=providers,\n                )\n''',
)
patch(
    'backend/app/core/cv/ai/joint_segmenter.py',
    '''                # Preprocess: resize to model input size (e.g. 640x640), normalize\n                blob = cv2.resize(image_bgr, (640, 640))\n                blob = blob.astype(np.float32) / 255.0\n                blob = np.transpose(blob, (2, 0, 1))[np.newaxis, :]  # NCHW\n\n                input_name = self._session.get_inputs()[0].name\n                outputs = self._session.run(None, {input_name: blob})\n\n                # Parse detection confidence and mask from model outputs\n                conf = float(outputs[0][0])\n''',
    '''                model_input = self._session.get_inputs()[0]\n                input_shape = list(model_input.shape)\n                if len(input_shape) != 4:\n                    raise ValueError(f"Unsupported segmenter input rank: {input_shape}")\n                channels = input_shape[1]\n                if isinstance(channels, int) and channels != 3:\n                    raise ValueError(f"Expected NCHW 3-channel input, got shape {input_shape}")\n\n                target_h = input_shape[2] if isinstance(input_shape[2], int) and input_shape[2] > 0 else 640\n                target_w = input_shape[3] if isinstance(input_shape[3], int) and input_shape[3] > 0 else 640\n\n                blob = cv2.resize(image_bgr, (target_w, target_h))\n                blob = blob.astype(np.float32) / 255.0\n                blob = np.transpose(blob, (2, 0, 1))[np.newaxis, :]  # NCHW\n\n                outputs = self._session.run(None, {model_input.name: blob})\n                if len(outputs) < 2:\n                    raise ValueError(f"Segmenter must return confidence and mask outputs; got {len(outputs)} output(s).")\n\n                conf_array = np.asarray(outputs[0], dtype=np.float32).squeeze()\n                if conf_array.size != 1 or not np.isfinite(conf_array).all():\n                    raise ValueError(f"Invalid segmenter confidence output shape: {np.asarray(outputs[0]).shape}")\n                conf = float(conf_array.reshape(-1)[0])\n                if not 0.0 <= conf <= 1.0:\n                    raise ValueError(f"Segmenter confidence outside [0, 1]: {conf}")\n''',
)
patch(
    'backend/app/core/cv/ai/joint_segmenter.py',
    '''                raw_mask = outputs[1][0]  # Expected 640x640 probability map\n                mask = cv2.resize((raw_mask > 0.5).astype(np.uint8) * 255, (w, h))\n''',
    '''                raw_mask = np.asarray(outputs[1], dtype=np.float32).squeeze()\n                if raw_mask.ndim != 2 or raw_mask.size == 0:\n                    raise ValueError(f"Invalid segmenter mask output shape: {np.asarray(outputs[1]).shape}")\n                if not np.isfinite(raw_mask).all():\n                    raise ValueError("Segmenter mask output contains non-finite values.")\n                if float(raw_mask.min()) < 0.0 or float(raw_mask.max()) > 1.0:\n                    raise ValueError("Segmenter mask output must be a probability map in [0, 1].")\n                mask = cv2.resize((raw_mask > 0.5).astype(np.uint8) * 255, (w, h))\n''',
)

write('backend/tests/test_cv_runtime_contracts.py', '''
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
''')

print('PR5 CV runtime contract hardening applied')
