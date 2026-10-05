"""Segmentation and Condition Classification Evaluation Engine.

Computes:
- Intersection over Union (IoU) for joint boundary segmentation masks
- Precision, Recall, and F1-Score
- mAP50 and mAP50-95
- Confusion matrix and per-class metrics for defect classification
"""

from typing import Dict, List, Tuple
import numpy as np
from pydantic import BaseModel, Field


class DetectionEvaluationReport(BaseModel):
    """Metrics for AI joint segmentation and classification models."""
    mean_iou: float = Field(..., description="Mean Intersection-over-Union across test set")
    precision: float = Field(..., description="Macro-averaged precision")
    recall: float = Field(..., description="Macro-averaged recall")
    f1_score: float = Field(..., description="Harmonic mean of precision and recall")
    map_50: float = Field(..., description="Mean Average Precision at IoU 0.50")
    map_50_95: float = Field(..., description="Mean Average Precision averaged across IoU 0.50 to 0.95")
    condition_accuracy: float = Field(..., description="Overall accuracy across 5 joint condition classes")
    per_class_f1: Dict[str, float] = Field(default_factory=dict, description="F1-score per condition class")


def compute_mask_iou(pred_mask: np.ndarray, gt_mask: np.ndarray) -> float:
    """Compute Intersection over Union between binary masks."""
    pred_bool = pred_mask.astype(bool)
    gt_bool = gt_mask.astype(bool)

    intersection = np.logical_and(pred_bool, gt_bool).sum()
    union = np.logical_or(pred_bool, gt_bool).sum()

    if union == 0:
        return 1.0 if intersection == 0 else 0.0
    return float(intersection / union)


def evaluate_segmentation_batch(
    pred_masks: List[np.ndarray],
    gt_masks: List[np.ndarray],
    pred_conditions: List[str],
    gt_conditions: List[str],
) -> DetectionEvaluationReport:
    """Evaluate batch of segmentation masks and condition predictions."""
    ious = [compute_mask_iou(p, g) for p, g in zip(pred_masks, gt_masks)]
    mean_iou = float(np.mean(ious)) if ious else 0.0

    # mAP approximation across IoU thresholds
    map_50 = float(np.mean([iou >= 0.50 for iou in ious])) if ious else 0.0
    thresholds = np.linspace(0.50, 0.95, 10)
    map_50_95 = float(np.mean([[iou >= t for t in thresholds] for iou in ious])) if ious else 0.0

    # Condition accuracy
    correct_cond = sum(1 for p, g in zip(pred_conditions, gt_conditions) if p == g)
    cond_acc = float(correct_cond / max(1, len(gt_conditions)))

    # Per-class F1
    classes = sorted(list(set(gt_conditions)))
    per_class_f1 = {}
    precisions, recalls = [], []

    for cls in classes:
        tp = sum(1 for p, g in zip(pred_conditions, gt_conditions) if p == cls and g == cls)
        fp = sum(1 for p, g in zip(pred_conditions, gt_conditions) if p == cls and g != cls)
        fn = sum(1 for p, g in zip(pred_conditions, gt_conditions) if p != cls and g == cls)

        p = tp / max(1, tp + fp)
        r = tp / max(1, tp + fn)
        f1 = (2 * p * r) / max(1e-4, p + r)

        per_class_f1[cls] = round(float(f1), 3)
        precisions.append(p)
        recalls.append(r)

    macro_p = float(np.mean(precisions)) if precisions else 0.0
    macro_r = float(np.mean(recalls)) if recalls else 0.0
    macro_f1 = (2 * macro_p * macro_r) / max(1e-4, macro_p + macro_r)

    return DetectionEvaluationReport(
        mean_iou=round(mean_iou, 3),
        precision=round(macro_p, 3),
        recall=round(macro_r, 3),
        f1_score=round(macro_f1, 3),
        map_50=round(map_50, 3),
        map_50_95=round(map_50_95, 3),
        condition_accuracy=round(cond_acc, 3),
        per_class_f1=per_class_f1,
    )
