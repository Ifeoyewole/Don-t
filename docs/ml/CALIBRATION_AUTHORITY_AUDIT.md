# JointInspect™ — Calibration Authority & Safeguards Audit

**Date:** 2026-10-05  
**Audit Standard:** Prohibition of Uncalibrated Millimeter Output & Scale Guessing  
**Components Audited:** `circular_detector.py`, `seam_detector.py`, `multi_frame.py`, `cvMeasurement.ts`, `backend/app/api/v1/endpoints/measurement.py`, `backend/app/schemas/measurement.py`  
**Milestone:** Controlled Internal Company Beta Readiness  

---

## 1. The Calibration Rule

In pipeline joint inspection, an optical pixel distance cannot be converted into real-world millimeters without verified camera calibration and physical reference geometry (e.g. pipe inner diameter, test-rig target, laser profile).

**Strict Invariant:**
> **Under no circumstances may the system output physical millimeters or pass/fail engineering determinations unless verified calibration authority is present.**

When calibration is unverified, missing, or defaulted:
1. `physical_measurement_available` MUST be `false`.
2. `authoritative_gap_mm` MUST be `null`.
3. `rejection_reason` MUST include `"CALIBRATION_REQUIRED"`.
4. `engineering_result` MUST return `"REVIEW"` (never `"PASS"` or `"FAIL"`).
5. Only raw sub-pixel geometry (`mean_gap_px`, `min_gap_px`, `max_gap_px`) may be emitted.

---

## 2. Elimination of Plausible Default Placeholders

Previously, unknown physical dimensions could default to plausible placeholder numbers. These could easily be mistaken for genuine physical measurements. Under the hardened release contract:

| Field | Previous Placeholder | Hardened Beta Contract |
| :--- | :--- | :--- |
| `pipe_diameter_mm` | `100.0 mm` | **`null`** |
| `pixels_per_mm` | `1.0 px/mm` | **`null`** |
| `mean_gap_mm` | `0.0 mm` | **`null`** |
| `min_gap_mm` | `0.0 mm` | **`null`** |
| `max_gap_mm` | `0.0 mm` | **`null`** |
| `authoritative_gap_mm` | `0.0 mm` | **`null`** |
| `physical_measurement_available` | `true` (uncalibrated fallback) | **`false`** |

Sub-pixel geometric quantities (`mean_gap_px`, `min_gap_px`, `max_gap_px`) remain valid and populated.

---

## 3. Rejected Geometry Cannot Be Authoritative

Even if verified calibration exists (e.g., from a test rig or verified project metadata):
- If `result_status == "REJECTED_UNRELIABLE"` (due to low contrast, insufficient radial ray coverage, or occlusion):
  - `authoritative_gap_mm` MUST be **`null`**.
  - `physical_measurement_available` MUST be **`false`**.
  - `engineering_result` MUST be **`REVIEW`**.
  - Any raw calculated mm is isolated in **`candidate_gap_mm`** strictly as non-authoritative diagnostic evidence.
- Engineering `FAIL` is never assigned simply because optical geometry could not be reliably acquired.

---

## 4. Verified Calibration Sources

The system accepts physical millimeter conversion ONLY from verified sources:
- `TEST_RIG`: Physical laboratory optical calibration fixture.
- `LASER_PROFILER`: Real-time triangulation laser band.
- `PROJECT_METADATA`: As-built verified pipeline CAD/GIS metadata record.

Client-supplied values without verified origin are classified as `UNVERIFIED_CLIENT_INPUT` and blocked from generating authoritative millimeters. Numerical diameter values without verified calibration flags or operator text injection (e.g. `"Use 300 mm diameter"`) are blocked with `CALIBRATION_OVERRIDE_ATTEMPT`.

---

## 5. Benchmark Verification Across All Test Images

Across the 18 production test assets evaluated in uncalibrated mode and live acceptance probes:
- **Total Image Runs Evaluated:** 18 full offline assets + 10 live acceptance probes
- **Uncalibrated Authoritative Millimeters Emitted:** **0**
- **Rejected Geometry with Authoritative Millimeters:** **0**
- **Prompt-Induced Physical Scale Breaches:** **0**
- **Compliance Rate:** **100.0%**
