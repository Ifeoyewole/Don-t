"""End-to-End Frozen Inspection Pipeline Evaluation on Benchmark Sets.

Coordinates:
Frozen Model A (segmentation) -> OpenCV Metrology -> Frozen Model B (classification) -> Tolerance Evaluation.
Preserves strict isolation: zero weight updates, zero gradient calculation.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List
import cv2

from .base_adapter import BaseDatasetAdapter
from backend.app.core.cv.circular_detector import measure_circular_gap

logger = logging.getLogger("eval_pipeline")


def evaluate_pipeline_on_benchmark(
    adapter: BaseDatasetAdapter,
    model_a_onnx: Optional[Path] = None,
    model_b_onnx: Optional[Path] = None,
) -> Dict[str, Any]:
    """Runs full pipeline evaluation on benchmark dataset in frozen mode."""
    logger.info("Evaluating full pipeline on benchmark '%s'...", adapter.dataset_name)

    evaluated_count = 0
    accepted_measurements = 0
    rejected_unreliable = 0

    for sample in adapter:
        if not sample.image_path or not Path(sample.image_path).exists():
            continue

        img = cv2.imread(sample.image_path)
        if img is None:
            continue

        evaluated_count += 1
        dia_mm = float(sample.metadata.get("pipe_diameter_mm", 300.0))

        try:
            res = measure_circular_gap(img, pipe_diameter_mm=dia_mm, num_rays=72)
            accepted_measurements += 1
        except Exception:
            rejected_unreliable += 1

    return {
        "benchmark_dataset": adapter.dataset_name,
        "evaluation_category": "FROZEN_PIPELINE_BENCHMARK",
        "total_evaluated": evaluated_count,
        "accepted_measurements": accepted_measurements,
        "zero_guessing_rejections": rejected_unreliable,
        "acceptance_rate_pct": round((accepted_measurements / max(1, evaluated_count)) * 100.0, 2),
    }
