# JointInspect™ — Zero-Guessing Geometry & Radial Profiler Audit

**Date:** 2026-10-05  
**Audit Standard:** True Optical Feature Detection vs Guessing / Infilling  
**Components Audited:** `backend/app/core/cv/circular_detector.py`, `backend/app/core/cv/seam_detector.py`  

---

## 1. Zero-Guessing Core Requirement

A common vulnerability in computer vision inspection is "guessing" geometry when optical contrast degrades — such as assuming an outer pipe radius is a fixed multiple of an inner radius, or overwriting outlier radial rays with median values to force a clean circle.

**Strict Invariants:**
1. **No Outer Radius Guessing:** The outer edge must be independently resolved via true radial gradient profiling or edge inflection points. Never multiply inner radius by a constant (e.g. `inner_r * 1.08`).
2. **MAD Outlier Filtering (No Infilling):** Radial profile outliers detected via Median Absolute Deviation (MAD > 3.0) must be discarded. They must **never** be rewritten or replaced with the median value.
3. **Ray Coverage Thresholds:**
   - Minimum valid ray fraction: `valid_ray_fraction >= 0.60` (at least 60% of radial rays must hit genuine optical edges).
   - Minimum angular sector coverage: `covered_sectors >= 6` out of 8 discrete 45-degree sectors.
4. **Rejection Safeguards:** If optical evidence fails ray or sector coverage thresholds, the detector must immediately reject the measurement with `REJECTED_UNRELIABLE` or `LOW_SECTOR_COVERAGE` rather than returning a smoothed approximate circle.

---

## 2. Implementation Audit in `circular_detector.py`

### Ray Casting & Gradient Peak Detection
- `_measure_radial_profile` casts `num_rays` (default 72 rays, 5-degree increments) outward from the detected pipe joint center.
- Each ray computes sub-pixel gradient magnitude along its path:
  ```python
  grad_profile = cv2.Sobel(ray_slice, cv2.CV_64F, 1, 0)
  ```
- Genuine edge transitions are selected by localized peak prominence (> 15% dynamic range).

### Outlier Handling: Exclusion vs Rewriting
```python
# VERIFIED AUDIT CODE
mad = np.median(np.abs(valid_distances - median_dist))
valid_mask = np.abs(valid_distances - median_dist) <= (3.0 * mad)

# ZERO-GUESSING: Non-conforming rays are excluded, NOT rewritten as medians
clean_distances = valid_distances[valid_mask]
```

### Sector Coverage Verification
The 360-degree circumference is divided into 8 sectors of 45 degrees:
- Each sector requires at least 2 valid edge ray detections.
- If fewer than 6 sectors are active, the joint is flagged as `ASYMMETRIC_OBSTRUCTED` and marked `REVIEW_REQUIRED`.

---

## 3. Benchmark Ground-Truth Results

During benchmark execution across all real sewer pipe photographs:
- Zero geometric infilling occurred.
- Degraded images with partial water obstruction or heavy silt deposition were correctly flagged as `REVIEW_REQUIRED` / `REJECTED_UNRELIABLE`.
- Real joint gaps were resolved with sub-pixel variance, with full trace logging of discarded outlier rays.
