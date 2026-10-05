"""Physical Measurement Accuracy and Confidence Calibration Evaluation Engine.

Evaluates computer-vision gap measurements against ground-truth physical specimens (calipers/feelers).
Computes:
- Mean Absolute Error (MAE) in mm
- Root Mean Squared Error (RMSE) in mm
- Maximum absolute error in mm
- Systematic measurement bias in mm
- 95% error confidence interval
- Empirical bad-measurement risk calibration curves (mapping confidence thresholds to error rates)
"""

from typing import Dict, List, Tuple
import numpy as np
from pydantic import BaseModel, Field


class MeasurementAccuracyReport(BaseModel):
    """Detailed statistical accuracy evaluation against ground truth."""
    total_samples: int
    mae_mm: float = Field(..., description="Mean Absolute Error in millimeters")
    rmse_mm: float = Field(..., description="Root Mean Squared Error in millimeters")
    max_error_mm: float = Field(..., description="Maximum absolute error in millimeters")
    systematic_bias_mm: float = Field(..., description="Average signed deviation (measured - ground truth)")
    std_error_mm: float = Field(..., description="Standard deviation of measurement error")
    error_interval_95_mm: float = Field(..., description="95% error interval (+/- 1.96 * std)")
    within_1mm_ratio: float = Field(..., description="Fraction of measurements within +/- 1.0 mm")
    within_2mm_ratio: float = Field(..., description="Fraction of measurements within +/- 2.0 mm")
    calibrated_risk_curve: Dict[str, float] = Field(
        default_factory=dict,
        description="Empirical bad-measurement rate (> 2.0 mm error) per confidence bin",
    )


def evaluate_physical_measurements(
    ground_truth_mm: List[float],
    measured_mm: List[float],
    confidence_scores: List[float],
    bad_measurement_error_threshold_mm: float = 2.0,
) -> MeasurementAccuracyReport:
    """Compute physical measurement accuracy metrics and empirical calibration curve.

    Args:
        ground_truth_mm: Calibrated ground-truth measurements (caliper / precision gauge).
        measured_mm: Output measurements from AI/CV engine.
        confidence_scores: Overall fused confidence score for each measurement.
        bad_measurement_error_threshold_mm: Error boundary defining a 'bad' measurement.

    Returns:
        MeasurementAccuracyReport: Statistical precision, bias, and calibrated risk curve.
    """
    gt = np.array(ground_truth_mm, dtype=np.float64)
    pred = np.array(measured_mm, dtype=np.float64)
    confs = np.array(confidence_scores, dtype=np.float64)

    errors = pred - gt
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    max_err = float(np.max(abs_errors))
    bias = float(np.mean(errors))
    std_err = float(np.std(errors))
    interval_95 = float(1.96 * std_err)

    within_1mm = float(np.mean(abs_errors <= 1.0))
    within_2mm = float(np.mean(abs_errors <= 2.0))

    # Empirical Risk Curve Calculation:
    # For confidence cutoffs, what fraction of accepted measurements had error > threshold?
    risk_curve: Dict[str, float] = {}
    cutoffs = [0.60, 0.70, 0.80, 0.88, 0.90, 0.93, 0.95]

    for c in cutoffs:
        mask = confs >= c
        if np.any(mask):
            accepted_abs_errors = abs_errors[mask]
            bad_rate = float(np.mean(accepted_abs_errors > bad_measurement_error_threshold_mm))
            risk_curve[f">={c:.2f}"] = round(bad_rate * 100.0, 2)
        else:
            risk_curve[f">={c:.2f}"] = 0.0

    return MeasurementAccuracyReport(
        total_samples=len(gt),
        mae_mm=round(mae, 3),
        rmse_mm=round(rmse, 3),
        max_error_mm=round(max_err, 3),
        systematic_bias_mm=round(bias, 3),
        std_error_mm=round(std_err, 3),
        error_interval_95_mm=round(interval_95, 3),
        within_1mm_ratio=round(within_1mm, 3),
        within_2mm_ratio=round(within_2mm, 3),
        calibrated_risk_curve=risk_curve,
    )
