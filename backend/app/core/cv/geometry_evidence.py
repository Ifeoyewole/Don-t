"""Geometry confidence derived from observable geometry evidence.

Tolerance PASS/FAIL is intentionally excluded. A joint can be out of tolerance
while still being measured with high confidence. Geometry tiers are produced by
the detector's independent evidence gates, so accepted/partial tiers are mapped
to confidence ranges using measured coverage within that tier.
"""

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def derive_geometry_confidence(response: Any) -> float:
    debug = getattr(response, "debug_info", None)
    tier = str(getattr(response, "geometry_tier", "") or "")

    if debug is None:
        if tier == "ACCEPTABLE_GEOMETRY":
            return 0.95
        if tier == "PARTIAL_REVIEW_GEOMETRY":
            return 0.72
        return 0.45

    def attr(*names: str, default: float = 0.0) -> float:
        for name in names:
            if isinstance(debug, dict) and name in debug:
                return _num(debug.get(name), default)
            if hasattr(debug, name):
                return _num(getattr(debug, name), default)
        return default

    valid_fraction = _clamp(attr("valid_ray_fraction", "valid_sample_fraction", "coverage_ratio"))
    angular = attr("angular_coverage", default=valid_fraction)
    if angular > 1.0:
        angular /= 360.0
    angular = _clamp(angular)

    # The geometry engine has already applied its strict independent evidence
    # thresholds before assigning these tiers. Confidence reflects strength
    # within the tier; it is never derived from PASS/WARNING/FAIL tolerance.
    if tier == "ACCEPTABLE_GEOMETRY":
        strength = (0.65 * valid_fraction) + (0.35 * angular)
        return round(min(0.99, 0.95 + (0.04 * strength)), 3)

    if tier == "PARTIAL_REVIEW_GEOMETRY":
        strength = (0.65 * valid_fraction) + (0.35 * angular)
        return round(min(0.84, 0.68 + (0.16 * strength)), 3)

    return round(max(0.20, min(0.65, valid_fraction * 0.65)), 3)
