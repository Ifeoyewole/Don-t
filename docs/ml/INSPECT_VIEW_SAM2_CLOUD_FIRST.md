# Cloud-first Inspect View r5 + SAM 2.1 evaluation

**Prepared, not deployed.** All checkpoint downloads, image reads, GPU inference,
and report writes occur inside Google Cloud. The operator's Windows PC is
only a control terminal. The existing production Cloud Run `pipe-joint-api`,
its IAM, inspection route and engineering gates are not modified by this branch.

Project: `joint-inspection-510310`; region `europe-west2`. Verify quota,
permissions and pricing before starting any billable Cloud Build or Vertex job.

## Artifacts

- Inspect View r5: `gs://joint-inspection-510310-data/models/inspect-view/research-candidates/repr-convnext-masked-r5-20261104/best.pt`
- Pinned Inspect View SHA-256: `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`
- Meta SAM2.1 Tiny publisher checkpoint:
  `https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt`
- SAM2 source revision: `2b90b9f5ceec907a1c18123530e92e794ad901a4`

## 1. Stage official SAM2 checkpoint directly to GCS

From Cloud Shell or any terminal with gcloud configured (no weight download to PC):

```bash
gcloud config set project joint-inspection-510310
gcloud builds submit --region=europe-west2 --config=scripts/cloud/cloudbuild-stage-official-sam2.yaml .
```

Cloud Build downloads the official checkpoint into its temporary workspace,
computes a SHA-256 digest and uploads both to
`gs://joint-inspection-510310-data/models/sam2/publisher-quarantine/<BUILD_ID>/`.
Review and independently record that digest and rights/provenance before use.
A publisher download alone is not commercial validation.

## 2. Build the isolated research image in Cloud Build

```bash
gcloud builds submit --region=europe-west2 --config=scripts/cloud/cloudbuild-inspect-view-sam2.yaml .
```

The image pins SAM2 source, includes GPU-capable PyTorch and inference code,
but does not embed either checkpoint. Record and use its immutable image digest.
No live inference service or GPU job is started by building this image.

## 3. Select an authorized cloud-hosted CCTV test image

The image must already be in GCS with rights appropriate for the planned use.
Determine its original SHA-256 **within GCP** (e.g. a short Cloud Build hashing
step); never copy the model or private image onto Windows. Record an
operator-selected ROI in original image-pixel coordinates (x0,y0,x1,y1).
Do not accept guessed dimensions or mismatched hashes.

Fill in each `REPLACE_...` value in
`scripts/cloud/vertex-inspect-view-sam2.example.yaml`, including the GCS
image/sha, reviewed SAM2 checkpoint/sha, fixed ROI, unique report prefix and
immutable container digest. The YAML is deliberately unusable as-is.
Use a **dedicated least-privilege service account** with read access only to
the required inputs and create-only access to the research output prefix.
Once the permissions, GPU quota and cost are verified:

```bash
gcloud ai custom-jobs create \
  --region=europe-west2 \
  --display-name=inspect-view-sam2-research \
  --service-account=REPLACE_VERTEX_WORKER_SERVICE_ACCOUNT \
  --config=scripts/cloud/vertex-inspect-view-sam2.example.yaml
```

This is a billable one-replica T4 Vertex AI custom job. It uses GCS-to-ephemeral
cloud-worker staging, validates all SHA-256 hashes, forces SAM2 onto CUDA, and
runs both models + OpenCV on the same frame. It uploads `report.json` and
optionally `overlay.png` back to GCS. It refuses missing checkpoints, failed
hashes, absent GPU and model-runtime failures. Low-quality masks are correctly
reported as REVIEW_REQUIRED, not fabricated successes.

## 4. Interpret and expand the evaluation

Read the cloud report for source image/weight hashes, Inspect View class
evidence, SAM2 mask/review status, OpenCV pixel candidates, elapsed runtime and
GPU allocated-memory high-water mark. A single successful inference, the
11 integration tests, and the previously reported 144 backend tests **do not**
establish field accuracy or approve production fusion.

Next use a consented, annotated and grouped holdout to assess defect-wise
F1/F2, mask IoU, latency p50/p95, peak memory, failure rate, and Inspect View
standalone vs fused ablation. In particular OPEN_JOINT, INFILTRATION and
PROTRUDING_LATERAL remain unvalidated. This experimental path reports neither
engineering PASS/FAIL nor authoritative millimetres.

Meta says official SAM2 code and checkpoints are Apache-2.0, subject to
preserving notices and reviewing the exact dependency/weight provenance.
The project owner reports Inspect View commercial permission; retrieval of
the rights-holder agreement and precise scope remains separate from technical
test success. None of these changes turn SAM2 into a defect classifier or
promote a research result into the production Cloud Run endpoint.
