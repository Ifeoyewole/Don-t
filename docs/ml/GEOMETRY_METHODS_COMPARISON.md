# JointInspect geometry methods: independent comparison (research branch)

**Scope:** Compare published methods with JointInspect's own implementation,
then develop original, minimal alternatives. **No copying, cloning, vendoring,
model weights, sample footage, or imported third-party project source.**

Date: 2026-11-07. Primary production branch examined:
`Ifeoyewole/Don-t@3d696bf`.

## What we inspected (technical reference only)

| Technical reference | Relevant method | Existing JointInspect behavior | Proposed ORIGINAL improvement |
|---|---|---|---|
| [Co-UDlabs camera calibration](https://github.com/Co-UDlabs/sewer_defects/tree/coudlabs/coudlabs/src/camera_calibration) | Checkerboard calibration from multiple known-size target views; optional labelled box references | `CameraCalibrator` undistorts using stored intrinsics, with example camera profiles | Separate, strictly advisory **reprojection error/coverage audit** of real camera calibration captures; never assert that camera was calibrated just because a nominal diameter exists |
| [Co-UDlabs size estimation](https://github.com/Co-UDlabs/sewer_defects/blob/coudlabs/coudlabs/src/object_size_estimation/distance_and_size.py) | Attempts image-space reference-object size ratios and focal length | Server-owned physical calibration record required; nominal diameter is NOT scale | Preserve JointInspect's stricter authority. Do **not** transfer reference sizes across unmatched depths/planes. Do not copy equations without validating camera geometry |
| [scikit-image measure docs](https://scikit-image.org/docs/stable/api/skimage.measure.html) | Contours, ellipse/line fitting, robust inlier estimation via RANSAC | Current seam detector finds top gradient peaks and applies ROI + width bound, but can still pair unrelated edges inside ROI | Independent dark-band method requiring **two-sided contrast, continuity, width consistency and localized ROI**. Currently implemented using existing OpenCV/NumPy; no new dependency |
| [OpenCV geometry](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html) | Contours, fitting circles/ellipses, shape checks | Circular detector already uses HoughCircles with a contour/min-enclosing-circle fallback | Experimental elliptical boundary fitting with coverage, residual and nested-ring checks on off-axis views; NOT production and NOT a measured axial gap |
| [SAM 2](https://github.com/facebookresearch/sam2) | Promptable segmentation in still images and video | Experimental segmentation is already present; lacks validated edge/scale accuracy for all pipe types | Future optional assist for inspector-selected ROIs and multiple video frames **only after** cost/latency and contour accuracy benchmarks; no checkpoint imported |

### Specific JointInspect shortcomings

1. **A contrast peak is not automatically a pipe-joint edge.**
   `seam_detector.py` selects candidates by edge gradient magnitude, which can
   include concrete texture, shadows, debris, or wall boundaries. Existing
   25%-of-ROI cap prevents huge pairings, but cannot by itself prove the
   boundaries are a joint.
2. **Cropped/angled rings are not necessarily concentric circles.**
   `circular_detector.py` uses Hough circles and a contour-circle fit;
   true projected openings can appear elliptical. We need a validated ellipse
   or perspective-specific alternative; do NOT treat ring diameter as axial
   joint separation from a single image.
3. **Nominal diameter is not physical pixel scale.**
   `calibration_authority.py` correctly checks server-owned project/camera/
   geometry reference metadata. The research reprojection audit is an
   additional diagnostic, not a substitute for that authority.
4. **Domain is larger than 'open joint'.** JointInspect should retain distinct
   geometry/evidence policies for cracks, laterals, open joints, infiltration,
   protrusions, deformity, roots and unexpected pipe structures. An unsupported
   class should show REVIEW, not be forced into a 3-geometry measurement.

## Implemented experiments (not in production measurement path)

- `backend/app/core/cv/experimental_geometry.py`:
  original dark-band seam candidate from a supplied ROI; cross-scanline
  two-sided brightness check, robust centerline fit, MAD-like width dispersion,
  and reasoned rejection. It returns **pixel candidates only**, never mm, PASS
  or a defect label. Comparison with the production detector is explicit.
- `backend/app/core/cv/experimental_ellipse.py`: original ROI-constrained ellipse fitting using existing OpenCV contours. Requires angular boundary coverage, low fit residual, compatible center/axes/orientation for nested rings. Returns **projected ring evidence**, NOT axial joint separation, mm, defect class or PASS. An ordinary socket, liner or distant opening may produce nested ellipses.
- `backend/app/core/cv/experimental_fusion.py`: combines independently localized
  ROI candidates (inspector, Inspect View, Gemini, CV mask) PER FRAME.
  The proposals are passed to the library by a caller; the library does
  **not** request or infer model coordinates on its own. It tracks source,
  rejects missing/invalid proposals, and handles **both** seam and projected
  ellipse evidence. Partial elliptical arcs are marked provisional; two
  distinct nearby frames from one video must agree on normalized projected
  geometry before they count as temporal evidence. Duplicate frames and
  brightness-only rewrites are rejected using image/edge fingerprints.
  Even corroborated projected rings are NOT measured axial joint gaps.
- `scripts/benchmark_fused_geometry.py`: run a short local inspection sequence
  with per-frame ROIs from any supported source; produces JSON evidence without
  uploading image bytes. Sample manifest and usage appear in its docstring.
- `backend/app/core/cv/experimental_calibration.py`:
  multi-view calibrated-target reprojection residuals with minimum view count,
  finite input checks and per-view quality threshold. Returns **review
  evidence**, never a trusted calibration record.
- `backend/tests/test_experimental_geometry_comparison.py`:
  synthetic positive, negative, mislocalized, huge-gap and calibration-fit
  checks using original generated arrays, not external project images.
- `scripts/benchmark_ellipse_geometry.py`: paired **circle vs ellipse** local benchmark. Both read the same ROI, and human ground truth is whether paired ring boundaries are visible—not whether an open-joint defect exists. Outputs labelled positive detections and false pair detections; no mm or photos published.
- `scripts/benchmark_shadow_geometry.py`: local-only paired benchmark on
  consented images and inspector-supplied ROI/ground truth; reports positive
  coverage, false gap claims on negatives and pixel MAE on measured positives.
  No cloud upload and no production inference change.

**This is not a production AI-ROI integration**: the current Gemini semantic
gate does not provide a validated bounding-box API for every geometry, and
Inspect View is not validated for Open Joint. To wire live localization, a
separate typed bounding-box contract, scale normalization and tests are
required. The fusion work consumes explicit per-frame proposals as input.

**No dependency added** to backend requirements, no third-party algorithms
copied, no existing measurement response schema modified, no GCP deployment.

## Release gates before any production use

1. Source independent **site/pipe/video-family holdout** examples from
   footage that your organization is permitted to evaluate. Include rough
   concrete seams, brown/dark plastic joints, changing camera angles, roots,
   laterals, wet surfaces, debris, glare, circular and non-circular interfaces.
   Do not put raw operator footage in GitHub Actions artifacts.
2. Inspector supplies known *pixel* boundary reference and explicit ROI for
   every comparison. Do not infer ground truth from Gemini or the current CV
   estimate. Negative examples must include known non-gap shadows.
3. Compare candidate coverage **and** false-positive rate and paired MAE on
   the exact same labeled examples; report per material, camera and geometry.
   If results are inconclusive, keep research mode rather than changing live
   outputs. No accuracy guarantee based only on synthetic tests.
4. Compare ellipse-specific failures: side laterals mistaken for pipe joints, nested pipes at different depths, cropping, obscuring deposits, noncircular pipes, tiny lenses, blur, undistortion and different camera pitch. An ellipse pair is *not* an Open Joint label and projected semiaxis spacing is *not* axial separation. Reprojection fit/geometry still need review.
5. Validate separate physical scale using controlled camera targets and depth/
   pose reference. A good reprojection RMS does not by itself prove an axial
   gap can be measured in mm in a different image.
6. Partial-arc temporal votes require independent frame geometry—not merely
   rewritten JPEGs or brightness-adjusted duplicates. Even correctly linked
   frames are correlated evidence, not independent field ground truth. Inspect
   how far the camera moved and whether parallax supports the same physical
   interface. Videos of a side connection may still show nested rings without
   any defective mainline joint.
7. Any future production ensemble must fail-closed on disagreement, missing
   ROI or unsupported geometry, and must not introduce measured mm without
   trusted calibration and adequate geometry.

## Licensing clarity

This branch only **reads and compares** external methods. Co-UDlabs' repository
LICENSE includes commercial use with attribution but its README has an
'Academic' badge and bundles other code with separate licensing. JointInspect
does not import/clone their code, model weights, data or embedded Ultralytics.
The underlying math/algorithms are general techniques, implemented here
independently using JointInspect's existing OpenCV and NumPy dependencies.
