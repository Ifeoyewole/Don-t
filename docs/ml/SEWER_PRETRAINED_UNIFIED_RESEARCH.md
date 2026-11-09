# Sewer pretrained model integration — research only

Status: implementation and synthetic contracts complete; real-checkpoint validation and benchmark pending. This is not a trained release, a production deployment, or evidence of improved detection accuracy.

## Source review (9 November 2026)

| Candidate | Public checkpoint evidence | Inference and classes | Rights and decision |
| --- | --- | --- | --- |
| [ISWDS](https://huggingface.co/mogurlu/Istanbul_Sewer_Defect_Dataset_ISWDS_Models) | Public ungated repository; immutable revision `ffe32890eee1fba794d7a22486289562b118e574`; RT-DETR v2 ONNX 103,295,200 bytes, published LFS SHA-256 `1afdfd5b1f39dcd9f927b3ac25662487d3ac2e7fe823d7322b1065a7e887bb3b` | Sewer-trained detector; published classes include infiltration and displaced joint. ONNX is the simplest box-to-SAM bridge. | Explicit Fair Non-Commercial Research License: commercial use prohibited. Selected **only as an isolated research comparator**, subject to permitted noncommercial usage. |
| [SFR-Net](https://github.com/infinitycan/SFR-Net) | README links a Sewer-ML ViT-B/16 checkpoint on Google Drive and Baidu. Drive responds with a download redirect; binary availability/checksum not independently validated. | Multi-label zero-shot classifier, not a localized detector; needs CLIP, text descriptions and its custom pipeline. Publisher benchmark numbers are not JointInspect results. | No clear licence file found in repository root. Not selected; permissions unresolved and localization requires another unverified proposal method. |
| [MultiLabel SewerDefect SSL](https://github.com/tubayildizli/MultiLabel_SewerDefect_SSL) | Official DOI resolves to [4TU version 2](https://doi.org/10.4121/1c21ce33-715f-4ca0-89fa-c170b30801ff.v2), publishing 5,301,264,060 bytes of weights/supporting data. | 17-head ResNet101 classifier; official evaluation uses 224x224 RGB and mean `[.523,.453,.345]`, std `[.210,.199,.154]`. No localized boxes. | Archive explicitly CC BY-NC-SA 4.0. Not selected; noncommercial restriction and overlap with existing r5 classification role. |

A bounded metadata inspection of the alternative ISWDS YOLO11m export confirmed embedded Turkish class names, but also an explicit AGPL-3.0 model licence. Its class IDs cannot establish RT-DETR class order; its additional licence obligations make it unsuitable as a shortcut around the selected model’s mapping/rights checks. It was inspected only, not integrated or executed.

This is a choice based on practical checkpoint and interface evidence, **not a measured ranking of model accuracy**. None of these sources currently establishes a commercially deployable additional checkpoint for JointInspect. Do not reinterpret availability as commercial permission. No selected model weights have been downloaded to a developer workstation.

## Implementation

- `research_sewer_detector.py`: a single ISWDS RT-DETR v2 adapter. Hash-checks cloud-staged weights, reads ONNX graph label metadata where present rather than assuming model-card row order, checks the input and output contract, performs scale-fill RGB preprocessing and suppresses same-class duplicate boxes. The selected postprocessed export receives original `[height,width]` to return original-image absolute XYXY boxes. A separately tested raw-export path converts normalized cx/cy/w/h into original-image boxes. Confidence and region limits are bounded.
- Actual selected export interface was checked through a bounded 32 KiB remote metadata tail and a 1 KiB shape check, without downloading full weights: float32 `images=[N,3,640,640]`, int64 `orig_target_sizes=[N,2]`, outputs `labels`, `boxes`, `scores`. Adapter handles this postprocessed absolute-box contract and dynamic batch axis at batch size one. The tail exposes no class-name metadata; such detections remain `UNVERIFIED_SOURCE_CLASS_ID_n` with no canonical class claim. Do not invent a class-ID map from the README table. An alternative raw `[1,N,12]` export is accepted only with graph-embedded class names. Full ONNX Runtime execution, preprocessing parity and numerical box validation on the real checkpoint remain pending.
- `research_sewer_fusion.py`: r5 classification, detector proposals and explicit ROIs, existing SAM2 mask adapter, contour-based region extents, optional signed Gemini evidence and one research result. It retains raw independent component evidence and disagreements instead of averaging scores.
- `research_sewer_runtime.py`: project-bucket-only, generation-pinned/checksum-verified staging inside a dedicated cloud worker. Reuses the existing r5 loader/preprocessing/checkpoint and SAM2 loader. Independent startup failures retain the remaining components.
- `/api/v1/cv/sewer-research/unified`: multipart `file` plus JSON `options`. Disabled by default, authenticated with the existing preview token. No changes to production measurement/calibration routes, authentication or model weights. Do not expose this noncommercial component through the commercial product.
- `sewer_unified_worker.py`: at most three frames from a strict, hash-bound, legitimately reviewed manifest. Create-only original bytes, reports, actual mask PNGs, overlays and baseline comparisons. Never submits cloud jobs, retries or invents an approval.
- Cloud-only acquisition script pins the publisher revision, byte length and SHA. It requires a documented usage permission record, leaves the checkpoint in research quarantine, and never grants commercial rights. It has not been executed.
- New isolated Docker/Cloud Build configuration extends the successful research image by immutable digest and pins ONNX Runtime `1.18.1`. No RF-DETR package, checkpoint, dependency or loader is retained.

Example authenticated request, against a separately authorized research worker only:

```text
POST /api/v1/cv/sewer-research/unified
Authorization: Bearer <existing secret>
file: original image
options: {"task":"OBJECT_SEGMENTATION","rois":[[42,109,375,248]]}
```

Optional options: `sequence_id`, `frame_index`, `receipt`; `geometry` is allowed only for `JOINT_GEOMETRY`. Client input cannot grant calibration or production authority.

## What the evidence means

- Detection labels are taken from graph metadata. Unknown source names are preserved and left unmapped. Exact English source names have explicit, provisional canonical mappings; no class IDs are guessed.
- `Displaced Joint` is not `OPEN_JOINT`. `Intruding Sealing Material` is an obstacle candidate, not `PROTRUDING_LATERAL`. Composite cracks/breaks/collapses remain unmapped rather than becoming fabricated broken-pipe positives.
- ISWDS infiltration scores remain visual research candidates. Repeated boxes or a still image do not prove active water ingress. The bounded temporal association uses original-frame IoU and monotonically increasing indices, rejects replays, and never certifies video lineage or active infiltration. It does not implement SAM2 video-mask propagation.
- SAM2 outputs actual same-frame binary masks. Target identity remains unverified; contour extent and area describe the selected mask, not intrusion depth or a joint gap.
- Existing rough joint geometry runs only for an explicit ROI with a supported geometry and an authenticated, same-image, unexpired, trusted Gemini joint-domain receipt. Automatically proposed boxes do not acquire geometry approval. Nonjoint tasks never call joint geometry.
- Gemini is optional and advisory. This path issues no paid Gemini requests. Missing or rejected receipts cannot authorize joint measurements. No component returns engineering PASS/FAIL or physical millimetres; verified physical measurement remains the existing calibrated production pipeline's responsibility.

## Configuration and rollout

Keep `JOINTINSPECT_SEWER_FUSION_ENABLED=false` in production. A separate permitted research worker needs:

- `JOINTINSPECT_CLOUD_RESEARCH_WORKER=true`
- `JOINTINSPECT_ISWDS_NONCOMMERCIAL_RESEARCH_ALLOWED=true`, backed by an actual permission record; an environment variable cannot establish legal permission.
- `JOINTINSPECT_RESEARCH_R5_URI`, `JOINTINSPECT_RESEARCH_SAM_URI`, `JOINTINSPECT_RESEARCH_SEWER_ONNX_URI`, all in the project models prefix and matching pinned hashes.
- Optional `JOINTINSPECT_RESEARCH_HMAC_SECRET_RESOURCE`, using the existing isolated research Secret Manager numeric version. Never commit its value.
- Existing preview token via secret injection for HTTP access; do not change production authentication.

Use `cloudbuild-sewer-unified-research.yaml` only after remaining authorized funding is established. Run a separately reviewed manifest using `python -m scripts.cloud.sewer_unified_worker --manifest-uri ... --manifest-sha ... --review-uri ... --review-sha ... --output-prefix ...`. Use one bounded worker, no automatic retries, immutable image digest, unique private output prefix and existing project IAM. Do not rebuild or launch paid jobs automatically.

The existing USD100 authorization includes all previous usage. Actual accumulated charges are not yet established, so **no new paid build, GPU job, Gemini call or training was submitted for this implementation**. The earlier research image is reused as a configuration base, not claimed to already contain this new implementation.

## Baseline comparison and weak classes

The unified response contains the exact same r5 payload, additional detector region count, actual mask count and an explicit null accuracy improvement. This permits paired comparisons on identical images without changing r5.

| Question | Current evidence |
| --- | --- |
| Does r5's baseline remain intact? | Tested with source-hash-bound synthetic payloads; existing full backend regression suite also run. |
| Can a sewer detector box drive SAM2 masks and pixel evidence? | Synthetic ONNX/session and predictor contracts exercise the complete API; this is software verification, not a pretrained-checkpoint benchmark. |
| Have the three reviewed pilot images been inferred with ISWDS? | No. No approved pilot rows found in GCP; noncommercial usage scope and real export compatibility also need validation. |
| Have OPEN_JOINT / PROTRUDING_LATERAL improved? | No measured improvement; selected model does not establish these classes. |
| Has INFILTRATION improved? | No measured improvement. A sewer-trained visual candidate pathway is implemented, but no held-out, independently adjudicated benchmark has run. |
| Is this commercially deployable? | No. Selected weights explicitly prohibit commercial use. Keep implementation isolated until suitable licensing exists. |

Next: establish permitted usage and remaining budget; stage and inspect the exact ONNX graph in cloud; verify real label names/export preprocessing/layout; obtain legitimate input reviews; run one bounded paired r5-versus-fusion pilot and inspect masks manually. Then evaluate on family-disjoint independently verified labels, with temporal/field evidence for active infiltration. Preserve all quarantined rights and annotation limitations. No 80% accuracy or other improvement is claimed.

## Verification recorded for this change

340 backend tests and 39 frontend tests passed after the real-interface correction (30 new tests). ESLint, TypeScript/Vite build, Python compilation and whitespace checks passed. Existing frontend OpenCV browser-externalization/chunk-size warnings remain; no frontend code changed. All new model-output tests are synthetic, including fake sessions/predictors and a tiny constant-only ONNX graph executed in actual ONNX Runtime. The latter tests runtime initialization and the end-to-end mask path without pretrained weights. No measured defect accuracy, precision, recall, F1, IoU or real-model speed improvement is available.
