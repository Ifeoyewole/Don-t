
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
) -> Optional[VerifiedCalibration]:
    if not reference_id or source is None or pipe_diameter_mm is None:
        return None

    for record in _records():
        if record.reference_id != reference_id:
            continue
        if record.source != source:
            continue
        if record.project_id and project_id and record.project_id != project_id:
            continue
        if record.camera_id and camera_id and record.camera_id != camera_id:
            continue
        if not _close(record.pipe_diameter_mm, pipe_diameter_mm):
            continue
        return record
    return None
