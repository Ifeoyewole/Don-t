# JointInspect Unified Vision v1 — research batch and trusted Gemini reuse

**RESEARCH PR ONLY: no GPU job, production deploy, model training or data promotion is triggered.**

## Purpose

The successful previous one-frame GPU smoke produced a SAM2 region mask for hanging
material, but no trustworthy joint geometry. One frame is not an accuracy test.

This change adds an opt-in bounded GCS/Vertex batch pipeline, one Inspect View r5
model load and one SAM2.1 Tiny predictor load per worker, plus an optional
authenticated reuse of the existing Vertex AI Gemini 3.1 Pro semantic result.
OpenCV and the Unified Vision v1 fail-closed decision contract are reused.
The GPU worker **never** makes a new Gemini API call.

## Step 1 — Prepare an 80-frame human-review worklist

The two imported public Roboflow registries are quarantine-only. The publishers
declared CC BY 4.0, but upstream rights and annotations are NOT independently
verified for commercial training.

Download *only their small JSON registries*, not the CCTV images:

~~~powershell
$root = "gs://joint-inspection-510310-data/datasets/quarantine/roboflow"
gcloud storage cp "$root/sewage-defect-detection-s68df/sewer-defects-u8zwz/v1/dataset_registry.json" ".\sewer-defects-registry.json"
gcloud storage cp "$root/kyle-scally-4ixoi/pipeline-cctv-defect/v1/dataset_registry.json" ".\pipeline-cctv-registry.json"

python -m scripts.cloud.prepare_unified_batch_worklist --registry ".\sewer-defects-registry.json" --registry ".\pipeline-cctv-registry.json" --out ".\unified-review-worklist.csv" --target 80
~~~

The worklist excludes recorded exact duplicate candidates and prioritizes
joint-offset, utility-intrusion, leak, normal and difficult-negative candidates.
It does NOT claim these source labels prove OPEN_JOINT, INFILTRATION or
PROTRUDING_LATERAL. No new class is invented if examples are missing.
Near-duplicates and video source-family leakage still require manual review.

Each CSV row deliberately leaves source media URI, source-family identity,
joint geometry, reviewer ROI and adjudicated ground truth blank. Those must be
filled through actual image inspection before GPU execution.

## Step 2 — Create a reviewed GPU batch manifest

The one-frame smoke template is in:
scripts/cloud/examples/unified-batch-one-frame.json

It references an already-known quarantined CCTV image and previously reviewed
ROI. To grow the manifest, add up to 100 independently checked frame objects:

~~~json
{
  "schema_version": "1.0",
  "manifest_id": "research_review_batch_001",
  "frames": [
    {
      "frame_id": "frame_001",
      "image_uri": "gs://joint-inspection-510310-data/REPLACE_IMAGE",
      "image_sha256": "REPLACE_WITH_64_LOWERCASE_HEX_SHA256",
      "geometry": "VERTICAL_SEAM",
      "roi": [100, 20, 400, 500],
      "source_family": "REPLACE_VERIFIED_VIDEO_FAMILY",
      "source_id": "REPLACE_SOURCE_FRAME_ID",
      "rights_status": "RESEARCH_QUARANTINE",
      "annotation_status": "UNVERIFIED_SOURCE_LABEL",
      "source_label": "Joint offset"
    }
  ]
}
~~~

Rights status must be RESEARCH_QUARANTINE or RIGHTS_REVIEWED_RESEARCH.
Annotation status must be UNVERIFIED_SOURCE_LABEL or REVIEWED_GROUND_TRUTH.
Reviewed ground truth requires an actual reviewed_label and review_id, not a
publisher source label. These are still research-only images.

The validator refuses duplicate exact image hashes, repeated IDs, malformed
ROIs, out-of-bucket GCS inputs, unknown metadata and batches over 100 frames.
A specialist must review near-duplicates and source families separately.

## Step 3 — Rebuild and run Vertex AI Spot

**Rebuild is mandatory:** the previous unified smoke image digest
sha256:a25ae49f17acc62b987241cd16e61af12ae5317adcb341ab473777676eaa4346
does not contain this new batch worker.

~~~powershell
gcloud builds submit . --project=joint-inspection-510310 --region=europe-west2 --config=scripts/cloud/cloudbuild-inspect-view-sam2.yaml
~~~

Find the NEW immutable digest in Artifact Registry. The batch job template
is scripts/cloud/vertex-unified-batch.example.yaml. It uses the previously
working trainer service account, an n1-standard-4 with one T4 GPU,
Spot scheduling and a unique output prefix. It selects the batch worker
using containerSpec.command, not the existing single-frame entrypoint.

Upload the reviewed manifest to a unique GCS path:

~~~powershell
$manifestFile = ".\scripts\cloud\examples\unified-batch-one-frame.json"
$manifestSha = (Get-FileHash $manifestFile -Algorithm SHA256).Hash.ToLowerInvariant()
$manifestUri = "gs://joint-inspection-510310-data/models/inspect-view/research-manifests/unified-batch-first-v1.json"
gcloud storage cp --no-clobber $manifestFile $manifestUri
Write-Host "Manifest SHA: $manifestSha"
~~~

Edit the example YAML placeholders for the new Docker digest, uploaded manifest
URI, exact manifest SHA, unique output GCS prefix and desired limit. The
launch command is billable and must be run explicitly:

~~~powershell
gcloud ai custom-jobs create --project=joint-inspection-510310 --region=europe-west2 --display-name=jointinspect-unified-batch-review-001 --config=scripts/cloud/vertex-unified-batch.example.yaml
~~~

The GPU job writes summary.json, frames.jsonl and individual frame research
report.json plus optional overlay.png files into the selected output prefix.
Any frame error is recorded; the job fails after writing an incomplete
summary rather than silently reporting the batch as fully complete.

## Gemini 3.1 Pro — authentic reuse, zero duplicate model calls

The existing normal measurement endpoint executes VertexSemanticGate.evaluate.
A new optional research receipt exporter uses THAT result; it does not call
Gemini again. Export is OFF by default and requires ALL of:

- JOINTINSPECT_GEMINI_RECEIPT_EXPORT_ENABLED=true on a controlled research
  backend revision.
- JOINTINSPECT_GEMINI_RECEIPT_EXPORT_TOKEN configured securely and the
  matching restricted X-JointInspect-Research-Receipt-Token request header.
- JOINTINSPECT_GEMINI_RECEIPT_HMAC_KEY, a separately provisioned secret of
  32 or more bytes. Supply through Cloud Run Secret Manager integration.
- Appropriate GCS write permissions for the backend identity.

Never put the token or signing secret in source code, YAML, the frontend,
Cloud Logging, CLI output or GCS. Export stores only selected structured
semantic flags, NOT original CCTV bytes, operator notes or Gemini narrative.
Authorized requests receive semantic_receipt_uri in the measurement response;
other requests get null and do not trigger an export.

For a frame with an existing receipt, the batch manifest can also specify
gemini_receipt_uri and gemini_receipt_sha256. The GPU job must include the
optional --gemini-hmac-secret-resource=projects/567370443508/secrets/NAME/versions/latest
argument and have access to exactly that secret version. The worker verifies
the file SHA, original image SHA, issuer, HMAC signature and receipt age
(<=30 days) before reusing Gemini evidence. Receipt signature verification
is an actual cryptographic provenance check; a matching image hash alone
would NOT be sufficient.

Missing receipt: gemini.status=NOT_PROVIDED. Invalid or stale receipt:
frame failure. A verified receipt may gate unsuitable scenes and suggest
orientation, but cannot establish a defect, physical millimetres, a licensing
right, or an engineering PASS/FAIL.

**There is no automatic four-model production endpoint in this PR.**
This implements the controlled receipt handoff and batch research harness;
production promotion requires held-out validation and a separate release review.

## Evaluation and safety requirements

This phase reports counts, candidate masks, pixel geometry states, failure
reasons, receipt reuse and frame processing durations. It intentionally sets
precision, recall and F1 to null. Genuine accuracy requires independently
labelled, video-family-separated and rights-reviewed ground truth. No quarantined
images are automatically promoted into commercial training.

Test without GPU or secrets:

~~~powershell
python -m pytest backend/tests/test_unified_batch_manifest.py backend/tests/test_signed_gemini_receipt.py backend/tests/test_unified_batch_research_reporting.py backend/tests/test_unified_vision_v1.py -q
~~~
