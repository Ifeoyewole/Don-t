"""Tolerance classification and pass/fail evaluation engine."""

from typing import List, Optional
from backend.app.schemas.domain import ToleranceStatus
from backend.app.schemas.measurement import ToleranceSpec


def classify_gap(
    gap_mm: float,
    pipe_diameter_mm: float = 100.0,
    tolerance_spec: Optional[ToleranceSpec] = None,
) -> ToleranceStatus:
    """Classify measured gap dimension against engineering tolerance standards.

    Standard Pipe Table Rules:
    - < 3.0 mm: REVIEW (Risk of binding, insufficient seal clearance, or thermal expansion pinch)
    - 3.0 mm - 15.0 mm: PASS (Optimal annular/seam clearance)
    - 15.0 mm - 25.0 mm: REVIEW (Marginal / excessive gap requiring inspector signoff)
    - > 25.0 mm: FAIL (Out of specification / seal failure risk)

    If a custom ToleranceSpec is provided, it evaluates against the specified bounds:
    - gap < min_gap_mm: REVIEW
    - gap > max_gap_mm + warning_margin_mm: FAIL
    - gap > max_gap_mm: WARNING
    - Otherwise: PASS

    Args:
        gap_mm: Measured gap distance in millimeters.
        pipe_diameter_mm: Reference pipe diameter in millimeters.
        tolerance_spec: Optional custom tolerance specification.

    Returns:
        ToleranceStatus: PASS, WARNING, FAIL, or REVIEW.
    """
    if gap_mm < 0:
        return ToleranceStatus.FAIL

    if tolerance_spec is not None:
        if gap_mm < tolerance_spec.min_gap_mm:
            return ToleranceStatus.REVIEW
        elif gap_mm > (tolerance_spec.max_gap_mm + tolerance_spec.warning_margin_mm):
            return ToleranceStatus.FAIL
        elif gap_mm > tolerance_spec.max_gap_mm:
            return ToleranceStatus.WARNING
        else:
            return ToleranceStatus.PASS

    # Standard Pipe Engineering Tolerance Table
    if gap_mm < 3.0:
        return ToleranceStatus.REVIEW
    elif 3.0 <= gap_mm <= 15.0:
        return ToleranceStatus.PASS
    elif 15.0 < gap_mm <= 25.0:
        return ToleranceStatus.REVIEW
    else:
        return ToleranceStatus.FAIL


def evaluate_overall_status(
    sample_statuses: List[ToleranceStatus],
) -> ToleranceStatus:
    """Aggregate individual point sample statuses into a single QA classification.

    Priority hierarchy:
    1. FAIL: If any sample is FAIL.
    2. WARNING: If any sample is WARNING (and no FAIL).
    3. REVIEW: If any sample is REVIEW (and no FAIL/WARNING).
    4. PASS: If all samples are PASS.

    Args:
        sample_statuses: Collection of ToleranceStatus values for all measurement points.

    Returns:
        ToleranceStatus: Overall aggregated status.
    """
    if not sample_statuses:
        return ToleranceStatus.REVIEW

    if ToleranceStatus.FAIL in sample_statuses:
        return ToleranceStatus.FAIL
    if ToleranceStatus.WARNING in sample_statuses:
        return ToleranceStatus.WARNING
    if ToleranceStatus.REVIEW in sample_statuses:
        return ToleranceStatus.REVIEW

    return ToleranceStatus.PASS
