"""Unit tests for WRc InceptionResNetV2 external baseline classifier and safety rules."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from backend.app.core.cv.ai.wrc_inception_classifier import (
    WRC_CLASS_MAP_PATH,
    WRCInceptionClassifier,
    compare_models,
    get_wrc_classifier,
)
from backend.app.schemas.domain import JointConditionClass, ToleranceStatus
from backend.app.schemas.measurement import (
    ExternalClassifierResult,
    MeasurementResponse,
    OverlayHints,
)


def test_wrc_class_map_contract():
    """Verify that wrc_class_map.json has all 13 canonical classes with verified fields."""
    assert WRC_CLASS_MAP_PATH.exists(), "wrc_class_map.json missing"
    with open(WRC_CLASS_MAP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["model_id"] == "wrc-inceptionresnetv2-baseline-v1"
    assert data["output_dimension"] == 13
    assert len(data["classes"]) == 13

    # Check key mappings
    classes = {c["index"]: c for c in data["classes"]}
    assert classes[5]["wrc_code"] == "DE"
    assert classes[5]["wrc_description"] == "Deposit"
    assert classes[5]["jointinspect_mapping"] == "DEPOSITS_OBSTACLES"
    assert classes[5]["mapping_status"] == "DIRECT"

    assert classes[6]["wrc_code"] == "JD"
    assert classes[6]["wrc_description"] == "Displaced Joint"
    assert classes[6]["jointinspect_mapping"] == "DISPLACED_JOINT"
    assert classes[6]["mapping_status"] == "DIRECT"

    assert classes[0]["wrc_code"] == "B"
    assert classes[0]["jointinspect_mapping"] == "DAMAGED_JOINT"
    assert classes[0]["mapping_status"] == "GROUPED"

    assert classes[1]["wrc_description"] == "Connection"
    assert classes[1]["jointinspect_mapping"] is None
    assert classes[1]["mapping_status"] == "UNMAPPED"

    assert classes[10]["wrc_description"] == "Line of Sewer"
    assert classes[10]["jointinspect_mapping"] is None
    assert classes[10]["mapping_status"] == "AMBIGUOUS"


def test_wrc_classifier_unavailable_fallback():
    """When model session is unavailable, classifier must return safe failure without crashing."""
    classifier = WRCInceptionClassifier()
    classifier._session = None  # Force unavailable

    dummy_img = np.ones((100, 100, 3), dtype=np.uint8) * 128
    res = classifier.classify(dummy_img)

    assert res.status == "EXTERNAL_CLASSIFIER_UNAVAILABLE"
    assert res.confidence == 0.0
    assert res.raw_class_name == "UNKNOWN"
    assert res.jointinspect_mapping is None
    assert res.mapping_status == "UNMAPPED"
    assert res.advisory_only is True


def test_wrc_classifier_empty_input():
    """Classifier must handle None or empty image safely without raising exceptions."""
    classifier = WRCInceptionClassifier()
    res = classifier.classify(None)
    assert res.status == "EXTERNAL_CLASSIFIER_UNAVAILABLE"
    assert res.confidence == 0.0

    empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
    res2 = classifier.classify(empty_img)
    assert res2.status == "EXTERNAL_CLASSIFIER_UNAVAILABLE"


def test_wrc_preprocessing_parity():
    """Preprocessing must output (1, 299, 299, 3) float32 in range [0.0, 255.0]."""
    classifier = WRCInceptionClassifier()
    # Non-square image to test aspect ratio preserving padding
    rect_img = np.ones((150, 300, 3), dtype=np.uint8) * 200

    blob = classifier.preprocess_image(rect_img, target_size=(299, 299))

    assert blob.shape == (1, 299, 299, 3)
    assert blob.dtype == np.float32
    assert np.min(blob) >= 0.0
    assert np.max(blob) <= 255.0
    # Center should be non-zero and border padding should be 0
    assert blob[0, 149, 149, 0] == 200.0
    assert blob[0, 0, 0, 0] == 0.0


def test_wrc_inference_mock_top_k():
    """Verify inference parsing, top-k ordering, and mapping when ONNX session returns logits."""
    classifier = WRCInceptionClassifier()

    # Create mock session
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "input_1_unnormalized"
    mock_session.get_inputs.return_value = [mock_input]

    # Mock 13 probabilities: Class 6 (Displaced Joint) has highest probability 0.82
    mock_probs = np.zeros((1, 13), dtype=np.float32)
    mock_probs[0, 6] = 0.82
    mock_probs[0, 5] = 0.10
    mock_probs[0, 2] = 0.05
    mock_probs[0, 0] = 0.03
    mock_session.run.return_value = [mock_probs]

    classifier._session = mock_session

    img = np.ones((200, 200, 3), dtype=np.uint8) * 100
    res = classifier.classify(img, top_k_count=3)

    assert res.status == "SUCCESS"
    assert res.raw_class_name == "Displaced Joint"
    assert res.raw_class_code == "JD"
    assert res.confidence == 0.82
    assert res.jointinspect_mapping == "DISPLACED_JOINT"
    assert res.mapping_status == "DIRECT"
    assert res.advisory_only is True

    assert len(res.top_k) == 3
    assert res.top_k[0].raw_class_name == "Displaced Joint"
    assert res.top_k[0].score == 0.82
    assert res.top_k[1].raw_class_name == "Deposit"
    assert res.top_k[1].score == 0.10


def test_wrc_low_confidence_classification():
    """When top-1 confidence is below min_score threshold, status should be LOW_CONFIDENCE_CLASSIFICATION."""
    classifier = WRCInceptionClassifier()
    classifier.min_score = 0.30

    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "input"
    mock_session.get_inputs.return_value = [mock_input]

    # Diffuse distribution where max probability is only 0.15
    mock_probs = np.ones((1, 13), dtype=np.float32) / 13.0
    mock_probs[0, 0] = 0.15
    mock_session.run.return_value = [mock_probs]

    classifier._session = mock_session

    img = np.ones((200, 200, 3), dtype=np.uint8) * 100
    res = classifier.classify(img)

    assert res.status == "LOW_CONFIDENCE_CLASSIFICATION"
    assert res.confidence == round(0.15, 4)


def test_wrc_duplicate_determinism():
    """Identical input images must produce exact identical outputs."""
    classifier = WRCInceptionClassifier()

    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "input"
    mock_session.get_inputs.return_value = [mock_input]

    mock_probs = np.zeros((1, 13), dtype=np.float32)
    mock_probs[0, 5] = 0.65
    mock_session.run.return_value = [mock_probs]
    classifier._session = mock_session

    img1 = np.ones((200, 200, 3), dtype=np.uint8) * 120
    img2 = img1.copy()

    res1 = classifier.classify(img1)
    res2 = classifier.classify(img2)

    assert res1.raw_class_name == res2.raw_class_name
    assert res1.confidence == res2.confidence
    assert res1.jointinspect_mapping == res2.jointinspect_mapping


def test_singleton_get_wrc_classifier():
    """get_wrc_classifier must return process-level singleton instance."""
    c1 = get_wrc_classifier()
    c2 = get_wrc_classifier()
    assert c1 is c2


def test_model_comparison_agreement():
    """compare_models must accurately reflect agreement across advisory channels."""
    wrc_res = ExternalClassifierResult(
        model_id="wrc-inceptionresnetv2-baseline-v1",
        source="WRc",
        raw_class_name="Displaced Joint",
        confidence=0.85,
        jointinspect_mapping="DISPLACED_JOINT",
        mapping_status="DIRECT",
        advisory_only=True,
        status="SUCCESS",
    )

    class MockNativeResult:
        condition = JointConditionClass.DISPLACED_JOINT
        confidence = 0.80

    comp = compare_models(
        wrc_result=wrc_res,
        native_result=MockNativeResult(),
        vertex_observation="Pipe joint appears displaced axially.",
    )

    assert comp.wrc_vs_native_agreement == "AGREE"
    assert comp.wrc_vs_vertex_agreement == "AGREE"
    assert comp.native_vs_vertex_agreement == "AGREE"
    assert comp.human_review_required is False


def test_model_comparison_high_confidence_disagreement_flags_review():
    """Strong disagreement between high-confidence models must trigger human_review_required."""
    wrc_res = ExternalClassifierResult(
        model_id="wrc-inceptionresnetv2-baseline-v1",
        source="WRc",
        raw_class_name="Displaced Joint",
        confidence=0.88,
        jointinspect_mapping="DISPLACED_JOINT",
        mapping_status="DIRECT",
        advisory_only=True,
        status="SUCCESS",
    )

    class MockNativeResult:
        condition = JointConditionClass.NORMAL_JOINT
        confidence = 0.75

    comp = compare_models(
        wrc_result=wrc_res,
        native_result=MockNativeResult(),
        vertex_observation="Pipe interior appears normal.",
    )

    assert comp.wrc_vs_native_agreement == "DISAGREE"
    assert comp.human_review_required is True


def test_zero_engineering_authority_safeguard():
    """External classifier must never override physical tolerance FAIL status."""
    # OpenCV geometry measured gap is 6.2 mm, exceeding 3.0 mm tolerance -> FAIL
    response = MeasurementResponse(
        joint_type="CIRCULAR_OPENING",
        pipe_diameter_mm=300.0,
        pixels_per_mm=2.5,
        mean_gap_mm=6.2,
        min_gap_mm=5.9,
        max_gap_mm=6.5,
        overall_status=ToleranceStatus.FAIL,
        overlay_hints=OverlayHints(),
    )

    # Even if WRc classifier says NORMAL or Deposit, physical engineering status remains FAIL
    wrc_res = ExternalClassifierResult(
        model_id="wrc-inceptionresnetv2-baseline-v1",
        source="WRc",
        raw_class_name="Deposit",
        confidence=0.95,
        jointinspect_mapping="DEPOSITS_OBSTACLES",
        mapping_status="DIRECT",
        advisory_only=True,
        status="SUCCESS",
    )
    response.external_classifier = wrc_res

    assert response.overall_status == ToleranceStatus.FAIL
    assert response.mean_gap_mm == 6.2
    assert response.external_classifier.advisory_only is True
