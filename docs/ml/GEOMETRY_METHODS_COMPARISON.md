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
| [OpenCV geometry](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html) | Contours, fitting circles/ellipses, shape checks | Circular detector already uses HoughCircles with a contour/min-enclosing-circle fallback | Next research experiment: elliptical boundary coverage/residuals on off-axis views, tested against inspector-labelled rings before replacing circular detector |
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
- `backend/app/core/cv/experimental_calibration.py`:
  multi-view calibrated-target reprojection residuals with minimum view count,
  finite input checks and per-view quality threshold. Returns **review
  evidence**, never a trusted calibration record.
- `backend/tests/test_experimental_geometry_comparison.py`:
  synthetic positive, negative, mislocalized, huge-gap and calibration-fit
  checks using original generated arrays, not external project images.
- `scripts/benchmark_shadow_geometry.py`: local-only paired benchmark on
  consented images and inspector-supplied ROI/ground truth; reports positive
  coverage, false gap claims on negatives and pixel MAE on measured positives.
  No cloud upload and no production inference change.

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
4. Validate separate physical scale using controlled camera targets and depth/
   pose reference. A good reprojection RMS does not by itself prove an axial
   gap can be measured in mm in a different image.
5. Any future production ensemble must fail-closed on disagreement, missing
   ROI or unsupported geometry, and must not introduce measured mm without
   trusted calibration and adequate geometry.

## Licensing clarity

This branch only **reads and compares** external methods. Co-UDlabs' repository
LICENSE includes commercial use with attribution but its README has an
'Academic' badge and bundles other code with separate licensing. JointInspect
does not import/clone their code, model weights, data or embedded Ultralytics.
The underlying math/algorithms are general techniques, implemented here
independently using JointInspect's existing OpenCV and NumPy dependencies.
