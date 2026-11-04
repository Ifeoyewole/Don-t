import pytest

torch = pytest.importorskip("torch")

from training.inspect_view_representation import (
    balanced_cap, macro_metrics, partition_validation, stable_cap, tune_thresholds,
)


def test_stable_cap_is_order_independent():
    rows = [{"sha256": value * 64} for value in "abc"]
    assert stable_cap(rows, 2) == stable_cap(list(reversed(rows)), 2)


def test_macro_metrics_perfect_predictions():
    truth = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    logits = torch.tensor([[10.0, -10.0], [-10.0, 10.0]])
    result = macro_metrics(truth, logits)
    assert result["macro_f1"] == 1.0
    assert result["macro_f2"] == 1.0


def test_balanced_cap_includes_rare_label():
    rows = [
        {"sha256": f"{index:064x}", "jointinspect_labels": ["COMMON"]}
        for index in range(5)
    ]
    rows.append({"sha256": "f" * 64, "jointinspect_labels": ["RARE"]})
    selected = balanced_cap(rows, 2)
    assert {label for row in selected for label in row["jointinspect_labels"]} == {"COMMON", "RARE"}


def test_partition_validation_keeps_families_together():
    rows = []
    for family in range(20):
        for frame in range(2):
            rows.append({"dataset_name": "d", "media_family_id": str(family), "frame": frame})
    tune, report = partition_validation(rows)
    tune_families = {row["media_family_id"] for row in tune}
    report_families = {row["media_family_id"] for row in report}
    assert tune_families.isdisjoint(report_families)


def test_tuned_thresholds_are_applied_to_per_class_report():
    truth = torch.tensor([[1.0], [0.0]])
    logits = torch.tensor([[-1.0], [-3.0]])
    thresholds = tune_thresholds(truth, logits)
    result = macro_metrics(truth, logits, thresholds, ["OPEN_JOINT"])
    assert result["macro_f1"] == 1.0
    assert result["per_class"]["OPEN_JOINT"]["threshold"] == thresholds[0]


def test_unobserved_targets_do_not_count_as_positive_or_negative():
    truth = torch.tensor([[1.0], [0.0], [-1.0]])
    logits = torch.tensor([[10.0], [-10.0], [10.0]])
    report = macro_metrics(truth, logits)
    assert report['macro_f1'] == 1.0
    assert report['per_class']['0']['false_positive'] == 0


def test_missing_positive_support_retains_default_threshold():
    assert tune_thresholds(torch.tensor([[-1.0], [0.0]]), torch.tensor([[10.0], [-10.0]])) == [0.5]
