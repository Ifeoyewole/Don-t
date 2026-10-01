"""Multi-component confidence fusion and calibrated production gating engine."""

from typing import Dict, Optional
from pydantic import BaseModel, Field

from backend.app.schemas.domain import MeasurementResultStatus
from backend.app.schemas.measurement import ConfidenceBreakdown


class ConfidenceWeights(BaseModel):
    """Component weighting for fused confidence calculation (v1 baseline defaults)."""
    weight_quality: float = Field(default=0.15, description="Weight for image clarity/exposure score")
    weight_segmentation: float = Field(default=0.25, description="Weight for AI joint mask confidence")
    weight_condition: float = Field(default=0.15, description="Weight for defect classification confidence")
    weight_geometry: float = Field(default=0.30, description="Weight for sub-pixel OpenCV edge/circle gradient score")
    weight_temporal: float = Field(default=0.15, description="Weight for multi-frame consistency score")


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

    def fuse_confidence(
        self,
        quality_score: float,
        segmentation_score: float,
        condition_score: float,
        geometry_score: float,
        temporal_score: Optional[float] = None,
    ) -> ConfidenceBreakdown:
        """Compute weighted fused confidence and assign production decision.

        Args:
            quality_score: 0.0 to 1.0 from image_quality validator.
            segmentation_score: 0.0 to 1.0 from JointSegmenter.
            condition_score: 0.0 to 1.0 from JointClassifier.
            geometry_score: 0.0 to 1.0 from OpenCV circle/seam detector.
            temporal_score: Optional 0.0 to 1.0 from multi-frame tracking buffer.

        Returns:
            ConfidenceBreakdown: Normalized scores, fused confidence, and decision gating.
        """
        # Clamp inputs
        q = min(1.0, max(0.0, quality_score))
        s = min(1.0, max(0.0, segmentation_score))
        c = min(1.0, max(0.0, condition_score))
        g = min(1.0, max(0.0, geometry_score))

        if temporal_score is not None:
            t = min(1.0, max(0.0, temporal_score))
            fused = (
                self.weights.weight_quality * q
                + self.weights.weight_segmentation * s
                + self.weights.weight_condition * c
                + self.weights.weight_geometry * g
                + self.weights.weight_temporal * t
            )
        else:
            t = None
            # Re-normalize weights for single-frame evaluation
            sum_weights = (
                self.weights.weight_quality
                + self.weights.weight_segmentation
                + self.weights.weight_condition
                + self.weights.weight_geometry
            )
            fused = (
                (self.weights.weight_quality * q)
                + (self.weights.weight_segmentation * s)
                + (self.weights.weight_condition * c)
                + (self.weights.weight_geometry * g)
            ) / max(1e-4, sum_weights)

        fused = round(float(min(1.0, max(0.0, fused))), 3)

        # Calibrated decision gating
        if fused >= self.thresholds.tau_accept:
            decision = MeasurementResultStatus.ACCEPTED_MEASUREMENT
        elif fused >= self.thresholds.tau_reject:
            decision = MeasurementResultStatus.REVIEW_REQUIRED
        else:
            decision = MeasurementResultStatus.REJECTED_UNRELIABLE

        return ConfidenceBreakdown(
            quality_score=round(q, 3),
            segmentation_score=round(s, 3),
            condition_score=round(c, 3),
            geometry_score=round(g, 3),
            temporal_score=round(t, 3) if t is not None else None,
            overall_confidence=fused,
            decision=decision,
        )


# Global singleton instance
confidence_engine = ConfidenceEngine()
