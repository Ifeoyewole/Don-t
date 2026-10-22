"""Evaluation and artifact integrity primitives for Sewer-ML candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


def binary_counts(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    truth = np.asarray(y_true, dtype=bool)
    pred = np.asarray(y_pred, dtype=bool)
    if truth.shape != pred.shape:
        raise ValueError("Ground truth and predictions must have identical shapes")
    return {
        "tp": int(np.logical_and(truth, pred).sum()),
        "fp": int(np.logical_and(~truth, pred).sum()),
        "fn": int(np.logical_and(truth, ~pred).sum()),
        "tn": int(np.logical_and(~truth, ~pred).sum()),
    }


def metrics_from_counts(counts: dict[str, int]) -> dict[str, float | int]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    f2 = 5 * precision * recall / (4 * precision + recall) if 4 * precision + recall else 0.0
    return {**counts, "precision": precision, "recall": recall, "f1": f1, "f2": f2}


def grouped_binary_metrics(y_true: np.ndarray, y_pred: np.ndarray, indices: Sequence[int]) -> dict[str, float | int]:
    if not indices:
        raise ValueError("At least one verified label index is required")
    grouped_true = np.asarray(y_true)[:, indices].astype(bool).any(axis=1)
    grouped_pred = np.asarray(y_pred)[:, indices].astype(bool).any(axis=1)
    return metrics_from_counts(binary_counts(grouped_true, grouped_pred))


def calibration_report(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 10) -> dict[str, Any]:
    truth = np.asarray(y_true, dtype=float)
    prob = np.asarray(y_prob, dtype=float)
    if truth.shape != prob.shape or truth.ndim != 2:
        raise ValueError("Calibration inputs must be equally shaped [samples, classes] arrays")
    if not np.isfinite(prob).all() or ((prob < 0) | (prob > 1)).any():
        raise ValueError("Probabilities must be finite and within [0, 1]")

    boundaries = np.linspace(0.0, 1.0, bins + 1)
    per_class, class_eces = [], []
    for class_index in range(prob.shape[1]):
        rows, ece = [], 0.0
        for index, (low, high) in enumerate(zip(boundaries[:-1], boundaries[1:])):
            mask = (prob[:, class_index] >= low) & ((prob[:, class_index] < high) if index < bins - 1 else (prob[:, class_index] <= high))
            count = int(mask.sum())
            mean_confidence = float(prob[mask, class_index].mean()) if count else None
            positive_frequency = float(truth[mask, class_index].mean()) if count else None
            if count:
                ece += (count / prob.shape[0]) * abs(mean_confidence - positive_frequency)
            rows.append({"lower": float(low), "upper": float(high), "count": count, "mean_probability": mean_confidence, "positive_frequency": positive_frequency})
        class_eces.append(ece)
        per_class.append({"class_index": class_index, "ece": ece, "bins": rows})
    epsilon = 1e-7
    clipped = np.clip(prob, epsilon, 1 - epsilon)
    return {
        "method": "equal-width probability bins; confidence compared with empirical positive frequency",
        "ece_macro": float(np.mean(class_eces)),
        "brier_score": float(np.mean((prob - truth) ** 2)),
        "log_loss": float(-np.mean(truth * np.log(clipped) + (1 - truth) * np.log(1 - clipped))),
        "per_class": per_class,
    }


def optimize_thresholds(y_true: np.ndarray, y_prob: np.ndarray, grid: Iterable[float] | None = None) -> list[float]:
    candidates = list(grid or np.arange(0.1, 0.91, 0.05))
    thresholds: list[float] = []
    for index in range(y_true.shape[1]):
        scored = [(metrics_from_counts(binary_counts(y_true[:, index], y_prob[:, index] >= threshold))["f1"], threshold) for threshold in candidates]
        thresholds.append(float(max(scored, key=lambda item: (item[0], item[1]))[1]))
    return thresholds


def validate_onnx_artifact(model_path: Path, native_outputs: np.ndarray, sample_inputs: np.ndarray, tolerance: float = 1e-4) -> dict[str, Any]:
    import onnx
    import onnxruntime as ort

    graph = onnx.load(str(model_path))
    onnx.checker.check_model(graph)
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    outputs = session.run(None, {session.get_inputs()[0].name: sample_inputs.astype(np.float32)})[0]
    if not np.isfinite(outputs).all():
        raise ValueError("ONNX produced non-finite outputs")
    max_abs_error = float(np.max(np.abs(outputs - native_outputs)))
    if max_abs_error > tolerance:
        raise ValueError(f"PyTorch/ONNX parity failed: {max_abs_error} > {tolerance}")
    return {"sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(), "max_abs_error": max_abs_error, "runtime": "onnxruntime-cpu"}


def audit_split_leakage(splits: dict[str, Sequence[dict[str, Any]]]) -> dict[str, Any]:
    """Finds filename/source-group overlap and emits a deterministic manifest digest."""
    normalized: dict[str, set[str]] = {}
    source_groups: dict[str, set[str]] = {}
    manifest_rows = []
    for split, rows in sorted(splits.items()):
        normalized[split] = set()
        source_groups[split] = set()
        for row in rows:
            filename = str(row.get("Filename", "")).strip().casefold()
            group = str(row.get("source_group") or row.get("video_id") or row.get("archive") or "").strip().casefold()
            if filename:
                normalized[split].add(filename)
            if group:
                source_groups[split].add(group)
            manifest_rows.append({"split": split, "filename": filename, "source_group": group})
    overlaps = []
    names = sorted(normalized)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            duplicate_names = sorted(normalized[left] & normalized[right])
            duplicate_groups = sorted(source_groups[left] & source_groups[right])
            if duplicate_names or duplicate_groups:
                overlaps.append({"left": left, "right": right, "filenames": duplicate_names, "source_groups": duplicate_groups})
    payload = json.dumps(manifest_rows, sort_keys=True, separators=(",", ":")).encode()
    return {"manifest_sha256": hashlib.sha256(payload).hexdigest(), "split_counts": {name: len(rows) for name, rows in splits.items()}, "overlaps": overlaps, "leakage_detected": bool(overlaps)}


def compare_same_input_predictions(
    ground_truth: np.ndarray,
    predictions: dict[str, np.ndarray],
    concept_indices: dict[str, Sequence[int]],
) -> dict[str, Any]:
    """Evaluates precomputed model decisions on one ordered image manifest."""
    truth = np.asarray(ground_truth)
    report: dict[str, Any] = {"sample_count": int(truth.shape[0]), "models": {}}
    for model_name, model_predictions in predictions.items():
        pred = np.asarray(model_predictions)
        if pred.shape != truth.shape:
            raise ValueError(f"{model_name} predictions do not match the common ground-truth shape")
        report["models"][model_name] = {
            concept: grouped_binary_metrics(truth, pred, indices)
            for concept, indices in concept_indices.items()
        }
    return report
