# ISWDS real-checkpoint CPU functional test — 10 November 2026

Status: **functional execution completed; do not adopt for canonical defect decisions yet**. This is a real-checkpoint research result, not the synthetic test fixture and not an accuracy evaluation.

## Delivery and execution

PR #36 was squash-merged as `050b93c5dcdb98a71ab619ebf73ebaf4b970b20d` after CI passed on its final HEAD. Vercel production deployment `dpl_7GSpXtUk18vYAE1kcPNQeL7rx9a8` reached READY and the public site alias was verified. No deployment hold was applied. The sewer research feature remains disabled by default; no production model weights or authentication were changed.

One CPU-only Cloud Build execution ran in `joint-inspection-510310`, `europe-west2`:

- Job: `759ed630-2e15-4689-b7bf-14f006cf5024`, SUCCESS.
- Existing immutable container: `inspect-view-sam2-research@sha256:bf93efdab86558f29a708e2719bdf511953b2c26d87c6cc7b57612ab0b8f0304`.
- Source: merged code plus a recorded exploratory runner; private Cloud Build source archive and execution plan preserve reproducibility.
- E2_HIGHCPU_8, 8 vCPU/8 GiB, 900-second maximum, one execution, no automatic retry.
- No GPU, Vertex model API, paid Gemini request, model training or new container build.
- ONNX Runtime `1.18.1`, CPUExecutionProvider; model inference threads bounded to two.
- Checkpoint, model loading and inference stayed inside GCP. Only reports, input copies, masks and overlays were retrieved for review; checkpoint weights were not downloaded to a workstation.

The user reconfirmed that cycle spending was far below the existing USD100 cap and instructed continuation. This was a bounded exploratory CPU scope, not an unlimited budget increase. Billing-account cost access was denied; actual invoiced charges remain unavailable.

## Actual model verification

The downloaded official `ISWDS_RT-DETR_v2_model.onnx` matched the publisher's immutable revision `ffe32890eee1fba794d7a22486289562b118e574`, exact size 103,295,200 bytes and SHA-256 `1afdfd5b1f39dcd9f927b3ac25662487d3ac2e7fe823d7322b1065a7e887bb3b`. The checkpoint was preserved in GCS research quarantine without overwriting prior artifacts.

Actual ONNX Runtime input/output inspection confirmed:

| Tensor | Type | Shape/meaning |
| --- | --- | --- |
| images | float32 | N x 3 x 640 x 640 |
| orig_target_sizes | int64 | N x 2; original height, width |
| labels | int64 | per-image predicted numeric class IDs |
| boxes | float32 | per-image postprocessed original-image XYXY coordinates |
| scores | float32 | detection scores |

Initialization took 0.738 seconds. Graph class-name metadata was empty. Numeric IDs **2, 3, 4, 5 and 7** appeared in the retained detections. Their semantic meaning was not established. The alternative YOLO checkpoint's class order was not borrowed. All remained `UNVERIFIED_SOURCE_CLASS_ID_n`; no canonical infiltration, open-joint or protruding-lateral positive was fabricated.

The model source declares noncommercial research use only. Quarantine, unresolved upstream rights and commercial-use restrictions remain. This successful test does not establish commercial permission.

## Three-frame functional comparison

Frames 10, 26 and 34 were used under the user's explicit exploratory-input authorization. Their original bytes were SHA-verified against the existing GCS registry/review package. Existing `NEEDS_HUMAN_REVIEW`, unverified source labels and lineage uncertainty were preserved. No record was promoted to READY_FOR_RESEARCH or independently verified ground truth.

No unapproved manual ROI or joint geometry was used. Each frame was routed through OBJECT_SEGMENTATION with detector-generated unverified region proposals. Detector threshold was 0.35, with at most three retained detections per image; these settings were not tuned to the examples.

| Frame | A: r5 only (s) | B: ISWDS only (s) | C: r5 + ISWDS + SAM2 (s) | Retained detections | Unique prompts | Accepted mask candidates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.2290 | 0.6096 | 6.4476 | 3 | 2 | 1 |
| 26 | 0.0905 | 0.5930 | 6.0522 | 2 | 2 | 2 |
| 34 | 0.0859 | 0.5968 | 8.6913 | 3 | 3 | 3 |
| Mean | 0.1351 | 0.5998 | 7.0637 | — | — | — |

These are single measured passes on three images, with shared warmed model instances. A, B and C each executed their own forwards; C did not substitute cached A/B outputs. Model downloading/loading, package installation and worker startup are excluded from these timings. They are not stable latency percentiles, throughput benchmarks or confidence intervals.

Eight retained detections yielded seven unique prompts because frame 10 had a duplicate box under another numeric class. Six prompts produced actual binary SAM2 PNG masks; one was rejected. This is processing availability, not segmentation accuracy or recall.

## Findings and limitations

- r5's existing preprocessing, checkpoint, class mapping and probabilities were preserved. Its weak classes remained UNVALIDATED/UNRELIABLE, not newly supported predictions.
- ISWDS produced finite boxes and scores on all three real frames, and the boxes successfully prompted SAM2. Canonical defect findings remain empty because class IDs are unmapped.
- Frame 10: the accepted mask follows part of the lower curved region and includes some overlaid text; it does not establish complete annular boundaries or a measurable open joint.
- Frame 26: masks cover a diagonal structure and a larger surrounding region; exact defect/target identity is unresolved.
- Frame 34: masks include surrounding wall/floor regions rather than cleanly isolating the horizontal cylinder that motivated the suspected-lateral example. High mask quality scores did not guarantee the intended target.
- These visual observations were made during assistant inspection of the saved overlays. They are not independent engineer adjudications, confirmed false positives or pixel ground truth.
- All unified decisions remained REVIEW_REQUIRED. All physical gap values remained null. No active infiltration was confirmed, no source lineage was invented, and no production semantic gate was overridden. Gemini was not invoked.

## Metrics and cost

Precision, recall, F1, false-positive rate, IoU, Dice and their confidence intervals are **not calculable from this experiment**: there are zero independently adjudicated benchmark labels/masks, unknown detector class mapping and only three exploratory frames. Counts above must not be reported as true positives or accuracy improvement.

The worker's actual research-script duration was 35.31 seconds. The complete Cloud Build ran from 07:45:34.176805710 to 07:47:56.302865 UTC, about 142.13 seconds including startup and package/model preparation. The official [Cloud Build pricing page](https://cloud.google.com/build/pricing), checked on 10 November, displayed $0.0156/minute for the default-pool e2-highcpu-8 machine. This gives roughly **$0.04–$0.05 in compute**, allowing minute rounding, before free allowances/credits and excluding storage or transfer. This is a public-rate estimate, not an invoice or a measured remaining account balance.

Amortizing that estimate across the three images gives about $0.013–$0.016 per image for this whole experiment, including all three configurations and startup. It must not be presented as the standalone production per-image price for A, B or C. Actual per-configuration billed costs are unavailable.

## Keep/drop decision and next action

**Do not adopt for production or canonical defect decisions at this stage.** The real model is computationally practical on CPU, but missing class identity and visible segmentation target mismatch block a keep decision. Preserve the artifacts and stop additional paid inference/training until those blockers are addressed. Do not delete existing models or datasets.

1. Obtain an authoritative ID-to-label map for this exact RT-DETR v2 artifact, including whether IDs are zero/one-based. Do not infer it from image appearance, score distributions or another checkpoint.
2. Establish a permitted, independently labelled held-out cohort with source/video-family separation, including normal appearances and verified target classes. Open-joint and protruding-lateral support must not be inferred from displaced-joint or sealing-material labels.
3. Obtain reviewed defect-region masks for mask-quality evaluation. Keep automated proposals distinct from annotation approval.
4. Run a paired A/B/C evaluation only after mapping, permissions, inputs and bounded spending scope are satisfied. Report per-class sample counts, independent family counts and 95% confidence intervals using family-aware resampling where related frames exist. Use mask IoU/Dice only where pixel ground truth exists. Active infiltration needs temporal/field evidence.
5. Apply the user's 80% recall target with reported precision and regression results. Acceptable precision and material-regression tolerances must be explicitly defined before an automatic keep decision. Unsupported classes remain unsupported; selective use is possible only where measured evidence supports it.

Private GCS reports include original bytes, r5 outputs, real ISWDS detections, actual masks, overlays, unified JSON, runtime contract, source hashes and the execution plan. Their exact private locations are retained in the operator handoff rather than published here.
