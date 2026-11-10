# Phase 1 real unified demonstration — 10 November 2026

**The integrated software path executed successfully on three real CCTV frames, including live authenticated Vertex Gemini. This is a working research demonstration, not engineering acceptance or proof that the missing defect classes are solved. Reliable axial joint-gap measurement remains unresolved.**

## What actually ran

One request per image exercised the same token-protected API:
`POST /api/v1/cv/sewer-research/unified` inside the GCP worker. Inspect View r5,
ISWDS proposals, actual SAM2.1 masks, OpenCV boundary evidence and Gemini were
combined into one JSON result and one annotated overlay. No synthetic model
outputs were used in these demonstrations. No public test endpoint was deployed;
the executable build and offline demonstration package are the handoff.

| Execution | Source | Actual result |
|---|---|---|
| Cloud Build `1a6e6667-72aa-45d9-960d-505534394eb9` | `2f35aef7fdcc5bdb02e6dbe97d7b17f7caf932a7` | Build process SUCCESS, integrated outcome PARTIAL_COMPONENT_FAILURE. Three Vertex requests returned HTTP400. Nine masks and partial results preserved; no automatic retry. |
| Separately approved recovery `2fe4c0e7-2dee-4993-8d79-7942c3bb0c3a` | `14dbc47d3e2c722152831d9e8d89b893a8e0aff1` | SUCCESS; all three images returned authenticated Gemini advisory evidence and completed the integrated component path. |

Both jobs used CPU e2-highcpu-8 in europe-west2. Original timeout 900s; approved
recovery 600s. There were six total provider attempts, three successful
interpretations, no automatic retries, no GPU, no training and no new container
build. The correction used Vertex's supported `responseSchema` subset instead
of forwarding the full library-generated JSON schema; strict local validation
remained intact. The original provider error body was not captured, so its
precise internal rejection reason is not established. The corrected request
succeeded. Subsequent offline hardening explicitly labels each supplied mask's
region ID, makes partial demo jobs exit nonzero and fixes mobile report overflow;
those changes do not replace the recorded live source commit above.

Existing immutable base container:
`europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/inspect-view-sam2-research@sha256:bf93efdab86558f29a708e2719bdf511953b2c26d87c6cc7b57612ab0b8f0304`.
Cloud Build source archive generation/hash and execution plans retain the exact
source snapshot. Dependencies added in the worker: ONNX Runtime 1.18.1 and
httpx 0.27.2. Checkpoints stayed inside GCP throughout.

## Real outcomes

| Frame | Task | Actual binary SAM2 masks | Gemini | Model path / Gemini+reconciliation / total seconds |
|---|---|---:|---|---|
| 10 | JOINT_GEOMETRY, provisional circular-opening ROI | 1 | Authenticated advisory | 13.695 / 26.726 / 40.478 |
| 26 | OBJECT_SEGMENTATION | 3 | Authenticated advisory | 12.373 / 26.001 / 38.380 |
| 34 | OBJECT_SEGMENTATION | 5 | Authenticated advisory | 20.168 / 31.481 / 51.655 |

These are single CPU observations on three unique images, not throughput
percentiles or an accuracy sample. Nine masks are region outputs on those three
images, not nine independent training examples. Timings exclude cloud startup,
package preparation and checkpoint staging. The first image's elapsed time
including worker initialization was 50.808s; the complete recovery script took
142.493s and the whole Cloud Build took273.510s. Process peak RSS was1,904,012KiB
(about 1.82 GiB). Build telemetry recorded 404.700 CPU-seconds and peak memory
utilization 0.30172 of its configured worker memory.

- **Frame10:** Gemini identifies a possible displaced joint and disagrees with
  r5's NORMAL flag. It also identifies mask contamination from burned-in text and
  debris. The text overlay itself describes joint offset; this is an annotation
  cue and possible model bias, not independent ground truth. Do not interpret
  agreement with the text as validation.
- **Frames26 and34:** Gemini returns possible PROTRUDING_LATERAL hypotheses and
  identifies protruding-object regions. The unified results explicitly mark
  those as visual hypotheses, not verified detector classes or confirmed defects.
  Source model scores and hypotheses remain separate.
- **Joint geometry:** frame 10 retains 54 original-coordinate opposing-mask edge
  samples. Their descriptive band-width median is 11.894 px, MAD 5.000 px,
  range 5.000–71.000 px. That is variable projected mask-band thickness, **not an
  axial opening or a reported joint gap**. It fails the stability requirement.
  All joint measurements correctly remain `joint_geometry_not_reliable` and all
  millimetre values remain null. No threshold was relaxed to turn it into a pass.
- **Gemini follow-up:** frame26 proposes another ROI. Recovery was deliberately
  limited to one reconciliation per image; this proposal was preserved but not
  executed. The one-additional-pass path is covered by offline regression tests,
  not represented as a live demonstration result.

Every decision is REVIEW_REQUIRED. No active groundwater infiltration was
confirmed. These are still frames with unverified source annotations and source
lineage; no engineer adjudication was manufactured.

## Baseline and specialist assessment

R5 remains unchanged. Its matched development comparison against r4 is F1
.4732/.4718 and F2 .5269/.5349; r5 improves matched joint-displacement F1
.9455 versus .9436 and NORMAL F1 .9326 versus .9206, while r4 retains the macro-F2
advantage. R3's native evaluation used different data/policy and is not a fair
replacement ranking. No new matched r3 inference was launched.

On these real demo frames, r5 NORMAL probabilities were .172666/.133831/.074792.
PROTRUDING_LATERAL probabilities were .000644/.000490/.000344, but that head is
UNVALIDATED: low output is not a measured false-negative result on a supported
class. Gemini wording that calls it a classifier failure remains advisory and
must be interpreted alongside the actual head support. Gemini can overstate
certainty and approximate source numbers in prose; the structured original
component values are the numerical evidence.

The one additional sewer model is the already-staged ISWDS RT-DETRv2 checkpoint.
Its real outputs remain numeric source IDs because no authoritative class map
was established for this export. It produced 3/2/5 retained detections across
frames10/26/34 at the unchanged .35 threshold. Source IDs 2/3/4/5/7 are not
silently mapped to canonical classes. It supplies useful exploratory proposals;
its contribution to correct defect recognition has **not** been demonstrated.
No generic detector or additional specialist was introduced.

Inspect View checkpoint SHA:
`659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`.
SAM2.1 Tiny SHA:
`7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`.
ISWDS RT-DETRv2 SHA:
`1afdfd5b1f39dcd9f927b3ac25662487d3ac2e7fe823d7322b1065a7e887bb3b`.
Gemini model: `gemini-3.1-pro-preview`, Vertex global. Signed receipts bind the
original image, complete evidence bundle, prompt/schema, issuer and model.
The existing isolated Secret Manager version 1 was used without exposing it.

OPEN_JOINT and PROTRUDING_LATERAL remain unvalidated model capabilities;
INFILTRATION remains unreliable. Gemini hypotheses do not turn them into trained
classes. Precision, recall, F1, IoU, Dice and accuracy improvement cannot be
calculated from this unadjudicated exploratory set. There is no 80% claim.

## Costs and operational limitations

The owner approved one research-only Vertex AI User binding for
`joint-inspection-trainer@joint-inspection-510310.iam.gserviceaccount.com`, then
separately approved the recovery build. Production identities, authentication,
deployments and checkpoints were not changed. Both jobs share the original USD5
internal reservation inside the USD100 cycle authorization; the reservation is
not an invoice or provider-side monetary kill switch.

Successful Gemini usage: 27,948 input tokens and 7,128 response+reasoning tokens.
At the checked [global on-demand rates](https://cloud.google.com/model-garden/pricing)
of USD 2/million input and USD 12/million output, the estimated API cost is
USD0.141432. Combined build runtime 447.910s at
[USD0.0156/minute](https://cloud.google.com/build/pricing) estimates USD0.116457
in CPU compute. Together this is **about USD0.26**, excluding storage, secret
operations, transfer and any charges associated with rejected requests for which
no token usage was returned. Actual billing and historical remaining balance
were not available; owner-confirmed headroom was the authorization basis.
This is an experimental-run estimate, not a production per-image price.

## Handoff artifacts and reproducibility

Successful outputs:
`gs://joint-inspection-510310-data/models/inspect-view/research-results/phase1/20261110T131131Z-11922bda/`.
Initial partial outputs:
`gs://joint-inspection-510310-data/models/inspect-view/research-results/phase1/20261110T130106Z-1d3eedd8/`.
Each preserves scope, execution plan, summary and per-frame original, overlay,
actual masks and complete unified report. No earlier objects were overwritten.

Recovery plan SHA:
`6194e5a11b2a06303ca72b21e8a98282badebbe43ff3a9eb9a45c3d4dde9c486`.
Original input SHA-256 values:

- Frame10: `c3e3dd5c91754100e66919b111bcf884421737193a958b5c4d43628be6ed382d`.
- Frame26: `9b381ebf3bb2893869586c535589c48cb70ff115c718df73489685c433a1bf47`.
- Frame34: `315297cff6a0f28da7d39b88a0c7088cbd30e6649ad374d53da2f7e9b359b38d`.

The engineering ZIP contains a static report (open `index.html`), originals,
annotated frames, masks, complete JSON, cost evidence and this report. It is not
an annotation/review workflow. Source code and executable configuration are in
PR#38. No public production model was replaced.

Verification: 362 backend tests, 39 frontend tests; frontend lint/build, Python
compilation and diff whitespace checks pass. Offline fixtures are explicitly
synthetic and separate from the real results above. Chromium verification loads
all 15 report images; responsive overflow found on the first mobile render was
fixed in the exporter. No training data or labels were modified.

## Engineering handoff conclusion

The first integrated demonstration is available now, including real segmentation,
real Vertex interpretation, disagreement handling and auditable pixel evidence.
The primary unresolved requirement is trustworthy opposing physical joint edges
and a stable joint-gap estimate; the current frames do not establish it.
Unsupported class recognition and numerical accuracy also remain unvalidated.
Engineers can assess these actual outputs and failures without waiting for more
training. This is readiness for prototype evaluation, not a declaration that all
Phase1 measurement requirements or engineering acceptance have been satisfied.
