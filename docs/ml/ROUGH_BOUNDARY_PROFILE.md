# Rough concrete seam width profile — research-only workflow

JointInspect's early dark-band detector could return one summary number (for
example, 127 pixels on a real uploaded photograph) without revealing the
locations of individual measurements. This experiment adds transparent,
per-cross-section measurements and an overlay without adding external project
code or new dependencies.

## Run on Windows / PowerShell

From the **repo root** (where `backend/` and `scripts/` appear):

```powershell
python -m pytest backend/tests/test_experimental_rough_profile.py backend/tests/test_multiframe_calibration_authority.py -q
python -m scripts.benchmark_rough_profile --manifest inspection-test.json --report rough-profile.json --overlay rough-profile.jpg
ii .\rough-profile.jpg
```

Use the original photo (without any previously drawn green ROI rectangle) and
set the JSON `geometry` and inspector ROI to `VERTICAL_SEAM` or
`HORIZONTAL_SEAM`. The command reads the same
`inspection-test.json` used by `benchmark_fused_geometry`. The JSON contains
all sampled positions, the two band-boundary image coordinates, rejected-row
reasons, median/min/max/p95 width and the supported scanline fraction.

The colored lines in the overlay indicate **dark-band intensity transitions**
rather than independently verified concrete material boundaries. The apparent
separation may contain shadows, texture, deposits or cracks. If the method
cannot support a band it reports `REVIEW_REQUIRED` and null widths rather
than guessing. Never use the JSON estimates as self-generated ground truth.

## Benchmarking and next decision

1. Manually annotate the *true visible concrete boundary* on at least 20
   rough-seam photographs from multiple pipes/cameras and add negative
   examples (wet stains, shadows, textures, other defects).
2. Compare the prior `benchmark_shadow_geometry.py` candidate against
   per-cross-section manual labels, using MAE, signed width bias, coverage
   and false measurement rate on negative images.
3. Include a held-out set by video, pipe and inspection site to avoid
   leakage; inspect each annotated overlay before assigning field accuracy.
4. Where boundaries cannot be identified visually, do not issue a physical
   measurement. Mask-based skeleton and distance transforms can be evaluated
   later but ONLY if segmentation masks represent the actual opening.
5. Keep this experiment out of `/api/v1/cv/measure` until real-world labels
   demonstrate repeatable advantages and per-photo calibration has authority.

No Cloud Run/Vertex AI/Inspect View credentials, weights, models or datasets
are changed. No third-party repository source or model checkpoints are imported.

## Multi-frame calibration security

`/api/v1/cv/measure/multi-frame` still accepts a legacy
`calibration_verified` form field for backwards compatibility, but explicitly
**ignores it for authorization**. To authorize any physical millimetre
calculations the request must include all of:

- `calibration_reference_id`
- `project_id` where the server record is project-scoped
- `camera_id` matching the validated camera/rig
- `calibration_source` and `pipe_diameter_mm` matching the server record

Only the server's `JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON` registry can
authorize this match, and only records supporting `CIRCULAR_OPENING` are
accepted by this currently circular-only burst endpoint. The detector must
also report authoritative mm and acceptable geometry for **every pixel-
accepted frame**; otherwise the entire burst stays pixels-only and in
review. A matching record alone does not guarantee a physically accurate
depth-dependent measurement or a field-validated calibration model.
