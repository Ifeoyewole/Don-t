"""Multi-component confidence fusion and calibrated production gating engine."""

from typing import Dict, Optional
from pydantic import BaseModel, Field

from backend.app.schemas.domain import MeasurementResultStatus
from backend.app.schemas.measurement import ConfidenceBreakdown


class ConfidenceWeights(BaseModel):
    """Component weighting for physical measurement confidence calculation."""
    weight_quality: float = Field(default=0.20, description="Weight for image clarity/exposure score")
    weight_segmentation: float = Field(default=0.30, description="Weight for AI joint mask localization confidence")
    weight_geometry: float = Field(default=0.50, description="Weight for sub-pixel OpenCV edge/circle gradient score")
    weight_temporal: float = Field(default=0.15, description="Weight for multi-frame consistency score when present")
    weight_condition: float = Field(default=0.0, description="Defect classification weight (0.0 to prevent contamination of physical measurement)")


class ConfidenceThresholds(BaseModel):
    """Configurable gating thresholds calibrated against empirical error rates."""
    tau_accept: float = Field(default=0.90, description="Threshold above which automated ACCEPTED_MEASUREMENT is issued")
    tau_reject: float = Field(default=0.70, description="Threshold below which REJECTED_UNRELIABLE is issued")


class ConfidenceEngine:
    """Combines independent QA signals and applies calibrated gating logic."""

    def __init__(
        self,
        weights: Optional[ConfidenceWeights] = None,
        thresholds: Optional[ConfidenceThresholds] = None,
    ):
        self.weights = weights or ConfidenceWeights()
        self.thresholds = thresholds or ConfidenceThresholds()

        # Illustrative placeholder risk curve mapping:
        # Note: These values are illustrative engineering placeholders until calibrated against physical ground truth.
        self._placeholder_risk_curve = [
            (0.93, 0.002),  # 0.93+ -> 0.2% bad-measurement rate (placeholder)
            (0.88, 0.007),  # 0.88+ -> 0.7% bad-measurement rate (placeholder)
            (0.80, 0.018),  # 0.80+ -> 1.8% bad-measurement rate (placeholder)
            (0.70, 0.041),  # 0.70+ -> 4.1% bad-measurement rate (placeholder)
            (0.60, 0.082),  # 0.60+ -> 8.2% bad-measurement rate (placeholder)
        ]

    def estimate_placeholder_error_rate(self, confidence: float) -> float:
        """Return illustrative placeholder error rate for a given confidence score."""
        for score_cutoff, risk_rate in self._placeholder_risk_curve:
            if confidence >= score_cutoff:
                return risk_rate
        return 0.15

    def fuse_measurement_confidence(
        self,
        quality_score: float,
        segmentation_score: float,
        geometry_score: float,
        temporal_score: Optional[float] = None,
        condition_score: Optional[float] = None,
    ) -> ConfidenceBreakdown:
        """Compute decoupled physical measurement confidence and decision gating.

        Measurement confidence is derived strictly from:
        - Image quality
        - Model A localization (if available)
        - OpenCV geometry evidence
        - Temporal consistency (if multi-frame)

        Defect classification confidence (WRc) is tracked separately and has ZERO
        authority over physical geometry acceptance or rejection.
        """
        q = min(1.0, max(0.0, quality_score))
        s = min(1.0, max(0.0, segmentation_score))
        g = min(1.0, max(0.0, geometry_score))
        c = min(1.0, max(0.0, condition_score)) if condition_score is not None else 0.0

        if temporal_score is not None:
            t = min(1.0, max(0.0, temporal_score))
            sum_weights = (
                self.weights.weight_quality
                + self.weights.weight_segmentation
                + self.weights.weight_geometry
                + self.weights.weight_temporal
            )
            fused = (
                (self.weights.weight_quality * q)
                + (self.weights.weight_segmentation * s)
                + (self.weights.weight_geometry * g)
                + (self.weights.weight_temporal * t)
            ) / max(1e-4, sum_weights)
        else:
            t = None
            sum_weights = (
                self.weights.weight_quality
                + self.weights.weight_segmentation
                + self.weights.weight_geometry
            )
            fused = (
                (self.weights.weight_quality * q)
                + (self.weights.weight_segmentation * s)
                + (self.weights.weight_geometry * g)
            ) / max(1e-4, sum_weights)

        meas_conf = round(float(min(1.0, max(0.0, fused))), 3)

        # Calibrated decision gating depends strictly on measurement confidence
        if meas_conf >= self.thresholds.tau_accept:
            decision = MeasurementResultStatus.ACCEPTED_MEASUREMENT
        elif meas_conf >= self.thresholds.tau_reject:
            decision = MeasurementResultStatus.REVIEW_REQUIRED
        else:
            decision = MeasurementResultStatus.REJECTED_UNRELIABLE

        classif_conf = round(c, 3) if condition_score is not None else None

        return ConfidenceBreakdown(
            quality_score=round(q, 3),
            segmentation_score=round(s, 3),
            condition_score=round(c, 3),
            geometry_score=round(g, 3),
            temporal_score=round(t, 3) if t is not None else None,
            measurement_confidence=meas_conf,
            classification_confidence=classif_conf,
            overall_confidence=meas_conf,
            decision=decision,
        )

    def fuse_confidence(
        self,
        quality_score: float,
        segmentation_score: float,
        condition_score: float,
        geometry_score: float,
        temporal_score: Optional[float] = None,
    ) -> ConfidenceBreakdown:
        """Compute weighted fused confidence and assign production decision.

        Maintains backward compatibility while enforcing strict authority separation:
        condition_score is tracked as classification_confidence but does NOT influence
        measurement acceptance or rejection decisions.
        """
        return self.fuse_measurement_confidence(
            quality_score=quality_score,
            segmentation_score=segmentation_score,
            geometry_score=geometry_score,
            temporal_score=temporal_score,
            condition_score=condition_score,
        )


# Global singleton instance
confidence_engine = ConfidenceEngine()
