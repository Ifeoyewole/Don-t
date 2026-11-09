
"""Server-owned calibration authority for engineering measurements.

The browser may submit calibration metadata, but it cannot grant itself
engineering authority. Trusted calibration records are loaded server-side from
JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON.
"""

import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from backend.app.schemas.domain import CalibrationSource


@dataclass(frozen=True)
class VerifiedCalibration:
    reference_id: str
    project_id: Optional[str]
    source: CalibrationSource
    pipe_diameter_mm: float
    camera_id: Optional[str] = None
    validated_joint_types: tuple[str, ...] = ('CIRCULAR_OPENING',)
    reference_length_mm: Optional[float] = None
    reference_span_px: Optional[float] = None
    image_sha256: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None

    def scale_for_image(self, sha256: str, width: int, height: int) -> Optional[float]:
        """Measured span is in rectified image pixels, at the joint plane.

        Exact uploaded bytes and resolution bind this scale to one photograph.
        These values are server-owned, never accepted as browser attestation.
        """
        if (not self.image_sha256 or self.image_sha256 != sha256
                or self.image_width != width or self.image_height != height):
            return None
        values = (self.reference_length_mm, self.reference_span_px)
        if any(v is None or not math.isfinite(v) or v <= 0 for v in values):
            return None
        if self.reference_span_px > math.hypot(width, height):
            return None
        return self.reference_span_px / self.reference_length_mm


def _close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=1e-6)


@lru_cache(maxsize=1)
def _records() -> tuple[VerifiedCalibration, ...]:
    raw = os.getenv("JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON", "[]").strip()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return tuple()

    if not isinstance(items, list):
        return tuple()

    records: list[VerifiedCalibration] = []
    for item in items:
        try:
            records.append(
                VerifiedCalibration(
                    reference_id=str(item["reference_id"]).strip(),
                    project_id=(str(item["project_id"]).strip() if item.get("project_id") else None),
                    source=CalibrationSource(str(item["source"])),
                    pipe_diameter_mm=float(item["pipe_diameter_mm"]),
                    camera_id=(str(item["camera_id"]).strip() if item.get("camera_id") else None),
                    reference_length_mm=float(item['reference_length_mm']) if item.get('reference_length_mm') is not None else None,
                    reference_span_px=float(item['reference_span_px']) if item.get('reference_span_px') is not None else None,
                    image_sha256=str(item['image_sha256']) if item.get('image_sha256') else None,
                    image_width=int(item['image_width']) if item.get('image_width') is not None else None,
                    image_height=int(item['image_height']) if item.get('image_height') is not None else None,
                    validated_joint_types=tuple(
                        x for x in item.get("validated_joint_types", ["CIRCULAR_OPENING"])
                        if x in {"CIRCULAR_OPENING", "HORIZONTAL_SEAM", "VERTICAL_SEAM"}
                    ),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(records)


def clear_calibration_cache() -> None:
    _records.cache_clear()


def get_verified_calibration(
    *,
    reference_id: Optional[str],
    project_id: Optional[str],
    source: Optional[CalibrationSource],
    pipe_diameter_mm: Optional[float],
    camera_id: Optional[str],
    joint_type: Optional[str] = None,
) -> Optional[VerifiedCalibration]:
    if (
        not reference_id
        or not reference_id.strip()
        or source is None
        or pipe_diameter_mm is None
        or not math.isfinite(float(pipe_diameter_mm))
        or pipe_diameter_mm <= 0.0
    ):
        return None

    for record in _records():
        if record.reference_id != reference_id:
            continue
        if record.source != source:
            continue
        # A server-owned reference scoped to a project or camera must NEVER
        # authorize an omitted, different, or unrecognized project/camera.
        if record.project_id and record.project_id != project_id:
            continue
        # Photo-scale permission is camera/rig-specific; a diameter-only record
        # is nominal metadata, not sufficient to authorize spatial millimetres.
        if not record.camera_id or not camera_id or record.camera_id != camera_id:
            continue
        if joint_type is not None and joint_type not in record.validated_joint_types:
            continue
        if not _close(record.pipe_diameter_mm, pipe_diameter_mm):
            continue
        return record
    return None
