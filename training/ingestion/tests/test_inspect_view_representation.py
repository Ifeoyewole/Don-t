import pytest

torch = pytest.importorskip("torch")

from training.inspect_view_representation import macro_metrics, stable_cap


def test_stable_cap_is_order_independent():
    rows = [{"sha256": value * 64} for value in "abc"]
    assert stable_cap(rows, 2) == stable_cap(list(reversed(rows)), 2)


def test_macro_metrics_perfect_predictions():
    truth = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    logits = torch.tensor([[10.0, -10.0], [-10.0, 10.0]])
    result = macro_metrics(truth, logits)
    assert result["macro_f1"] == 1.0
    assert result["macro_f2"] == 1.0
