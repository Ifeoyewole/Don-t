import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "sewer_ml_pipeline"))
from benchmark_integrity import audit_split_leakage, calibration_report, compare_same_input_predictions, grouped_binary_metrics, optimize_thresholds


def test_grouped_metrics_use_or_predictions_and_real_counts():
    truth = np.array([[1, 0], [0, 1], [0, 0], [0, 0]])
    pred = np.array([[1, 0], [0, 0], [0, 1], [0, 0]])
    result = grouped_binary_metrics(truth, pred, [0, 1])
    assert result == pytest.approx({"tp": 1, "fp": 1, "fn": 1, "tn": 1, "precision": .5, "recall": .5, "f1": .5, "f2": .5})


def test_calibration_compares_probability_to_positive_frequency():
    truth = np.array([[0], [0], [1], [1]])
    probability = np.array([[0.1], [0.1], [0.9], [0.9]])
    report = calibration_report(truth, probability, bins=2)
    assert report["ece_macro"] == pytest.approx(0.1)
    assert report["brier_score"] == pytest.approx(0.01)
    assert sum(row["count"] for row in report["per_class"][0]["bins"]) == 4


def test_thresholds_are_fitted_per_class():
    truth = np.array([[0, 0], [1, 0], [1, 1]])
    probability = np.array([[.2, .1], [.4, .2], [.6, .3]])
    assert optimize_thresholds(truth, probability, [.25, .5]) == [.25, .25]


def test_calibration_rejects_invalid_probabilities():
    with pytest.raises(ValueError):
        calibration_report(np.array([[1]]), np.array([[1.2]]))


def test_split_audit_detects_filename_and_source_group_leakage():
    report = audit_split_leakage({
        "train": [{"Filename": "A.png", "video_id": "v1"}],
        "test": [{"Filename": "a.PNG", "video_id": "v2"}],
        "validation": [{"Filename": "b.png", "video_id": "v1"}],
    })
    assert report["leakage_detected"] is True
    assert len(report["manifest_sha256"]) == 64
    assert len(report["overlaps"]) == 2


def test_head_to_head_requires_identical_ordered_shapes():
    truth = np.array([[1, 0], [0, 1]])
    report = compare_same_input_predictions(truth, {"wrc": truth, "v2": np.array([[1, 0], [0, 0]])}, {"ANY_DEFECT": [0, 1]})
    assert report["sample_count"] == 2
    assert report["models"]["wrc"]["ANY_DEFECT"]["f1"] == 1.0
    with pytest.raises(ValueError):
        compare_same_input_predictions(truth, {"bad": np.array([[1, 0]])}, {"ANY_DEFECT": [0, 1]})
