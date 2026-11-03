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

## Expanded-dataset representation candidates — 2026-11-03

- Balanced EfficientNet-B0 Vertex job `618868778347790336` succeeded on one Spot T4 using 2,000 training records and 400 validation records. The family-safe validation subset contained 205 threshold-tuning and 195 development-report records.
- Development macro-F1 was `0.6291775421` and macro-F2 was `0.7051346067`. Only seven of fifteen canonical classes had positive development support, so this is a pipeline/candidate result and is not a production-promotion result.
- The locked test was not read. The candidate remains `production_approved=false`.
- Immutable artifact: `gs://joint-inspection-510310-data/models/inspect-view/research-candidates/repr-efficientnet-balanced-r2-20261103/best.pt`; SHA-256 `d10954a20b2fa36b10a9fa0098f243cc8bfeee5cebc0cbf167409bcea4141882`.
- Balanced ConvNeXt-Tiny job `5308734471556562944` was submitted with the identical manifest, split contract, seed, sample caps, epoch count, learning rate, GPU type, and worker image.
- Balanced ConvNeXt-Tiny job `5308734471556562944` subsequently succeeded. Development macro-F1 was `0.7319878159` and macro-F2 was `0.8289892045`, exceeding the balanced EfficientNet candidate on the same 195-record development report.
- ConvNeXt also evaluated only seven of fifteen canonical classes; the unsupported classes include `NORMAL`, `OPEN_JOINT`, and `JOINT_DISPLACEMENT`. It therefore remains a research candidate and must not advance to the locked test or production on this result alone.
- Immutable ConvNeXt artifact: `gs://joint-inspection-510310-data/models/inspect-view/research-candidates/repr-convnext-balanced-r2-20261103/best.pt`; SHA-256 `74ae2a12569ef4927ca83eecdd8d09b46ec53da263138d8e0a2c7c16abe8d81c`.
- Production WRc remains the primary classifier. Candidate promotion requires same-image comparison and the final locked-test metrics, calibration, latency, memory, and failure-rate checks described in the production plan.

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
5. Audit the 333 unique Robotic Pipe Defect Detection v7 candidates, then promote only accepted records into a new versioned joint-focused training manifest. Do not add all 1,917 exports to the effective dataset count.
6. Import PVC Pipe Defect v2 next. Keep Pipe Defects v1 quarantined because its generated class metadata appears corrupted, and generate a downloadable version for Pipeline Defect Detection Segmentation before attempting that import.

## External source preflight

- `SRuibo/Sewer-pipe-defects` is public and ungated on Hugging Face, declares CC BY 4.0, and is pinned for preflight to revision `7fafcbe676aad60f38d8fe39cde93cf599f8362e` (4,739,196,325 bytes).
- The repository contains paired YOLO images/labels: 1,561 train, 193 validation, and 198 test items.
- Its original YOLO splits and class codes (`CK`, `PL`, `SG`, `SL`, `TL`, `ZW`) are visible, but the dataset card does not define those codes or establish primary provenance.
- It is registered as `SRC-SRUIBO-001` with `PENDING_REVIEW`, `production_eligible=false`, and all class codes mapped fail-closed to `GEOMETRY_UNCERTAIN` until semantics are verified.
- Bounded Cloud Build quarantine import `5864ab81-80d1-4404-a555-084d8bda7e5a` failed before publication because Hugging Face rate-limited the shared Cloud Build IP at its Xet token endpoint (`429`). The importer was changed to disable Xet and use one standard HTTP worker. It preserves original splits and IDs, records SHA-256/dHash/dimensions/annotations, checks perceptual overlap against Sewer-ML v4, uploads without clobbering existing objects, and publishes `dataset_registry.json` last.
- HTTP-only retry `c70fa84e-ef87-4ed1-b1fa-1921996afb5c` succeeded. The immutable quarantine prefix contains 3,907 objects (2,376,131,463 bytes) and a publish-last registry with 1,952 paired YOLO records: 1,561 train, 193 validation, and 198 test.
- Deduplication against Sewer-ML v4 found 357 exact SHA-256 matches, 144 near-dHash matches, and 1,451 unique candidates. The source itself contains 1,947 unique SHA-256 values, so five exact intra-source duplicates must be excluded before evaluation or training.
- All records remain `QUARANTINED_PENDING_PROVENANCE_AND_LABEL_REVIEW`; none are eligible for training yet.

## Roboflow expansion

- The `roboflow-api-key` exists in Secret Manager and is never written to source or build arguments. The Cloud Build service account has accessor permission scoped to that secret.
- All five requested Roboflow projects are reachable and declare CC BY 4.0 through the authenticated project API.
- Four projects have generated versions. `pipeline-defect-detection-segmentation` has 4,000 annotated source images but zero generated versions, so no versioned download is currently available.
- Robotic Pipe Defect Detection version 7 was imported by successful Cloud Build `ceac29b7-4e89-4ccd-ae63-4b3f8f02f0dc` to `gs://joint-inspection-510310-data/datasets/quarantine/roboflow/hatim-husaini/pipe-defect-detection/v7/`.
- The quarantine prefix occupies 82,834,196 bytes and preserves the source YOLOv8 ZIP, extracted media, annotations, and publish-last registry.
- The registry contains 1,917 records: 1,728 train, 126 validation, and 63 test. Original classes are Deformation, Misalignment, Obstacle, and Rupture, with canonical mappings preserved alongside them.
- Strict deduplication against Sewer-ML v4, SRuibo, and earlier records within this export found 1 exact baseline dHash match, 445 exact intra-source dHash duplicates, 1,138 near duplicates, and 333 unique candidates. All remain `QUARANTINED_PENDING_ANNOTATION_AUDIT` until human annotation and primary provenance review.
- PVC Pipe Defect v2 is the next useful downloadable joint-focused source: 3,066 generated images across Defective, L Joint, and T Joint. Pipe Defects v1 reports malformed generated class metadata and must remain lower priority. Pipeline Defect Detection v8 contains 38,400 heavily tiled/augmented generated images and requires a source-level deduplication plan before import.
- PVC Pipe Defect v2 import build `13e18970-68f6-4af7-b6ec-f2564d21ed67` succeeded. The actual export contains 3,064 paired records rather than the 3,066 reported in version metadata: 2,746 train, 217 validation, and 101 test. Deduplication found 2,817 unique candidates, 66 exact intra-source dHash duplicates, and 181 near duplicates. `Defective` maps to `FAULTY_JOINT`; `L Joint` and `T Joint` remain fail-closed as `GEOMETRY_UNCERTAIN` because they describe joint types rather than defect states.
- Pipe Defects v1 import build `95db9634-d31a-42ba-9842-ef19c7e4a0e4` succeeded into quarantine with 8,097 records. It contains 4,854 exact intra-source dHash duplicates, 2 exact baseline dHash matches, 2,300 near duplicates, and 941 unique candidates.
- Pipe Defects v1 is unusable for training in its present form. Its 15 exported class names are README sentences such as `Roboflow is an end-to-end computer vision platform that helps you`; every label therefore maps to `GEOMETRY_UNCERTAIN` pending recovery from a trustworthy annotation source.
- The Pipeline Defect Detection Segmentation project exposes 4,000 source images but no generated version. An authenticated request for version 1 returned HTTP 404 (`version ... does not exist or cannot be loaded due to missing permissions`), so the public API key cannot generate an export in the owner's workspace.
- Pipeline Defect Detection v8 import build `9ae19420-2779-45f4-9cee-5d879959a889` succeeded with 38,400 records: 33,600 train, 3,200 validation, and 1,600 test. Deduplication found 455 exact intra-source dHash duplicates, 3,856 near duplicates, and 34,089 unique candidates. Original `corrosion` and `pipe` labels are retained; `corrosion` maps to `CORROSION`, while generic `pipe` remains `GEOMETRY_UNCERTAIN`.
- Across SRuibo and the three usable Roboflow exports, 38,690 unique external candidates are now quarantined. Pipe Defects v1 adds 941 visually unique records but is excluded from that usable count because its labels are corrupted.
- The official VideoPipe site remains online at `https://videopipe.github.io/`. QV-Pipe and CCTV-Pipe downloads route through CodaLab competitions 2232 and 2284 and require CodaLab access.
- The official Co-UDlabs release is Zenodo record `8193032` and `github.com/Co-UDlabs/sewer_defects`. Its documented 1,577-image Google Drive source currently rejects anonymous folder enumeration, while the alternate public sample folder resolves but is empty. No count is claimed in GCS.
- IPD Zenodo record `17398156` contains only its licence agreement. The 357-image, pixel-mask dataset requires a signed one-year, research-only agreement returned to Aristotle University before the download is issued; it cannot be imported from Zenodo without that completed access step.

## Frozen Inspect View dataset scope

- The owner elected to skip VideoPipe, CCTV-Pipe, IPD, and the inaccessible Co-UDlabs media for this phase and proceed with the material already in GCS.
- `training/configs/inspect_view_scope_v1.json` freezes the current inputs, exclusions, candidate counts, promotion requirements, staged training order, and fusion acceptance gate.
- Pipe Defects v1 remains excluded. Records from the other external sources remain candidates until record-level annotation and provenance review produces a versioned promoted manifest.
- Do not launch a nominal final model from quarantine paths. The existing `training/train_classifier.py` uses a legacy six-class synthetic-data contract and cannot correctly train the fifteen-class canonical dataset without a new source-aware loader and evaluation contract.
- Exact next action: build the promoted, family-grouped manifests from accepted records, add the canonical multi-task loader, run a CPU data-loader smoke evaluation, then submit the first bounded representation-learning job.

## Family-grouped Inspect View manifests

- Cloud Build `21d5905f-3cb6-4e72-b387-d72951845992` created immutable research-candidate manifests under `gs://joint-inspection-510310-data/datasets/manifests/inspect-view-expanded-v1-20261102/inspect-view-manifests/`.
- Global SHA-256 enforcement removed four additional cross-source duplicates, leaving 38,686 external representation candidates in 6,704 source-media families.
- The joint-detection stage contains 2,066 records from 972 families: 1,675 train, 198 validation, and 193 test.
- The surface-condition stage contains 7,953 records from 1,494 families: 6,267 train, 754 validation, and 932 test.
- Every family is assigned deterministically to exactly one split. Full-manifest validation confirmed unique SHA-256 values and no family leakage across train, validation, or test.
- The first loader smoke build correctly rejected an annotation labelled as a bounding box that actually contained a segmentation polygon. The canonical loader now preserves and validates both normalized YOLO boxes and segmentation polygons.
- Corrected loader smoke build `44f1b562-ca95-4e01-a90b-82b8222dc3f8` passed all three manifests, verified sampled image SHA-256 values, dimensions, annotation syntax, and GCS paths, and published `loader_smoke_report.json` beside the manifests.
- The next action is to implement the bounded representation-learning worker against `representation.jsonl`. Do not reuse the legacy random-update six-class classifier as the final Inspect View trainer.

## Representation worker

- A real PyTorch canonical multi-label worker now trains EfficientNet-B0 or ConvNeXt-Tiny using BCE-with-logits, checksum-verified GCS images, fixed sample caps, and create-only versioned artifact uploads.
- The first CPU smoke build `72da3057-10d0-4586-92fa-8ef419fca282` correctly stopped on an empty-label record. Empty annotations are now excluded from supervised learning rather than guessed as `NORMAL`; 6,529 such records remain available only for a future self-supervised objective.
- Corrected CPU smoke build `b51287e8-d45c-4ad0-bf02-375a4b434651` succeeded with 24 train and 12 validation records for one epoch. Its macro-F1 and macro-F2 were both 0.333333 across the three classes present in that tiny sample. These are pipeline-smoke metrics, not model-selection evidence.
- Immutable worker image build `9874acdb-bf3f-48c2-9ae2-9de43675f6f0` published digest `sha256:83c6908e7e3215a85b4e27edb52723739c574457fbd1b9076eae13ba8afc6599`.
- Compute Engine reports unused T4 and L4 quota in europe-west2, but Vertex AI has separate accelerator quotas. Standard Vertex T4 submission was rejected before job creation because its quota is zero. Vertex exposes one preemptible T4 in europe-west2.
- Spot Vertex Custom Job `9121805612311642112` was submitted with one T4, 1,000 training records, 200 validation records, two epochs, and a one-hour hard timeout. Its output prefix is `gs://joint-inspection-510310-data/models/inspect-view/research-candidates/repr-v1.0.0-t4-r1-20261102/`. At handoff it is pending Spot capacity; no standard T4 job was created or charged.
- Spot Vertex Custom Job `9121805612311642112` later obtained capacity and succeeded, running from 2026-11-02 23:54:08 to 23:57:09 UTC. No Vertex training jobs remain active.
- The versioned checkpoint is 16,386,654 bytes. Training loss fell from 0.541233 to 0.238640 over two epochs on 1,000 records. On 200 validation records, only five canonical classes were represented; fixed-threshold macro-F1 was 0.285899 and macro-F2 was 0.265101.
- This checkpoint validates GPU execution and artifact preservation but is not eligible for fusion or promotion. Its score is not comparable to the prior nine-class ConvNeXt-Tiny result because the class contract and validation population differ.
- Exact next action: add class-balanced bounded sampling, per-class support/precision/recall/F1/F2, and threshold tuning on a dedicated tuning split before expanding training volume or comparing architectures.
