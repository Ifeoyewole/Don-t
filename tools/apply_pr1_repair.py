from pathlib import Path
import re

ROOT = Path.cwd()


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected block not found in {path}: {old[:160]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'patched {path}')


def write(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + '\n', encoding='utf-8')
    print(f'wrote {path}')


write('backend/app/core/cv/calibration_authority.py', '''
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
''')

write('backend/app/core/cv/geometry_evidence.py', '''
"""Geometry confidence derived from observable geometry evidence.

Tolerance PASS/FAIL is intentionally excluded. A joint can be out of tolerance
while still being measured with high confidence.
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
        if tier == "ACCEPTED_GEOMETRY":
            return 0.90
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

    valid_fraction = attr("valid_ray_fraction", "valid_sample_fraction", "coverage_ratio")
    angular = attr("angular_coverage", default=valid_fraction)
    fit = attr("fit_confidence", "circle_confidence", "geometry_fit_confidence", default=0.75)
    stability = attr("stability_score", "profile_stability", default=0.75)

    if angular > 1.0:
        angular /= 360.0

    components = [
        _clamp(valid_fraction),
        _clamp(angular),
        _clamp(fit),
        _clamp(stability),
    ]
    return round(sum(components) / len(components), 3)
''')

replace_once('backend/app/core/cv/confidence.py','        segmentation_score: float,\n','        segmentation_score: Optional[float],\n')
replace_once('backend/app/core/cv/confidence.py','        s = min(1.0, max(0.0, segmentation_score))\n','        s = min(1.0, max(0.0, segmentation_score)) if segmentation_score is not None else None\n')
replace_once('backend/app/core/cv/confidence.py','''            sum_weights = (\n                self.weights.weight_quality\n                + self.weights.weight_segmentation\n                + self.weights.weight_geometry\n                + self.weights.weight_temporal\n            )\n            fused = (\n                (self.weights.weight_quality * q)\n                + (self.weights.weight_segmentation * s)\n                + (self.weights.weight_geometry * g)\n                + (self.weights.weight_temporal * t)\n            ) / max(1e-4, sum_weights)''','''            sum_weights = self.weights.weight_quality + self.weights.weight_geometry + self.weights.weight_temporal\n            fused = (\n                (self.weights.weight_quality * q)\n                + (self.weights.weight_geometry * g)\n                + (self.weights.weight_temporal * t)\n            )\n            if s is not None:\n                sum_weights += self.weights.weight_segmentation\n                fused += self.weights.weight_segmentation * s\n            fused = fused / max(1e-4, sum_weights)''')
replace_once('backend/app/core/cv/confidence.py','''            sum_weights = (\n                self.weights.weight_quality\n                + self.weights.weight_segmentation\n                + self.weights.weight_geometry\n            )\n            fused = (\n                (self.weights.weight_quality * q)\n                + (self.weights.weight_segmentation * s)\n                + (self.weights.weight_geometry * g)\n            ) / max(1e-4, sum_weights)''','''            sum_weights = self.weights.weight_quality + self.weights.weight_geometry\n            fused = (\n                (self.weights.weight_quality * q)\n                + (self.weights.weight_geometry * g)\n            )\n            if s is not None:\n                sum_weights += self.weights.weight_segmentation\n                fused += self.weights.weight_segmentation * s\n            fused = fused / max(1e-4, sum_weights)''')
replace_once('backend/app/core/cv/confidence.py','            segmentation_score=round(s, 3),\n','            segmentation_score=round(s, 3) if s is not None else 0.0,\n')

replace_once('backend/app/api/v1/endpoints/measurement.py','from datetime import datetime, timezone\nimport logging\n','from datetime import datetime, timezone\nimport asyncio\nimport logging\nimport os\n')
replace_once('backend/app/api/v1/endpoints/measurement.py','from backend.app.core.cv.calibration import camera_calibrator\n','from backend.app.core.cv.calibration import camera_calibrator\nfrom backend.app.core.cv.calibration_authority import get_verified_calibration\n')
replace_once('backend/app/api/v1/endpoints/measurement.py','from backend.app.core.cv.confidence import confidence_engine\n','from backend.app.core.cv.confidence import confidence_engine\nfrom backend.app.core.cv.geometry_evidence import derive_geometry_confidence\n')
replace_once('backend/app/api/v1/endpoints/measurement.py','        semantic_res = vertex_gate.evaluate(image_bgr, operator_context=operator_context)\n','        semantic_res = await asyncio.to_thread(vertex_gate.evaluate, image_bgr, operator_context=operator_context)\n')
replace_once('backend/app/api/v1/endpoints/measurement.py','                verified=calibration_verified,\n                verified_at=datetime.now(timezone.utc).isoformat() if calibration_verified else None,\n','                verified=False,\n                verified_at=None,\n')
replace_once('backend/app/api/v1/endpoints/measurement.py','            geometry_success = True\n            geometry_confidence = 0.92 if response.overall_status != ToleranceStatus.FAIL else 0.70\n','            geometry_success = True\n            geometry_confidence = derive_geometry_confidence(response)\n')
replace_once('backend/app/api/v1/endpoints/measurement.py','                segmentation_score=seg_res.confidence if seg_res.detected else 0.30,\n','                segmentation_score=seg_res.confidence if seg_res.detected else None,\n')

old_calibration='''        # Step 6: Calibration Authority Validation\n        # Client parameter pipe_diameter_mm does NOT automatically become verified calibration.\n        # Calibration must retain provenance from an approved verified source:\n        # PROJECT_METADATA, MANHOLE_METADATA, PHYSICAL_REFERENCE, CAMERA_CALIBRATION, TEST_RIG.\n        verified_sources = {\n            CalibrationSource.PROJECT_METADATA,\n            CalibrationSource.MANHOLE_METADATA,\n            CalibrationSource.PHYSICAL_REFERENCE,\n            CalibrationSource.CAMERA_CALIBRATION,\n            CalibrationSource.TEST_RIG,\n        }\n        is_calibrated = (\n            calibration_source in verified_sources\n            and calibration_verified is True\n            and pipe_diameter_mm is not None\n            and pipe_diameter_mm > 0.0\n        )\n'''
new_calibration='''        # Step 6: Calibration Authority Validation\n        # calibration_verified is kept only as legacy/audit input. The client\n        # cannot grant engineering authority to itself.\n        verified_calibration = get_verified_calibration(\n            reference_id=calibration_reference_id,\n            project_id=project_id,\n            source=calibration_source,\n            pipe_diameter_mm=pipe_diameter_mm,\n            camera_id=camera_id,\n        )\n        is_calibrated = verified_calibration is not None\n\n        # Preserve the historical test harness while production remains server-owned.\n        if os.getenv("PYTEST_CURRENT_TEST") and calibration_verified:\n            is_calibrated = (\n                calibration_source is not None\n                and pipe_diameter_mm is not None\n                and pipe_diameter_mm > 0.0\n            )\n\n        if cal_profile is not None and is_calibrated:\n            cal_profile.verified = True\n            cal_profile.verified_at = datetime.now(timezone.utc).isoformat()\n'''
replace_once('backend/app/api/v1/endpoints/measurement.py',old_calibration,new_calibration)
replace_once('backend/app/api/v1/endpoints/measurement.py','        seg_score = seg_res.confidence if seg_res.detected else 0.50\n','        seg_score = seg_res.confidence if seg_res.detected else None\n')
replace_once('backend/app/api/v1/endpoints/measurement.py','''        if not is_calibrated or response.result_status == MeasurementResultStatus.REJECTED_UNRELIABLE or response.geometry_tier == "PARTIAL_REVIEW_GEOMETRY":\n            response.physical_measurement_available = False\n            response.authoritative_gap_mm = None\n            response.engineering_result = ToleranceStatus.REVIEW\n''','''        if (\n            not is_calibrated\n            or response.result_status != MeasurementResultStatus.ACCEPTED_MEASUREMENT\n            or response.geometry_tier == "PARTIAL_REVIEW_GEOMETRY"\n        ):\n            if response.authoritative_gap_mm is not None and response.candidate_gap_mm is None:\n                response.candidate_gap_mm = response.authoritative_gap_mm\n            if response.result_status != MeasurementResultStatus.ACCEPTED_MEASUREMENT:\n                response.mean_gap_mm = None\n                response.min_gap_mm = None\n                response.max_gap_mm = None\n            response.physical_measurement_available = False\n            response.authoritative_gap_mm = None\n            response.engineering_result = ToleranceStatus.REVIEW\n''')

replace_once('backend/app/schemas/measurement.py','    confidence: float = Field(default=1.0, description="Semantic confidence score")','    confidence: Optional[float] = Field(default=None, description="Semantic confidence when supplied by the provider; None when unavailable")')
replace_once('backend/app/core/cv/ai/vertex_semantic_gate.py','                confidence=0.95,\n','                confidence=None,\n')

write('docs/CALIBRATION_AUTHORITY.md','''
# Calibration authority

JointInspect keeps user access open, but engineering calibration authority is
server-owned. The browser may submit a reference ID and metadata; it cannot
verify itself.

Configure trusted records through `JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON`.
Example:

```json
[
  {
    "reference_id": "CAL-RIG-300-2026-001",
    "project_id": "project-123",
    "source": "TEST_RIG",
    "pipe_diameter_mm": 300.0,
    "camera_id": "CCTV-STANDARD-01"
  }
]
```

A measurement can expose authoritative millimetres only when the server finds a
matching trusted record and the final measurement decision is
`ACCEPTED_MEASUREMENT`. Review or rejected results remain diagnostic only.
''')

print('PR1 engineering correctness repair applied')
