# JointInspect Unified AI and measurement — full implementation report

Date: 11 November 2026. Repository: Ifeoyewole/Don-t. Project:
`joint-inspection-510310`, region `europe-west2`.

## Actual completion status

The five-component research inference path has run successfully on real CCTV
frames in GCP. The existing website can render, persist and export its unified
report. Joint-boundary recovery and server-authorized conversion to millimetres
are implemented and regression-tested.

**A reliable millimetre measurement on a real field joint has NOT yet been
demonstrated.** No supplied real demonstration frame had independently verified
joint-plane calibration and reliable opposing axial opening boundaries. Passing
software tests does not establish physical measurement accuracy.

The earlier statements that website integration was finished were too broad:
its upload/export flow had been verified with saved real artifacts, but fresh
inference through the deployed website had not been verified. The operator
sign-in requirement also prevented the intended no-sign-in experience.

## One coordinated inference path

Existing inspection upload → website gateway → private Cloud Run worker →
Inspect View r5 + ISWDS detection → candidate regions → SAM2.1 masks → OpenCV
boundary evidence → authenticated Vertex Gemini interpretation → at most one
targeted refinement → one unified result, overlay, record and export.

| Component | Implemented behavior | Evidence and limits |
|---|---|---|
| Inspect View | Existing ConvNeXt r5 checkpoint, preprocessing and class probabilities | Real CPU inference completed; predictions remain advisory |
| ISWDS | Existing RT-DETR v2 ONNX checkpoint; real boxes/scores in original coordinates | Real inference completed; source class-ID order is not independently verified, so no invented canonical label mapping |
| SAM2.1 Tiny | Actual prompted masks, original coordinates, raw-mask hashes and contamination diagnostics | Nine masks across the earlier three real frames; masks do not establish defect identity |
| OpenCV | Rough seam profiles, ellipse/ring audit, text exclusions, opposing image-edge pairing and stability rejection | Frame10 recovery correctly rejects ambiguous curved socket/step evidence |
| Vertex Gemini | Same original image, masks, model evidence and geometry; structured interpretation and signed evidence binding | All three earlier real frames returned authenticated advisory interpretation; Gemini cannot supply numeric measurements or engineering verdicts |
| Fusion | Preserves independent evidence, disagreements, source identity and provenance | One JSON/overlay; incompatible confidences are not averaged; REVIEW_REQUIRED remains distinct from engineering acceptance |

Existing Inspect View, ISWDS and SAM checkpoints are preserved. No new model,
retraining, replacement production weights or GPU experiment was introduced.

## Real cloud execution recovered from existing artifacts

Successful recovery build: `2fe4c0e7-2dee-4993-8d79-7942c3bb0c3a`.
Results:
`gs://joint-inspection-510310-data/models/inspect-view/research-results/phase1/20261110T131131Z-11922bda/`.

| Frame | Unified real path | Actual masks | Gemini | Total processing | Physical gap |
|---|---|---:|---|---:|---|
| 10 | Completed | 1 | Authenticated advisory | 40.478 s | null |
| 26 | Completed | 3 | Authenticated advisory | 38.3802 s | null |
| 34 | Completed | 5 | Authenticated advisory | 51.6551 s | null |

These are historical measured processing durations, not current website latency
or a throughput promise. Total including initialization/runner overhead was
142.493 seconds. Peak process RSS was 1,904,012 KiB. GPU count was zero.

This three-image functional demonstration does not establish precision, recall,
F1, IoU, measurement error or an improvement over r5. The records contain no
independently adjudicated ground truth for such metrics. Larger pilot and
held-out evaluation completion is not established by these artifacts.

The earlier frame10 Gemini explanation referred to burned-in CCTV label text.
That is an annotation cue, not independent confirmation. The updated prompt
explicitly prohibits using captions as ground truth.

## Geometry implementation and reuse

The unified path now calls `joint_gap_recovery.py`, reusing
`experimental_rough_profile.py` and `experimental_ellipse.py`. The earlier
experimental geometry/fusion modules and production calibration authority remain
preserved. Not every experimental candidate is promoted into a measurement.

Implemented checks:

- Conservative bright-caption candidates near frame borders; original image
  pixels are retained, not inpainted.
- SAM negative prompts and exclusion of caption-contaminated mask pixels.
- Two-sided image-intensity boundary profiles supported locally by segmentation.
- At least sixteen accepted pairs and sixty-percent sampling coverage.
- Rejection of exclusion-crossing pairs and unstable width distributions.
- Elliptical/projected-ring evidence kept separate from physical axial gaps.
- Gemini scene corroboration and conflict handling before a gap is promoted.
- One targeted ROI refinement, without an uncontrolled analysis loop.
- Same-size, same-joint frame context where supplied; declared sequence identity
  remains unverified and is not manufactured from filenames/upload order.

These checks reduce invalid candidates; they do not prove that every dark band
is an opening. Shadows, sockets and offset joints can remain unmeasurable.

### Frame10 geometry replay

Original SHA-256:
`c3e3dd5c91754100e66919b111bcf884421737193a958b5c4d43628be6ed382d`.
The original image and raw saved mask hashes were checked before geometry replay.
The replay made no new SAM, detector, classifier or Gemini request.

- 1,885 mask pixels intersected conservative caption exclusions.
- Rejection: `CURVED_JOINT_STEP_OR_SOCKET_NOT_IDENTIFIABLE_AS_AXIAL_OPENING`.
- Joint-gap pixels: null. Physical gap mm: null.
- Required evidence: opposing actual opening edges and an independent view or
  adjacent frames resolving depth/perspective.

The old 11.894 px median described mask-band thickness. It is not a physical
joint separation. Earlier 127–134 px rough-profile values similarly cannot be
promoted into millimetres or field ground truth. The original `pipe01image`
source/hash and corresponding verified calibration were not recovered in the
available repository, attachments or cached result inventory.

## Millimetres and calibration

**mm remains the primary/default engineering unit.** Optional metres are a
presentation conversion. Pixels are diagnostic, not a substitute default unit.

`unified_calibration.py` reuses the server-owned calibration authority and requires:

1. Matching reference, project, camera, source, geometry, image hash and resolution.
2. Independently verified joint plane and axial measurement direction.
3. A supported physical reference, test rig or camera-calibration source.
4. Explicit already-rectified coordinates, or verified camera intrinsics,
   distortion coefficients and a valid joint-plane transform where required.
5. Stable transformed opposing edge pairs.

The transformation is applied to actual edge points before the distance-to-mm
conversion. Repeatability MAD and supplied calibration-scale uncertainty are
reported separately. No synthetic field uncertainty is invented.

A nominal pipe diameter, selected pipe size or browser `verified` flag does not
grant physical scale. Camera/reference geometry must match the measurement plane.
Projected radial ring spacing is rejected for axial-mm conversion without an
independently supported axial depth model.

Where evidence is insufficient:

`physical_gap_mm = null`

“Measurement unavailable — calibration or reliable joint boundaries required”.

A known-scale synthetic regression produces approximately 6 mm and verifies the
full software handoff. This proves the conversion contract, **not real CCTV
measurement accuracy**. Research mm, when supported, remain estimates and cannot
become an automatic production PASS.

## Website, records and exports

The existing upload page, queue, results page, IndexedDB records and JSON/PDF/ZIP
exports carry the unified evidence. The report includes model findings, actual
masks, overlay, geometric pairs/rejections, calibration status and Gemini analysis.
The normal inspection path and existing records are preserved.

`/code` is retired and redirects home. `/api/code` returns 410 and cannot dispatch
GitHub or GCP commands. The unwanted sign-in form is being removed; the session
login endpoint is retired. No user password should be required in the product.

For the currently authorized demonstration, no-sign-in access is limited to the
existing immutable allowance ending **2026-11-11 10:31:35 UTC**. The gateway must
be explicitly enabled for that exact one-time window. A changed/future timestamp
does not silently authorize anonymous paid inference. Private service IAM,
same-origin POST checks, upload/rate limits and the persistent worker allowance
remain enforced. Expiry is not extended by this change.

The website accesses Cloud Run using server-side workload identity. This service
authentication is distinct from user sign-in and remains necessary to keep model
credentials and the worker private.

## Cloud deployment and spending

- Preview service: `jointinspect-unified-preview`, revision `00002-2cb`.
- Preview image build: `67818966-fe2c-43bd-a8a4-0058fa703b01`, SUCCESS.
- Immutable image: `sha256:e60fc54559743ed4ccd8ccc5af079baa38ea0cd293a4017906243fd0c5948c56`.
- Backend source: PR39 merge `4764717ce4ee12bac80e6e1abdaa1813b6dc9468`.
- CPU2, memory4GiB, min0/max1 instance, concurrency1, no GPU.
- Existing production model service remains `pipe-joint-api-00015-fej`.
- Existing website deployment after PR41: `dpl_94KzGCCixSMiSYpKgpo76pyCdBt3`.
- Current research prefix:
  `gs://joint-inspection-510310-data/models/inspect-view/research-results/engineering-preview/20261111T083135Z/`.

The shared allowance is at most three inspections/six Gemini attempts, including
optional refinements. Persistent create-only claims precede model work; failed
or uncertain executions are not automatically repeated. Successful identical
requests reuse stored responses. At the report's initial inspection, only scope
and deployment report objects existed: no new inference claim was present.

USD5 was authorized within the user's USD100 cycle ceiling. Actual billing-account
charges are not readable here. Neither an estimate nor an application request
limit is a provider-enforced monetary billing cap.

## Verification and remaining work

Earlier final backend regression suite: 378 passed. PR41 verification: 49 frontend
and gateway tests, native emitted-Node import test, lint and build passed. Local
HTTPS browser verification exercised actual inline sign-in, inspection replay,
record persistence and all three export formats; that sign-in behavior is now
superseded by the user's no-sign-in directive. The replacement no-sign-in browser
replay and final deployment results are recorded in the delivery update below.

Outstanding substantive work:

- Fresh website-to-cloud inference verification after removing the login obstacle.
- Real CCTV with a verified joint-plane physical reference and independently
  measured gap, followed by error/uncertainty analysis.
- Unambiguous source class definitions for this ISWDS checkpoint.
- Independently labelled, family-disjoint benchmark data for the three weak classes.
- Robust temporal joint tracking/measurement fusion on an actual sequence; current
  prior-frame evidence support is not a validated multi-frame metrology system.

OPEN_JOINT and PROTRUDING_LATERAL are not verified supported classes merely because
heads/hypotheses exist. INFILTRATION remains unreliable; active infiltration cannot
be confirmed from one still image. None has a measured new accuracy improvement.

The next measurement milestone is a known-reference real joint case, with its
opposing physical edges visible and its true gap independently measured. That
can validate or falsify the implemented mm path without retraining or another
model.

## Delivery update

PR42 merged as `0535c898693fab5c776c394740309be4a246a33f` and deployment
`dpl_6enucjaPAk1tzq41qHvnPszxmsWV` is READY. The live browser reached the
inspection upload and submitted frame10 without an operator cookie or password.
The user-facing sign-in form is removed, and the session endpoint is retired.

The first new request exposed a real timeout defect: the gateway stopped waiting
after110.601 seconds (HTTP502), while Cloud Run completed at116.005 seconds with
HTTP200 and saved the complete result. Therefore that initial website attempt
was **not** a successful end-to-end display.

The saved real result has all three models available, two real SAM masks,
authenticated Gemini advisory interpretation, and `functional_path_complete=true`.
Inference/fusion took78.55 seconds; the116.005-second request also included
initialization/transport overhead. There were two bounded analysis passes.
Millimetres remain null, with `joint_geometry_not_reliable` and unverified
calibration. No physical measurement or accuracy improvement is claimed.

Saved result:
`gs://joint-inspection-510310-data/models/inspect-view/research-results/engineering-preview/20261111T083135Z/responses/ac2dac58544b431fb9874b44690b9634ab998c47afaed943ed2694fdc227e539.json`.
One inspection slot and two Gemini slots were consumed; two inspections/four
Gemini attempts remain at this observation. No inference was automatically retried.

The website-only recovery increases its network wait from110 to240 seconds,
client wait from115 to245 seconds, and Vercel function ceiling to300 seconds.
**Cloud Run's120-second request bound, CPU, instance limit, immutable scope,
expiry and spending allowance remain unchanged.** The change accommodates the
observed116-second successful cloud response; it does not extend cloud execution.

Fresh website readback and final delivery verification are recorded after the
recovery deployment. A saved, hash-matched response can be read back without
repeating model work.
