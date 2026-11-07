"""Research-only fusion of independently localized pipe geometry evidence.

Accepts per-photo ROIs from an inspector, Inspect View, Gemini or a CV mask
pipeline. These are CALLER-PROVIDED proposals, not live calls to either model.
Only original OpenCV/NumPy algorithms are used; no external repo is imported.

No measured millimetres, automatic defect labels, calibration verification,
or engineering PASS/FAIL are returned. Partial arcs require independent,
distinct nearby video frames with coherent normalized geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Optional, Sequence, Tuple

import numpy as np

from backend.app.core.cv.experimental_ellipse import audit_projected_pipe_rings
from backend.app.core.cv.experimental_geometry import audit_dark_seam

_SOURCE_PRIORITY = {"INSPECTOR": 0, "INSPECT_VIEW": 1, "GEMINI": 2, "CV_MASK": 3}
_GEOMETRIES = {"CIRCULAR_OPENING", "HORIZONTAL_SEAM", "VERTICAL_SEAM"}


@dataclass(frozen=True)
class RoiProposal:
    source: str
    bbox: Tuple[int, int, int, int]
    geometry: str
    confidence: Optional[float] = None


@dataclass(frozen=True)
class FrameRequest:
    frame_id: str
    frame_index: int
    sequence_id: str
    image_bgr: np.ndarray
    proposals: Sequence[RoiProposal]


@dataclass(frozen=True)
class FrameAudit:
    frame_id: str
    roi_source: Optional[str]
    roi_bbox: Optional[Tuple[int, int, int, int]]
    status: str
    projected_pixel_candidate: Optional[float]
    normalized_ring_spacing: Optional[float]
    ring_aspect_ratio: Optional[float]
    reason: str


@dataclass(frozen=True)
class GeometryFusionAudit:
    geometry: str
    status: str
    frame_audits: tuple[FrameAudit, ...]
    reason: str
    # Intentionally no mm, condition label, engineering verdict, or PASS field.


def _valid_bbox(
    bbox: Tuple[int, int, int, int],
    shape: tuple[int, ...],
    geometry: str,
) -> bool:
    try:
        x0, y0, x1, y1 = bbox
        if any(type(v) is not int for v in (x0, y0, x1, y1)):
            return False
        h, w = shape[:2]
        min_span = 64 if geometry == "CIRCULAR_OPENING" else 30
        return (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
                and x1 - x0 >= min_span and y1 - y0 >= min_span)
    except (ValueError, TypeError):
        return False


def _select_roi(
    proposals: Sequence[RoiProposal],
    image: np.ndarray,
    geometry: str,
) -> Optional[RoiProposal]:
    candidates = []
    for proposal in proposals:
        if proposal.geometry != geometry or proposal.source not in _SOURCE_PRIORITY:
            continue
        if not _valid_bbox(proposal.bbox, image.shape, geometry):
            continue
        if proposal.source == "INSPECTOR":
            # Human selections are editable, but still only define the search ROI.
            rank = 1.0
        else:
            confidence = proposal.confidence
            if (confidence is None or isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not isfinite(confidence) or not 0.70 <= confidence <= 1.0):
                continue
            rank = float(confidence)
        candidates.append((_SOURCE_PRIORITY[proposal.source], -rank, proposal))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2] if candidates else None


def audit_geometry_frames(
    frames: Sequence[FrameRequest],
    geometry: str,
) -> GeometryFusionAudit:
    """Combine per-photo independent geometry, rejecting unsupported evidence.

    Full projected ring pairs may be reported as SINGLE_FRAME evidence. Partial
    rings never pass without 2+ different adjacent frames from ONE sequence.
    Spatial calibration is completely outside this function.
    """
    if geometry not in _GEOMETRIES:
        return GeometryFusionAudit(geometry, "REVIEW_REQUIRED", (), "unsupported_geometry")
    if not (1 <= len(frames) <= 8):
        return GeometryFusionAudit(geometry, "REVIEW_REQUIRED", (), "invalid_frame_count")

    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    frame_audits: list[FrameAudit] = []
    distinct_sequences: set[str] = set()
    temporal: list[tuple[int, float, float]] = []  # index, normalized gap, aspect
    full_count = 0
    for frame in frames:
        if (not frame.frame_id or not frame.sequence_id or
                frame.frame_id in seen_ids or
                not isinstance(frame.frame_index, int) or frame.frame_index < 0):
            return GeometryFusionAudit(
                geometry, "REVIEW_REQUIRED", tuple(frame_audits), "invalid_or_duplicate_frame_metadata",
            )
        seen_ids.add(frame.frame_id)
        distinct_sequences.add(frame.sequence_id)
        img = frame.image_bgr
        if img is None or not isinstance(img, np.ndarray) or img.size == 0 or img.ndim not in (2, 3):
            frame_audits.append(FrameAudit(frame.frame_id, None, None, "INSUFFICIENT_EVIDENCE", None, None, None, "invalid_image"))
            continue
        digest = sha256(np.ascontiguousarray(img).tobytes()).hexdigest()
        if digest in seen_hashes:
            frame_audits.append(FrameAudit(frame.frame_id, None, None, "INSUFFICIENT_EVIDENCE", None, None, None, "duplicate_image_bytes"))
            continue
        seen_hashes.add(digest)
        selected = _select_roi(frame.proposals, img, geometry)
        if selected is None:
            frame_audits.append(FrameAudit(frame.frame_id, None, None, "INSUFFICIENT_EVIDENCE", None, None, None, "no_valid_localized_roi"))
            continue
        if geometry == "CIRCULAR_OPENING":
            audit = audit_projected_pipe_rings(img, selected.bbox, allow_partial=True)
            if audit.inner_ring is None or audit.outer_ring is None:
                frame_audits.append(FrameAudit(frame.frame_id, selected.source, selected.bbox, "INSUFFICIENT_EVIDENCE", None, None, None, audit.reason))
                continue
            outer_axes = audit.outer_ring.axes_px
            major = max(outer_axes)
            minor = min(outer_axes)
            if major <= 0 or minor <= 0 or audit.projected_semiaxis_spacing_px is None:
                frame_audits.append(FrameAudit(frame.frame_id, selected.source, selected.bbox, "INSUFFICIENT_EVIDENCE", None, None, None, "invalid_fitted_axes"))
                continue
            relative_spacing = audit.projected_semiaxis_spacing_px / (major / 2.0)
            aspect = minor / major
            if not (0.015 < relative_spacing < 0.5 and 0.32 < aspect <= 1.0):
                frame_audits.append(FrameAudit(frame.frame_id, selected.source, selected.bbox, "INSUFFICIENT_EVIDENCE", None, None, None, "invalid_relative_ring_geometry"))
                continue
            is_full = audit.status == "PROJECTED_RING_EVIDENCE"
            if is_full:
                full_count += 1
            frame_audits.append(FrameAudit(
                frame.frame_id, selected.source, selected.bbox,
                "FULL_RING_CANDIDATE" if is_full else "PARTIAL_RING_CANDIDATE",
                audit.projected_semiaxis_spacing_px, round(relative_spacing, 4),
                round(aspect, 4), audit.reason,
            ))
            temporal.append((frame.frame_index, relative_spacing, aspect))
        else:
            audit = audit_dark_seam(img, geometry, selected.bbox)
            frame_audits.append(FrameAudit(
                frame.frame_id, selected.source, selected.bbox, audit.status,
                audit.candidate_gap_px, None, None, audit.reason,
            ))

    if geometry != "CIRCULAR_OPENING":
        if any(f.status == "EVIDENCE_CANDIDATE" for f in frame_audits):
            return GeometryFusionAudit(geometry, "PIXEL_SEAM_CANDIDATE", tuple(frame_audits), "independent_seam_evidence_requires_validation")
        return GeometryFusionAudit(geometry, "REVIEW_REQUIRED", tuple(frame_audits), "no_supported_seam_evidence")

    if full_count >= 1:
        return GeometryFusionAudit(geometry, "SINGLE_FRAME_RING_CANDIDATE", tuple(frame_audits), "nested_projected_rings_not_axial_gap")

    # Only partial contours remain. Require near-adjacent, distinct frames of
    # the same video. Same-photo duplicates and unrelated sites cannot vote.
    if len(distinct_sequences) != 1 or len(temporal) < 2:
        return GeometryFusionAudit(geometry, "REVIEW_REQUIRED", tuple(frame_audits), "partial_rings_need_two_frames_one_sequence")
    temporal.sort(key=lambda item: item[0])
    pairs = []
    for first, second in zip(temporal, temporal[1:]):
        frame_delta = second[0] - first[0]
        if not 1 <= frame_delta <= 5:
            continue
        _, span_a, aspect_a = first
        _, span_b, aspect_b = second
        if abs(span_a - span_b) > max(0.035, 0.25 * max(span_a, span_b)):
            continue
        if abs(aspect_a - aspect_b) > 0.18:
            continue
        pairs.append((first, second))
    if not pairs:
        return GeometryFusionAudit(geometry, "REVIEW_REQUIRED", tuple(frame_audits), "partial_rings_not_temporally_consistent")
    return GeometryFusionAudit(
        geometry, "TEMPORAL_PARTIAL_RING_CANDIDATE", tuple(frame_audits),
        "nearby_frames_support_projected_ring_pair_not_physical_gap",
    )
