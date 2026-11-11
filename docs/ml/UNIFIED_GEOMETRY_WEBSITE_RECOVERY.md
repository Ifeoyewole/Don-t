# Unified geometry and existing website integration

## Implementation and primary units

The existing upload queue, inspection records, result page and JSON/PDF/evidence
ZIP exports now support the five-component research result. The normal measurement
workflow is unchanged. The existing results unit selector still initializes to
**mm**; px remains diagnostic and m remains an optional presentation conversion.
Unavailable physical measurements display:
“Measurement unavailable — calibration or reliable joint boundaries required”.

`joint_gap_recovery.py` reuses `experimental_rough_profile.py` and
`experimental_ellipse.py`. Seam cross-sections use two-sided image intensity
transitions with local SAM support, caption exclusion, coverage and stability
checks. Complete nested ring candidates additionally require observed dark-space
contrast between both image edges; ring/mask spacing is not an axial gap.
Existing geometry/fusion/calibration experiments remain available and unchanged;
their candidate outputs are not promoted merely because they returned a number.

SAM receives negative prompts for conservative caption candidates and records
its raw mask SHA plus excluded-pixel count. Original images are never inpainted.
Gemini receives the same image, masks and geometric evidence, is told not to use
burned-in labels as ground truth and may propose one bounded refinement. That
refinement segments only the proposed ROI, avoiding another full detector fanout.
Conflicting displacement/lateral versus opening hypotheses withhold a joint-gap
measurement. No unverified ISWDS class order is invented.

`unified_calibration.py` uses the existing server-owned registry. Physical mm
require matching reference, project, camera, source, image SHA, resolution and
supported geometry, plus independently verified joint-plane/axial direction.
Verified camera distortion and a joint-plane homography are applied where
provided. Already-rectified image coordinates require an explicit server-owned
record. No browser `verified` flag or nominal diameter grants scale. Circular
radial spacing cannot authorize axial mm without an independent depth model.
Research mm remain estimates with REVIEW_REQUIRED, never engineering PASS.
Repeatability MAD and known calibration uncertainty are reported separately.

## Real CCTV evidence and historical experiments

The frame10 original and actual mask from PR38 were SHA-verified and replayed
through geometry only: no SAM, classifier, detector or Vertex call was repeated.
The long caption was detected, and its mask intersection was excluded. The view
remains a partial curved joint step/socket with no defensible opposing axial
opening edges. Its mm and joint-gap estimate remain null. The former54 mask-band
cross-sections and11.894px median are descriptive mask thickness, not a gap.
The original artifact and prior reports remain unchanged.

Reproduce with:

```sh
python -m scripts.replay_joint_gap_recovery --frame-directory <existing-frame10-directory> --output <new-directory>
```

`docs/ml/ROUGH_BOUNDARY_PROFILE.md` documents the earlier127px case and explicitly
states its boundaries are intensity transitions, not verified material edges.
The current unit regression fixtures also contain127/134px values; those are
synthetic display contracts and must not be misreported as real measurements.
An original `pipe01image` file, a corresponding immutable source hash and a
verified image-specific scale were not located in the current repository or
available attachment/cache paths. A historical number alone cannot reproduce or
validate that case. No physical value was fabricated to replace the missing
source/calibration evidence.

## Website protection and data path

Existing Upload page → opt-in Unified engineering preview → `/api/unified` →
private Cloud Run `/api/v1/cv/sewer-research/unified` → original results page and
IndexedDB record → existing exports. The gateway uses the existing signed Secure
operator session from `/code`, not the anonymous public-product identity.
It verifies same origin, including HTTP/2 `:authority`, enforces upload/rate limits
and obtains an IAM ID token through existing Vercel federation. Tokens/keys never
enter the browser bundle. The private research backend independently verifies the
Google token's audience and allowed invoker email. The old backend token mode
remains unchanged for existing uses; the IAM mode is isolated and opt-in.

Reports retain the original source hash, all model evidence, real masks, overlay,
Gemini status, geometry rejection, calibration status and diagnostics. Research
records have `CLOUD_RESEARCH_UNVERIFIED` provenance. Optional known sequence ID
and original frame index can be entered per photo; upload order/filenames do not
establish video lineage. Frame consistency remains advisory; no temporal ground
truth or camera pose is fabricated. Raw video ingestion was not added.

JSON includes the unified report. PDF adds paginated unified interpretation and
the annotated image. Evidence ZIP adds unified JSON, overlay and mask PNGs.
Default mm remains unavailable until the server can support a physical estimate;
calibrated research estimates are distinct from authoritative production values.

## Verification and deployment boundary

`tools/verify-unified-site.mjs` starts local HTTPS, the actual existing React app,
the actual protected gateway and FastAPI with a recorded-real-artifact fixture.
It verifies anonymous401 rejection, original upload, request forwarding, source
hash, result persistence and JSON/PDF/ZIP export. Real Secure-cookie protection
is retained. Only the GCP execution transport is local replay; this does **not**
claim fresh cloud inference or a deployed engineering endpoint. Local TLS test
keys and private artifacts are outside Git. Browser screenshots and machine
verification evidence are saved by the runner.

Live deployment is prepared by `cloudbuild-unified-preview.yaml` and
`unified-preview.service.yaml`; neither is automatically executed by CI.
It needs one private CPU service, min0/max1 instance, concurrency1, a pinned image
and immutable research scope. The scope allows at most3 inspections/6 Gemini
requests, expires, reserves CPU work before model initialization, caches completed
identical responses and never automatically retries a failure. Scope-level model
request slots remain atomic. Request counts/timeouts are resource controls, not
a provider-enforced monetary cap or an invoice.

Read-only GCP discovery found only production `pipe-joint-api` and the existing
GPU controller; there is no deployed isolated unified-serving service. Existing
Vercel federation permits the production environment only. A branch preview must
not borrow/bypass that trust. One deployment option is enabling the operator-only
feature in the existing site's production environment while normal workflow and
authentication stay unchanged; this requires explicit approval for the feature
configuration and private service. Alternatively, a separate preview federation
identity can be reviewed later. No production settings, new cloud resources or
billable workloads have been changed by this development cycle.

The previous research runs exhausted their specifically approved request scope;
actual remaining billing balance is not available. New live deployment/inference
therefore requires a verified remaining authorization. Commercial permissions
remain separately documented and are not used as an intermediate engineering
review gate for software development.
