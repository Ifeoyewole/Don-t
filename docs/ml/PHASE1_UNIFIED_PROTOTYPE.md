# Phase 1 unified research prototype

One authenticated API: `POST /api/v1/cv/sewer-research/unified`. The existing
token check and default-disabled feature remain intact. In an isolated cloud
worker, setting `JOINTINSPECT_PHASE1_VERTEX_ENABLED=true` selects the integrated
Inspect View r5 → ISWDS proposals → SAM2 masks → OpenCV boundary evidence →
authenticated Vertex Gemini interpretation path. No production deployment,
authentication change or checkpoint promotion is required.

## Implementation

`Phase1Unified` reuses `SewerFusion` and its cloud loaders. All models use original
image coordinates and an image SHA-256. Independent classifier probabilities,
detector scores and SAM quality values remain separate; they are never averaged
into a synthetic confidence score. Gemini sees the original, overlay, actual
masks, component results, pixel geometry, advisory metadata and available prior
frame evidence. A strict schema rejects extra measurements/confidence fields,
unknown region references and invalid proposals. Signed results bind the model,
prompt/schema, source image and complete evidence bundle. The existing semantic
receipt contract is reused for scene gating. Authenticated model output is still
advisory, not engineering authority.

Gemini may propose one additional original-coordinate region. At most one
targeted segmentation pass and one subsequent reconciliation are permitted.
Atomic GCS claims survive provider failures, and scope-wide request slots bound
changed bundles as well as repeated images. Valid receipts are reused; failed,
invalid, expired or already-claimed requests are not automatically charged again.
Production semantic-gate settings and singleton state are untouched.

Seam evidence reuses the existing two-sided intensity profile, with SAM spatial
support checked at multiple cross-sections. Partial annular masks additionally
support opposing-mask-boundary samples along distance ridges. Projected ring
spacing, mask-band thickness, dark-band width and verified axial gap are different
quantities. Every sample is retained with its endpoints and pixel units. Only
joint-suitable mask assessments and an authenticated joint scene can expose a
preliminary boundary candidate. The prototype does not establish physical scale:
millimetres stay null, including when nominal pipe diameter is supplied. Real
calibrated measurements remain the responsibility of the existing production
calibration-authority path; this research route does not accept authority flags.

Sequential frames retain bounded, caller-declared context. Pixel consistency is
checked only for nearby distinct images with matching geometry and overlapping
regions; this does not verify original video lineage or establish active ingress.
Component failures retain usable independent evidence with REVIEW_REQUIRED.

## Model selection and limitations

R5 remains the existing baseline. The matched 679-image r4/r5 development result
is F1 .4718/.4732 and F2 .5349/.5269, respectively. R5 does not dominate r4. R3's
native score used a different dataset/policy and cannot justify replacing r5.
The saved results are development evidence, not independent engineer validation.

Only one additional sewer model is used: the already-staged ISWDS RT-DETR v2
checkpoint. Real CPU execution is established, but its export omits class-name
metadata. Numeric IDs remain unmapped; the pipeline does not borrow another
checkpoint's order or claim new open-joint/lateral support. No verified deployable
alternative weights were established by the preceding investigation. SAM masks
and Gemini hypotheses improve evidence availability, not measured class accuracy.
OPEN_JOINT and PROTRUDING_LATERAL remain unvalidated; r5's saved infiltration
development recall is 0/6. No training or threshold tuning is included.

## Isolated execution

`scripts/cloud/phase1_demo.py` exercises the same authenticated FastAPI route on
up to three existing GCS frames, with SHA-pinned inputs and plan. It writes
originals, real masks, an annotated overlay, unified JSON and a runtime summary
to a unique private GCS prefix. It never downloads weights to an operator PC.
The source archive is independently pinned by Cloud Build; the reused container
digest is `bf93efdab86558f29a708e2719bdf511953b2c26d87c6cc7b57612ab0b8f0304`.
`cloudbuild-phase1-demo.yaml` uses CPU e2-highcpu-8, 900-second maximum, no GPU,
no automatic retry and the existing research trainer. Live execution requires a
server-provisioned, SHA-pinned scope and existing numeric Secret Manager version.
The scope limits this demonstration to six Gemini requests and a USD5 internal
reservation within the owner-authorized USD100 research cycle. Reservations are
not actual charges or provider-enforced monetary limits.

The owner explicitly approved the research trainer's Vertex AI User grant on
10 November 2026. No production principal or authentication configuration was
changed. Source labels and research quarantine remain preserved; development
execution does not establish commercial clearance or annotation adjudication.

## Verification and handoff

Offline tests cover multimodal evidence handoff, signature/cache integrity,
request caps and timeout deduplication, ROI validation, a bounded second pass,
partial failure, pixel edge samples and no fabricated millimetres. Synthetic
fixtures in those tests are never demonstration outputs. Actual cloud outcomes
belong in `PHASE1_DEMONSTRATION_RESULTS.md`, after execution; passing tests alone
does not complete Phase 1. Engineer acceptance, accuracy improvement and verified
physical joint-gap measurements must not be claimed from exploratory cases.
