"""Benchmark Evaluator for Frozen Model B (Classifier).

Evaluates frozen classification models on external benchmark datasets.
Strict isolation: zero weight updates, zero gradient calculation, forward pass only.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List
import cv2
import numpy as np

from .base_adapter import BaseDatasetAdapter

logger = logging.getLogger("eval_classifier")

CLASS_NAMES = [
    "NORMAL_JOINT",
    "DISPLACED_JOINT",
    "DAMAGED_JOINT",
    "INTRUDING_SEAL",
    "DEPOSITS_OBSTACLES",
    "DIFFICULT_CONDITION",
]
CLASS_MAP = {c: i for i, c in enumerate(CLASS_NAMES)}


def evaluate_classifier_on_benchmark(
    model_onnx_path: Path,
    adapter: BaseDatasetAdapter,
) -> Dict[str, Any]:
    """Runs forward-only inference of frozen Model B on benchmark samples."""
    import onnxruntime as ort

    logger.info("Initializing read-only frozen ONNX session for %s", model_onnx_path)
    session = ort.InferenceSession(str(model_onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    img_size = input_shape[2] if len(input_shape) >= 4 and isinstance(input_shape[2], int) else 128

    y_true, y_pred = [], []

    for sample in adapter:
        if not sample.image_path or not Path(sample.image_path).exists():
            continue

        img = cv2.imread(sample.image_path)
        if img is None:
            continue

        label_str = (sample.condition_label or "NORMAL_JOINT").upper()
        if label_str == "OPEN_JOINT":
            label_str = "NORMAL_JOINT"
        true_idx = CLASS_MAP.get(label_str, 0)

        img_res = cv2.resize(img, (img_size, img_size)) / 255.0
        x = np.transpose(img_res, (2, 0, 1))[None, ...].astype(np.float32)

        # Forward-only prediction (Zero gradients)
        probs = session.run(None, {input_name: x})[0][0]
        pred_idx = int(np.argmax(probs))

        y_true.append(true_idx)
        y_pred.append(pred_idx)

    acc = float(np.mean(np.array(y_true) == np.array(y_pred))) if y_true else 0.0

    return {
        "benchmark_dataset": adapter.dataset_name,
        "model_evaluated": model_onnx_path.name,
        "evaluation_mode": "FROZEN_MODEL_INFERENCE_ONLY",
        "samples_evaluated": len(y_true),
        "accuracy": round(acc, 4),
    }
