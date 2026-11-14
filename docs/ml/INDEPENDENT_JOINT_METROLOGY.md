# Independent joint metrology recovery

## Corrected architecture

The existing website and private five-component preview remain intact. Image
seam geometry now reuses the original rough-boundary profiler independently of
classification and SAM availability. For a seam task, original-image proposals
(or an explicitly unverified full-frame search) produce a separate OpenCV region.
Each boundary pair is measured along a local normal intersecting the observed
edge polylines. Width outliers, caption candidates, inadequate coverage and
unstable widths are rejected. Overlays show both curves and cross-gap lines.
SAM-derived evidence remains available alongside the independent region.

Pipe/joint scene authorization, geometric evidence, defect hypotheses and
engineering acceptance are separate. A missing OPEN_JOINT prediction, NORMAL
classification or failed classifier no longer deletes a supported pixel
candidate. Gemini still checks scene suitability and provides advisory findings;
missing/invalid/unsuitable scene receipts cannot authorize physical mm. Existing
production routes, semantic gates, authentication and model weights are unchanged.
The system never defaults to NORMAL, PASS or a confirmed defect.

## Physical measurement limits

Mm remains the default. Existing server-owned, image-specific reference,
camera/project identity, original hash/resolution, joint plane, measurement
direction and rectification requirements remain enforced. The unchanged
calibration converter can produce research mm for supported seams when these
inputs and authenticated scene evidence exist. A synthetic end-to-end test now
exercises that path without SAM or a defect label; it is not field accuracy.

The currently deployed preview had no verified reference registry at inspection.
No actual camera calibration, measured reference span or rectification record was
supplied with these photos. No such data is invented or registered. Nominal900mm
and150mm are metadata, not image scale. The owner independently measured3–4mm on
the150mm pipe: retain it as a comparison range, never use it to force the output.
A single reference case cannot establish general measurement accuracy.

Circular projected spacing still cannot establish axial separation without an
independent depth model. Existing ellipse/circle diagnostics are preserved; this
change does not claim to solve that physical ambiguity or silently restore an
old diameter/image-width heuristic.

## Real-image comparison (CPU OpenCV only)

Reproduction:

    python -m scripts.compare_joint_metrology --image ORIGINAL.jpg \
      --geometry VERTICAL_SEAM --nominal-pipe-diameter-mm 900 --output OUTPUT

For the150mm curved seam use HORIZONTAL_SEAM and nominal150. Both the legacy detector
and the improved method see the identical original and full-frame search area.
Machine-readable reports preserve hashes, dimensions, every boundary pair,
variation, method and scope. These are unverified image-intensity boundaries;
shadows/socket lips can still be included. No trained model is executed by this
comparison script, no manual ROI approval is asserted and no accuracy score is
calculated without verified boundary annotations.

Initial supplied900mm concrete image: legacy seam detector rejected insufficient
boundaries; improved local-normal evidence approximately159px. Supplied150mm
photo: legacy detector rejected; improved diagnostic separation approximately
100px. These numbers describe selected image boundaries, not physical gaps.
Exact results and overlays are versioned with execution evidence.

## Website repairs

- Processing displays a named pending stage and elapsed seconds, not a fabricated
  upload60% while waiting on the cloud. Indeterminate progress is accessible and
  respects reduced motion. There is no invented per-model progress stream.
- Detailed reports use full-width cards with wrapping and contained images.
  Browser verification covers1440,980(desktop-mode width) and390px viewports.
- Unified pixel diagnostics are available to the existing unit selector even
  without legacy cvDebug data. Mm remains primary and null where unsupported.
- Region reports include method, accepted cross-sections, variation, scene status,
  component availability and physical rejection reasons. Empty defect findings
  explicitly do not imply a normal joint or PASS.
- The service worker no longer caches API health, capability or authentication;
  its shell cache version is advanced without deleting unrelated caches.
- Existing export schemas retain unified evidence, overlay and available masks.

## Deployment and cost controls

No new model, GPU or training. Existing CPU worker remains private, min0/max1,
concurrency1. A210-second request limit fits inside the240-second gateway and
245-second client limits, preventing the former120-second inner cutoff from
aborting normal cold starts. This is bounded execution, not an automatic retry.
The persistent cumulativeUSD100 ledger and all prior claims are retained. Daily
quotas remain absent. A remaining financial authorization check is required
before the single build and requested real cloud900mm inspection.

## Remaining validation

Obtain independently measured reference targets/camera geometry and per-position
boundary annotations; compare coverage, false measurements and error across
materials, normal joints, displaced joints, shadows and obstructions. Neither
passing software tests nor this exploratory two-photo comparison establishes
commercial measurement accuracy or complete defect coverage.
