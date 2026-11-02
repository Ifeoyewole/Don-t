# JointInspect Work Cycle — 2026-11-02

## Verified environment and infrastructure

- Google Cloud CLI `591.0.0` (`core 2026.10.26`) installed at `/workspace/tools/google-cloud-sdk`.
- Active account: `akintunde.dolapo1@gmail.com`.
- Active project: `joint-inspection-510310` (`Joint-Inspection`, project number `567370443508`).
- Existing Cloud Run services are healthy: `jointinspect-gpu-controller` and `pipe-joint-api` in `europe-west2`.
- Existing scheduler `jointinspect-gpu-controller-15m` remains enabled.
- Existing buckets, Artifact Registry repositories, Cloud Build history, Batch history, APIs, and model objects were read successfully. Nothing was deleted, recreated, or overwritten.

## Live dataset verification

The original recorded checkpoint remains reproducible at `datasets/sewer-ml/curated-v3/20k`:

| Field | Verified count |
| --- | ---: |
| Training records | 20,000 |
| Reused existing GCS images | 4,315 |
| Newly extracted images | 15,685 |
| Unique SHA-256 values | 20,000 |
| Unique dHash values | 20,000 |
| Early-stop validation images | 878 |

The current revised dataset at `datasets/sewer-ml/curated-v4/20k` is a separate version and must not be conflated with v3:

| Field | Verified count |
| --- | ---: |
| Training records | 20,000 |
| Reused existing GCS images | 4,726 |
| Newly range-extracted images | 15,274 |
| Unique SHA-256 values | 20,000 |
| Unique dHash values | 20,000 |
| Early-stop / threshold-tune / development-report | 819 / 380 / 388 |

## Recovered Inspect View decision

The successful `class-aware-v2-cv-r2-20261025` experiment combined ConvNeXt-Tiny, EfficientNet-B0, and adapted WRc class-by-class. It completed technically but failed its pre-declared acceptance gate:

| Candidate | Development macro-F1 | Development macro-F2 |
| --- | ---: | ---: |
| ConvNeXt-Tiny standalone | 0.554764 | 0.583692 |
| Inspect View fusion v2 | 0.517330 | 0.538663 |

The fusion therefore remains a development prototype with `production_approved=false`. ConvNeXt-Tiny remains the strongest evaluated standalone model on this held-out development split. A final frozen Inspect View model must wait until the expanded datasets are normalized, deduplicated, split without source/video leakage, and used in staged retraining. The existing acceptance gate must remain in force.

## Dataset expansion continuation

- `train00.zip` is preserved in GCS at 18.38 GiB.
- The previous `train01` staging job failed because `sciencedata.dk` timed out after bounded retries.
- Batch previously expanded the secret environment value into agent logs. The staging implementation now reads Secret Manager at runtime through an authorized API session; the Batch job definition contains only the secret resource name.
- Focused credential-path and archive tests: 8 passed.
- Immutable staging image built successfully as Cloud Build `80166c52-1179-4f3d-9985-9929006df12f`, digest `sha256:f373137543b75a51d61490998dfdad377db0b9a3bcac2b11ecaca6cddc444be9`.
- One bounded CPU retry was submitted as `sewer-ml-stage-train01-usc1-r2-20261102` in `us-central1`, then cancelled at the owner's direction after independent probes confirmed the provider outage.
- Fresh probes of `https://sciencedata.dk/`, the `train01.zip` URL, and `https://www.sciencedata.dk/` all completed TLS but returned HTTP 503. This establishes a provider/backend outage rather than an authentication rejection or GCP block. No further Sewer-ML download retries should run until a public probe stops returning 503.

## Blockers and exact next action

1. Rotate the `sewer-ml-download-password` credential because its first version appeared in historical Batch agent logs. Do not copy the exposed value into code, documentation, issues, or commits.
2. Do not retry Sewer-ML downloads while the provider returns HTTP 503. Retain `train00.zip`, curated-v3, and curated-v4 as immutable source material.
3. Monitor SRuibo quarantine import build `5864ab81-80d1-4404-a555-084d8bda7e5a`. On success, verify the final registry count, split counts, hashes, and duplicate report before any evaluation.
4. Resolve SRuibo class-code semantics and primary provenance before allowing training. Preserve every original annotation and keep unapproved weights isolated from production promotion.

## External source preflight

- `SRuibo/Sewer-pipe-defects` is public and ungated on Hugging Face, declares CC BY 4.0, and is pinned for preflight to revision `7fafcbe676aad60f38d8fe39cde93cf599f8362e` (4,739,196,325 bytes).
- The repository contains paired YOLO images/labels: 1,561 train, 193 validation, and 198 test items.
- Its original YOLO splits and class codes (`CK`, `PL`, `SG`, `SL`, `TL`, `ZW`) are visible, but the dataset card does not define those codes or establish primary provenance.
- It is registered as `SRC-SRUIBO-001` with `PENDING_REVIEW`, `production_eligible=false`, and all class codes mapped fail-closed to `GEOMETRY_UNCERTAIN` until semantics are verified.
- Bounded Cloud Build quarantine import `5864ab81-80d1-4404-a555-084d8bda7e5a` failed before publication because Hugging Face rate-limited the shared Cloud Build IP at its Xet token endpoint (`429`). The importer was changed to disable Xet and use one standard HTTP worker. It preserves original splits and IDs, records SHA-256/dHash/dimensions/annotations, checks perceptual overlap against Sewer-ML v4, uploads without clobbering existing objects, and publishes `dataset_registry.json` last.
- HTTP-only retry `c70fa84e-ef87-4ed1-b1fa-1921996afb5c` succeeded. The immutable quarantine prefix contains 3,907 objects (2,376,131,463 bytes) and a publish-last registry with 1,952 paired YOLO records: 1,561 train, 193 validation, and 198 test.
- Deduplication against Sewer-ML v4 found 357 exact SHA-256 matches, 144 near-dHash matches, and 1,451 unique candidates. The source itself contains 1,947 unique SHA-256 values, so five exact intra-source duplicates must be excluded before evaluation or training.
- All records remain `QUARANTINED_PENDING_PROVENANCE_AND_LABEL_REVIEW`; none are eligible for training yet.
