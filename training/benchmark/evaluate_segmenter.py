"""Benchmark Evaluator for Frozen Model A (Segmenter).

Enforces Strict Benchmark Isolation:
- Loads frozen ONNX model into read-only ONNX Runtime InferenceSession
- Disables all gradient tracking and optimizer updates
- Evaluates purely forward pass predictions against benchmark ground truth
- Never modifies weights, never saves checkpoints, never trains
"""

import logging
from pathlib import Path
from typing import Any, Dict, List
import cv2
import numpy as np

from .base_adapter import BaseDatasetAdapter

logger = logging.getLogger("eval_segmenter")


def evaluate_segmenter_on_benchmark(
    model_onnx_path: Path,
    adapter: BaseDatasetAdapter,
) -> Dict[str, Any]:
    """Runs forward-only inference of frozen Model A on benchmark samples."""
    import onnxruntime as ort

    logger.info("Initializing read-only frozen ONNX session for %s", model_onnx_path)
    session = ort.InferenceSession(str(model_onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape  # e.g. [1, 3, H, W]
    target_h = input_shape[2] if len(input_shape) >= 4 and isinstance(input_shape[2], int) else 270
    target_w = input_shape[3] if len(input_shape) >= 4 and isinstance(input_shape[3], int) else 480

    ious, dices = [], []

    for sample in adapter:
        if not sample.image_path or not Path(sample.image_path).exists():
            continue

        img = cv2.imread(sample.image_path)
        if img is None:
            continue

        # Preprocess
        img_res = cv2.resize(img, (target_w, target_h)) / 255.0
        x = np.transpose(img_res, (2, 0, 1))[None, ...].astype(np.float32)

        # Forward-only prediction (Zero gradients)
        preds = session.run(None, {input_name: x})[0]
        pred_bin = (preds[0, 0] >= 0.5).astype(bool)

        if sample.mask_path and Path(sample.mask_path).exists():
            gt_mask = cv2.imread(sample.mask_path, cv2.IMREAD_GRAYSCALE)
            if gt_mask is not None:
                gt_bin = (cv2.resize(gt_mask, (target_w, target_h)) > 127).astype(bool)
                inter = np.logical_and(pred_bin, gt_bin).sum()
                union = np.logical_or(pred_bin, gt_bin).sum()
                iou = float(inter / union) if union > 0 else 1.0
                dice = float(2.0 * inter / (pred_bin.sum() + gt_bin.sum())) if (pred_bin.sum() + gt_bin.sum()) > 0 else 1.0
                ious.append(iou)
                dices.append(dice)

    m_iou = float(np.mean(ious)) if ious else 0.0
    m_dice = float(np.mean(dices)) if dices else 0.0

    return {
        "benchmark_dataset": adapter.dataset_name,
        "model_evaluated": model_onnx_path.name,
        "evaluation_mode": "FROZEN_MODEL_INFERENCE_ONLY",
        "samples_evaluated": len(adapter),
        "mean_iou": round(m_iou, 4),
        "dice_score": round(m_dice, 4),
    }
