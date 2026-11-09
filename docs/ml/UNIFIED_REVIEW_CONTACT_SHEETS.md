# JointInspect: Private GCS CCTV review contact sheets

**Research only.** Uses a CPU-only Cloud Build job, quarantined Roboflow
registries and the previously generated 80-row CSV worklist. Does not call
Gemini, run SAM2, start Vertex GPUs, train, or approve commercial data rights.

## Why these frames matter

The first eight source-media IDs suggest the source families PI005299 and
PI005455. These are tentative video-family hints, not verified lineage.
Related source frames must not be split across training/evaluation partitions.
A human reviewer must confirm actual source footage and transformed variants.

## How the resolver works

The original importer stored source media under an extracted/ subtree in
each quarantine prefix. Some GCS folder-copy layouts can include an
additional import-root directory. This cloud-side resolver therefore lists
the REAL object names under each known source prefix and requires exactly
one match for the registry's source_root_within_extracted_archive and
original_image_path fields.

The image's worklist SHA-256 and relative path must match an existing
record in the corresponding quarantine registry. Each candidate object
is read into the ephemeral Cloud Build worker (up to 8 MiB per image);
the actual image bytes are SHA-256 checked before creating a thumbnail.

Ambiguous names, missing objects, invalid image bytes or SHA mismatches are
recorded as unresolved and never reported as verified.

The output CSV fills only image_uri_TO_VERIFY when the object path and
bytes have been checked. It DOES NOT fill the reviewer ROI, geometry,
source_family_TO_VERIFY or independent adjudicated ground truth. It does
not change an image's quarantine status or mark it as ready for training.

Four-column JPEG contact sheets contain at most 20 images per page,
with candidate category, tentative family and SHA prefix. Outputs stay in
private GCS; images are not downloaded to the PC except a sheet you
explicitly request for visual review.

## Run after this PR is merged

From the existing Windows PowerShell repository checkout:

~~~powershell
git checkout main
git pull origin main

$runId = "unified-review-$(Get-Date -Format yyyyMMdd-HHmmss)-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$worklistUri = "gs://joint-inspection-510310-data/datasets/quarantine/review-worklists/$runId.csv"
$outputPrefix = "gs://joint-inspection-510310-data/datasets/quarantine/review-sheets/$runId"

gcloud storage cp --no-clobber ".\unified-review-worklist.csv" $worklistUri
gcloud builds submit . --project=joint-inspection-510310 --region=europe-west2 --config=scripts/cloud/cloudbuild-unified-review-contact-sheets.yaml --substitutions="_WORKLIST_URI=$worklistUri,_OUTPUT_PREFIX=$outputPrefix"
~~~

Cloud Build can incur charges, but this step uses **no GPU or AI API**.

After Cloud Build succeeds:

~~~powershell
$summary = gcloud storage cat "$outputPrefix/summary.json" | ConvertFrom-Json
$summary | Select-Object worklist_count,sha256_verified_image_count,unresolved_count,pages
$summary.family_hints_not_ground_truth
gcloud storage cp "$outputPrefix/contact-sheet-01.jpg" ".\jointinspect-contact-sheet-01.jpg"
Start-Process ".\jointinspect-contact-sheet-01.jpg"
gcloud storage cp "$outputPrefix/review-worklist-verified.csv" ".\unified-review-worklist-verified.csv"
~~~

If all 80 objects were verified there should be 4 JPG contact sheets.
Inspect the summary's unresolved reasons if the count is smaller; do not
assume every image exists or matches the registry hash.

## What to review in the sheets

For each selected frame, inspect whether a real pipe joint is visible,
whether the source defect label is justified, and whether the camera/view
supports the intended geometric measurement. Confirm the original CCTV
video lineage rather than accepting PI005299/PI005455 naming as proof.

Once reviewed, fill the original verified-path CSV's source-family, geometry
and 4-point ROI columns manually and change review_status only for those
rows to READY_FOR_RESEARCH. Use the existing
scripts/cloud/create_unified_batch_manifest.py to convert ready rows into
a bounded GCS research manifest. Start with ~10-16 diverse frames before
testing all 80; don't repeatedly spend GPU time on near-identical frames.

This workflow does not establish defect accuracy, physical millimetres or
commercial-use permissions for any quarantined source.
