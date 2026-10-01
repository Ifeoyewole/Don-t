"""Multi-frame temporal measurement fusion and outlier filtering engine."""

from typing import List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from backend.app.schemas.domain import JointConditionClass, ToleranceStatus


class MultiFrameFusionResult(BaseModel):
    """Aggregated temporal measurement results across a burst of video frames."""
    num_input_frames: int = Field(..., description="Total sequential frames supplied")
    num_accepted_frames: int = Field(..., description="Frames retained after MAD outlier rejection")
    fused_mean_gap_mm: float = Field(..., description="Robust median gap across accepted frames in mm")
    fused_min_gap_mm: float = Field(..., description="Minimum gap across accepted frames in mm")
    fused_max_gap_mm: float = Field(..., description="Maximum gap across accepted frames in mm")
    mad_mm: float = Field(..., description="Median Absolute Deviation of gap across temporal sequence in mm")
    temporal_consistency_score: float = Field(..., description="Normalized temporal stability score (0.0 to 1.0)")
    outlier_frame_indices: List[int] = Field(default_factory=list, description="Frame indices rejected as outliers")


class MultiFrameFusion:
    """Combines consecutive CCTV video frame measurements with robust statistics."""

    @staticmethod
    def fuse_frame_measurements(
        frame_gaps_mm: List[float],
        mad_threshold_factor: float = 2.5,
    ) -> MultiFrameFusionResult:
        """Filter transient measurement spikes across consecutive frames using Median & MAD.

        Args:
            frame_gaps_mm: Sequence of measured mean gap values from consecutive frames.
            mad_threshold_factor: Multiplier for outlier rejection boundary (default 2.5 * 1.4826 * MAD).

        Returns:
            MultiFrameFusionResult: Robust fused gap, MAD, and temporal consistency score.
        """
        if not frame_gaps_mm:
            return MultiFrameFusionResult(
                num_input_frames=0,
                num_accepted_frames=0,
                fused_mean_gap_mm=0.0,
                fused_min_gap_mm=0.0,
                fused_max_gap_mm=0.0,
                mad_mm=0.0,
                temporal_consistency_score=0.0,
                outlier_frame_indices=[],
            )

        arr = np.array(frame_gaps_mm, dtype=np.float64)
        n = len(arr)

        if n == 1:
            val = float(arr[0])
            return MultiFrameFusionResult(
                num_input_frames=1,
                num_accepted_frames=1,
                fused_mean_gap_mm=round(val, 2),
                fused_min_gap_mm=round(val, 2),
                fused_max_gap_mm=round(val, 2),
                mad_mm=0.0,
                temporal_consistency_score=1.0,
                outlier_frame_indices=[],
            )

        median_gap = float(np.median(arr))
        abs_deviations = np.abs(arr - median_gap)
        mad = float(np.median(abs_deviations))

        # Outlier rejection using MAD
        normalizer = 1.4826 * mad
        outlier_indices = []
        accepted_values = []

        for idx, val in enumerate(arr):
            deviation = abs(val - median_gap)
            if normalizer > 1e-4 and deviation > (mad_threshold_factor * normalizer):
                outlier_indices.append(idx)
            else:
                accepted_values.append(val)

        if not accepted_values:
            accepted_values = [median_gap]

        accepted_arr = np.array(accepted_values)
        fused_gap = float(np.median(accepted_arr))

        # Temporal consistency score: high if MAD is small relative to nominal gap
        # E.g. MAD < 0.5mm is very high consistency (score ~0.95+), MAD > 2.0mm degrades score
        temporal_score = max(0.2, 1.0 - (mad / 3.0))
        # Penalize if many frames were rejected
        rejection_penalty = float(len(outlier_indices)) / float(n) * 0.3
        final_temporal_score = round(float(np.clip(temporal_score - rejection_penalty, 0.0, 1.0)), 3)

        return MultiFrameFusionResult(
            num_input_frames=n,
            num_accepted_frames=len(accepted_values),
            fused_mean_gap_mm=round(fused_gap, 2),
            fused_min_gap_mm=round(float(np.min(accepted_arr)), 2),
            fused_max_gap_mm=round(float(np.max(accepted_arr)), 2),
            mad_mm=round(mad, 3),
            temporal_consistency_score=final_temporal_score,
            outlier_frame_indices=outlier_indices,
        )

    @staticmethod
    def fuse_condition_with_geometry(
        classifier_condition: JointConditionClass,
        measured_gap_mm: float,
        max_allowable_gap_mm: Optional[float] = None,
    ) -> JointConditionClass:
        """Enforce tolerance-primary authority: OPEN_JOINT if measured gap exceeds allowable threshold."""
        if max_allowable_gap_mm is not None and measured_gap_mm > max_allowable_gap_mm:
            return JointConditionClass.OPEN_JOINT
        return classifier_condition
